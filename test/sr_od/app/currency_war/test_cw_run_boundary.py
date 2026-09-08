"""开局遥测行 run_id 归属(ADR-0588:run 铸造边界对齐进局时刻)主题锁。

锁行为契约,不锁分布数值。state 模块全局(_CURRENT_RUN_ID/_RUN_CLOSED/
_RUN_MATCH/_RECORDER 等)按测试纪律 monkeypatch 桩化;recorder 落盘指
tmp_path,禁写真 .debug/。setup 桩清单(方案审 攻击面7 点名):

- ensure → start_run 链会调 ``ledger_hooks.recover_dangling_run_summaries``
  (state.start_run 兜底回填)——须同桩(w603 先例);
- recorder 用真 ``TelemetryRecorder(enabled=True, replay_dir=tmp_path)``
  (经 state._RECORDER 槽注入),真实落盘行可断言,无 SimpleNamespace 缺
  start_run/_append 方法的 AttributeError 面。

锁面(方案 §4.1;L5 悬空防护与 L2 第三分支同 gate 分支,按 README 规则 7
「重复断言构成删/并理由」并入 L2,场景命名保留;原 L4 冷启动零行为 L3
断言面真子集,同规则并入 L3):
L1 幂等认领 / L2 换局重铸三分支(含悬空防护形态)/ L3 选卡前铸造主锁
(兼辖冷启动首局)/ L6 loop 构造认领(入口已铸 open run + 同容器不重铸)
/ L7 复位正规入口(reset_run_state 清 run 态簇,含难度列/简报缓冲——
三审报告-第三波.md F3,易失产物待 ADR 回填)/ L8 假局 teardown 复位链
× 后续部分桩化 ensure(组合复位锁;出处 .debug/temp/currency_war/attacks/
three_review_20260908/三审报告-第二波.md F1,易失产物待 ADR 回填)。
"""
from __future__ import annotations

import json
from datetime import datetime as _real_datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fixtures.cw_harness import fake_p1_run

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import (
    recorder as recorder_mod,
)
from sr_od.application.currency_war.telemetry import (
    state as state_mod,
)
from test.harness.fixture_controller import (
    enter_running_state,
    reset_running_state,
)


class _FakeClock:
    """单调假钟:每次 now() 前进 1 秒。

    run_id 粒度 = 秒(state.start_run 内联 strftime);同一测试秒内连铸两次
    会撞 id(与实现正确性无关的时间粒度伪红),假钟让铸造序列确定可分。
    """

    _n: int = 0

    @staticmethod
    def now() -> Any:
        _FakeClock._n += 1
        return _real_datetime(2026, 9, 7, 8, 0, _FakeClock._n)


@pytest.fixture()
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """telemetry 模块全局桩化 + recorder 指向 tmp_path(测试隔离整条副作用链)。"""
    monkeypatch.setattr(state_mod, 'datetime', _FakeClock)
    _FakeClock._n = 0
    monkeypatch.setattr(state_mod, '_RECORDER',
                        recorder_mod.TelemetryRecorder(enabled=True,
                                                       replay_dir=tmp_path))
    monkeypatch.setattr(state_mod, '_CURRENT_RUN_ID', '')
    monkeypatch.setattr(state_mod, '_CURRENT_DIFFICULTY', '')
    monkeypatch.setattr(state_mod, '_RUN_CLOSED', False)
    monkeypatch.setattr(state_mod, '_RUN_MATCH', None)
    monkeypatch.setattr(state_mod, '_PENDING_BRIEFING_ROWS', [])
    # 缺陷复现计数/L0 副作用链隔离(与 w603 同款:构造与铸造路径会触碰)
    monkeypatch.setattr(state_mod, '_defect_seen', {})
    monkeypatch.setattr(state_mod, '_defect_seen_run', '')
    monkeypatch.setattr(state_mod, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(state_mod, '_L0_ANDON_FIRED_RUNS', set())
    # ensure → start_run → 兜底回填:同桩(w603 先例,防真实 .debug/ 读面)
    monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                        lambda: None)
    return tmp_path


def _count_start_run(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """真 start_run 外包计数壳(门控行为保真,铸造次数可断言)。"""
    calls: list[str] = []
    real = state_mod.start_run

    def _counting(difficulty: str = '') -> str:
        calls.append(difficulty)
        return real(difficulty)

    monkeypatch.setattr(state_mod, 'start_run', _counting)
    return calls


def _invest_rows(tmp_path: Path) -> list[dict]:
    p = tmp_path / 'invest_cards.jsonl'
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


def test_ensure_same_match_claims_existing_run(
        _isolated_state: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L1 幂等认领:同一 match 容器连续两次 ensure → 同一 run_id,第二次
    不触发 start_run(铸造一次/局;loop 侧认领不重铸)。"""
    calls = _count_start_run(monkeypatch)
    m = SimpleNamespace(session=None)
    rid1 = state_mod.ensure_run_started(m, 'A8')
    rid2 = state_mod.ensure_run_started(m, 'A8')
    assert rid1 == rid2 and rid1.startswith('run_')
    assert calls == ['A8'], f'第二次 ensure 不得重铸,实得铸造 {calls!r}'


def test_ensure_remaps_on_new_container_closed_or_empty(
        _isolated_state: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2 换局重铸三分支(gate 恰三支,不多不少):不同容器对象 = 悬空
    open run 防护(入口铸造后入口链 FAIL,新局确凿信号处容器弃置重建);
    _RUN_CLOSED = 上局已收口;run_id 空 = 进程首局/重启。三分支各自产出
    新 run_id。"""
    calls = _count_start_run(monkeypatch)
    m1 = SimpleNamespace(session=None)
    m2 = SimpleNamespace(session=None)
    rid1 = state_mod.ensure_run_started(m1, 'A8')
    # 分支③:换容器(悬空防护形态)→ 重铸
    rid2 = state_mod.ensure_run_started(m2, 'A8')
    assert rid2 != rid1
    # 分支②:上局收口 → 重铸
    monkeypatch.setattr(state_mod, '_RUN_CLOSED', True)
    rid3 = state_mod.ensure_run_started(m2, 'A8')
    assert rid3 != rid2
    assert state_mod._RUN_CLOSED is False   # start_run 复位关闭位
    # 分支①:run_id 空(冷启动/重启)→ 铸造
    monkeypatch.setattr(state_mod, '_CURRENT_RUN_ID', '')
    rid4 = state_mod.ensure_run_started(m2, 'A8')
    assert rid4 != rid3
    assert len(calls) == 4, (
        f'首铸 + 三次门控命中各铸一次(共 4),实得 {calls!r}')


def test_invest_row_before_loop_claim_lands_on_entry_run(
        _isolated_state: Path) -> None:
    """L3 选卡前铸造主锁(S12 病灶序列):ensure(m) → record_invest_cards
    ('env', …) → 再次 ensure(m)(模拟 loop 认领)→ 落盘行 run_id == 入口
    run_id 且 current_run_id 未变。回归(行盖上局戳/丢失)= 红。
    首个 ensure 即冷启动铸造(分支①,桩面 _CURRENT_RUN_ID 为空起步),
    兼辖「冷启动首局 env 行落盘」(原独立冷启动测为断言面真子集,已并)。"""
    m = SimpleNamespace(session=None)
    rid_entry = state_mod.ensure_run_started(m, 'A8')
    recorder_mod.record_invest_cards('env', [
        {'idx': 0, 'name': '昼之半神概念股', 'x': 300,
         'effect_text': 'e', 'chosen': True}])
    rid_claim = state_mod.ensure_run_started(m, 'A8')
    assert rid_claim == rid_entry
    rows = _invest_rows(_isolated_state)
    assert len(rows) == 1
    assert rows[0]['run_id'] == rid_entry, (
        '开局 env 行必须归属入口铸造的 run(修前行盖上局戳/首局被丢)')
    assert state_mod.current_run_id() == rid_entry


def test_loop_construction_claims_entry_minted_run(
        _isolated_state: Path, monkeypatch: pytest.MonkeyPatch,
        test_context) -> None:
    """L6 loop 构造认领(备1 形态):入口已铸 open run + 同容器 → CwLoop
    构造不重铸(同一物理对局一段一 id;防把认领改回无条件重铸的回归)。
    分配器桩化(模块级全局一并桩化纪律);ensure/start_run 走真实现。"""
    from sr_od.application.currency_war.operations import cw_loop as loop_mod
    calls = _count_start_run(monkeypatch)
    monkeypatch.setattr(loop_mod, '_get_or_init_allocator', lambda ctx: None)
    m = SimpleNamespace(session=None)
    monkeypatch.setattr(test_context, 'cw_match', m, raising=False)
    monkeypatch.setattr(test_context, 'cw_selected_difficulty', 'A8',
                        raising=False)
    rid_entry = state_mod.ensure_run_started(m, 'A8')
    loop_mod.CwLoop(test_context)
    assert calls == ['A8'], (
        f'入口已铸同容器 open run,loop 构造须认领不重铸,实得铸造 {calls!r}')
    assert state_mod.current_run_id() == rid_entry


def test_reset_run_state_clears_run_cluster(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """L7 复位正规入口:run 态簇五件脏值 → reset_run_state 后全回生产缺省。

    红的语义 = 复位链缺件:漏清任一件即假局残留病理的入口侧复发
    (出处见文件头 L8 行)——收口位残留会让后续直调 ensure 的测试把
    open run 误判「上局已收口」走重铸假分支;难度列/简报缓冲残留 =
    遥测内容污染(三审报告-第三波.md F3,易失产物待 ADR 回填:决策行
    带前局难度、简报行归属错局,无分支翻转)。脏值经 monkeypatch 注入,
    teardown 自动还原,不依赖本测试的复位调用兜底。"""
    monkeypatch.setattr(state_mod, '_CURRENT_RUN_ID', 'run_dirty')
    monkeypatch.setattr(state_mod, '_RUN_MATCH', object())
    monkeypatch.setattr(state_mod, '_RUN_CLOSED', True)
    monkeypatch.setattr(state_mod, '_CURRENT_DIFFICULTY', 'A9_stale')
    monkeypatch.setattr(state_mod, '_PENDING_BRIEFING_ROWS',
                        [{'stale': 'previous_run'}])
    state_mod.reset_run_state()
    assert state_mod.current_run_id() == ''
    assert state_mod._RUN_MATCH is None
    assert state_mod._RUN_CLOSED is False, (
        '复位入口漏清收口位 _RUN_CLOSED(ensure 门与 recorder 简报缓冲'
        '都消费该位,残留即跨测试假分支)')
    assert state_mod._CURRENT_DIFFICULTY == '', (
        '复位入口漏清难度列 _CURRENT_DIFFICULTY(recorder 决策行难度列'
        '消费,残留 = 后续测试遥测行带前局难度,F3)')
    assert state_mod._PENDING_BRIEFING_ROWS == [], (
        '复位入口漏清简报缓冲 _PENDING_BRIEFING_ROWS(下一局 start_run '
        '把缓冲行归属新局,残留 = 简报行错局归属,F3)')


def test_fake_p1_teardown_resets_cluster_before_next_ensure(
        test_context, monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path) -> None:
    """L8 组合复位锁:假局跑完 → 后续**部分桩化**测试直调 ensure 须认领
    open run,不得见「上局已收口」假分支(出处见文件头 L8 行;ensure 门
    语义见 ADR-0588)。

    复现病理序:阶段① 真 harness 驱动最小假局,局终生产
    record_run_summary 裸写 _RUN_CLOSED=True(前提自检,没置位先红,
    防锁空转);阶段② with 块退出走 teardown 复位链后,按病理同形的
    漏桩清单只桩 run_id/容器 token/recorder——独独不桩 _RUN_CLOSED——
    ensure 应认领现有 open run(同容器一段一 id)。harness teardown 漏
    复位时残留 True 误判已收口走重铸 → 红。

    分层申报:本锁辖「进程内 with 块进出」的 harness 复位链;跨测试
    残留面由 conftest autouse 钉桩(_RUN_CLOSED=False)把守,两道防线
    不同层,互不替代。"""
    enter_running_state(test_context)
    try:
        with fake_p1_run(test_context, monkeypatch, tmp_path, 1,
                         node_sequence=['battle'], initial_gold=30) as run:
            run.run_p1(settle=False)
            assert state_mod._RUN_CLOSED is True, (
                '前提自检失败:局终 record_run_summary 未置收口位'
                '(本锁阶段②判定失去前提)')
        # 阶段②:teardown 已跑(端口卸载 + run 态簇复位 + 两根槽复位);
        # 部分桩化重建 open run 语境——漏桩清单与 F1 病理同形
        monkeypatch.setattr(state_mod, '_CURRENT_RUN_ID', 'run_open_next')
        m = SimpleNamespace(session=None)
        monkeypatch.setattr(state_mod, '_RUN_MATCH', m)
        monkeypatch.setattr(
            state_mod, '_RECORDER',
            recorder_mod.TelemetryRecorder(enabled=True,
                                           replay_dir=tmp_path / 'next'))
        # ensure → start_run 链的兜底回填同桩(w603/_isolated_state 先例,
        # 防真实 .debug/ 读面;红路径的重铸分支也会经过它)
        monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                            lambda: None)
        rid = state_mod.ensure_run_started(m, 'A8')
        assert rid == 'run_open_next', (
            'run 态簇复位缺口:上局收口位残留把 open run 误判已收口'
            '(ensure 走了重铸假分支)')
    finally:
        reset_running_state(test_context, test_context.cw_match)
