"""test_cw_w603_telemetry_wiring 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_state import GameState

# 分包期 6:恢复兜底族(DESIGN §4.4 hooks 行)归 sim/ledger_hooks,
# telstate.start_run 经该模块属性查找调用 → 桩点随生产引用址重钉
from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of
from sr_od.application.currency_war.telemetry import query
from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry import state as telstate


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w603t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(telstate, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(telstate, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(telstate, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(telstate, '_RUN_CLOSED', False)
    monkeypatch.setattr(telstate, '_PENDING_BRIEFING_ROWS', [])
    # 缺陷台账复现计数/L0 副作用链隔离(W505 同款)
    monkeypatch.setattr(telstate, '_defect_seen', {})
    monkeypatch.setattr(telstate, '_defect_seen_run', '')
    monkeypatch.setattr(telstate, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(telstate, '_L0_ANDON_FIRED_RUNS', set())
    # 分包期 4:obs_conflict 的 run_id 归属键读 kernel.cw_telemetry_exit 钩子位,
    # provider 钉回本模块 current_run_id(随 _CURRENT_RUN_ID 桩值走)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        telstate.current_run_id)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 披露键进 decisions 遥测行 =====

def _fake_match(counters: tuple[int, int] = (2, 1),
                ledger: object | None = None):
    """fake ctx.cw_match 容器(session 带披露键;record_outcome 板深快照同款槽)。"""
    sess = StrategySession()
    state_of(sess).v3_blood_budget_rejects = counters[0]
    state_of(sess).v3_blood_budget_refresh_rejects = counters[1]
    exec_state_of(sess).xp_expect_ledger = ledger
    return SimpleNamespace(session=sess)


def test_decision_row_carries_disclosure_keys(tmp_path: Path, monkeypatch) -> None:
    """锁①a:record_decision 落盘行带血预算计数/经验账本字段。

    (p1_downgrade_active 写入面已随 v2 退役链退役——统一迁移批按底稿
    MAP ⓪ A7 退役,schema 字段历史只读,新数据恒 None。)
    """
    _setup_recorder(monkeypatch, tmp_path)

    from sr_od.application.currency_war.kernel.cw_prep_expect import XpLedger
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF',
                        [_fake_match((2, 1), XpLedger(level=3, xp_cur=4,
                                                      xp_next=8, anchored=True))])
    st = GameState(gold=30, hp=50, round_num=6, plane=1)
    telstate.get_recorder().record_decision('w603a', 'A8', st, '', {}, {}, [])
    rows = _rows(tmp_path, 'decisions.jsonl')
    assert len(rows) == 1
    r = rows[0]
    assert r['sess_blood_budget_rejects'] == 2
    assert r['sess_blood_budget_refresh_rejects'] == 1
    assert r['p1_downgrade_active'] is None   # 写入面退役,新数据恒缺省
    led = r['xp_expect_ledger']
    assert isinstance(led, dict) and led['level'] == 3 and led['anchored'] is True


def test_decision_row_downgrade_inactive_and_no_match(tmp_path: Path, monkeypatch) -> None:
    """锁①b:无 match 注册 → 键恒 None(离线/测试缺省,旧 schema 不破坏;
    p1_downgrade_active 写入面已退役,字段恒 None)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(telstate, '_CTX_MATCH_REF',
                        [_fake_match((0, 0), None)])
    st = GameState(gold=30, hp=90, round_num=2, plane=1)
    telstate.get_recorder().record_decision('w603b', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['p1_downgrade_active'] is None   # 写入面退役,新数据恒缺省
    assert r['sess_blood_budget_rejects'] == 0
    assert r['xp_expect_ledger'] is None

    monkeypatch.setattr(telstate, '_CTX_MATCH_REF', [None])
    telstate.get_recorder().record_decision(
        'w603b2', 'A8', GameState(gold=30, hp=50, round_num=6, plane=1),
        '', {}, {}, [])
    r2 = _rows(tmp_path, 'decisions.jsonl')[1]
    assert r2['sess_blood_budget_rejects'] is None
    assert r2['xp_expect_ledger'] is None


def test_session_field_xp_expect_ledger_declared() -> None:
    """锁①c:xp_expect_ledger 为 ExecState 正式字段(session 职责分离批:
    执行层期望账迁 kernel/cw_exec_state.py,读端 getattr 读写不变)。"""
    import dataclasses

    from sr_od.application.currency_war.kernel.cw_exec_state import ExecState
    names = {f.name for f in dataclasses.fields(ExecState)}
    assert 'xp_expect_ledger' in names
    sess = StrategySession()
    assert exec_state_of(sess).xp_expect_ledger is None   # 新建 session 缺省未锚定


# w611 储备/义务四键(sess_reserve_cap/overflow/budget/spent)读端透传锁
# = test_cw_budget_disclosure.py::TestBudgetDisclosureWriteRead::
#   test_recorder_row_keys_non_none_and_match_state(超集:写端经 assemble+
#   accrue 真生产链 + reason 键 + None 边界;本文件原直调注入形态已删)。


# ===== ② obs_conflicts 补 run_id =====

def test_obs_conflict_row_carries_run_id(tmp_path: Path, monkeypatch) -> None:
    """锁②a:汇点写入行带 run_id(取 current_run_id;调用方零改动)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_w603x')
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL',
                        tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('gold_delta', 45, 20, None,
                            verdict='测试', source='w603')
    r = _rows(tmp_path, 'obs_conflicts.jsonl')[0]
    assert r['run_id'] == 'run_w603x'
    assert r['field'] == 'gold_delta'


def test_obs_conflict_no_run_id_outside_run(tmp_path: Path, monkeypatch) -> None:
    """锁②b:局外冲突(进程首局前,run_id 空)不写假键(历史行同形)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL',
                        tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('level', 4, 5, None, verdict='测试')
    r = _rows(tmp_path, 'obs_conflicts.jsonl')[0]
    assert 'run_id' not in r


def test_query_obs_conflicts_filters_by_run_id(tmp_path: Path) -> None:
    """锁②c:读端 --run 过滤「有键且相等」;历史行(无键)只在全量视图出现。"""
    p = tmp_path / 'obs_conflicts.jsonl'
    p.write_text(
        json.dumps({'ts': '2026-08-30T01:00:00', 'field': 'gold',
                    'run_id': 'run_a'}) + '\n'
        + json.dumps({'ts': '2026-08-30T02:00:00', 'field': 'hp'}) + '\n',
        encoding='utf-8')
    filtered = query.query_obs_conflicts(tmp_path, 'run_a')
    assert any('[gold]' in ln for ln in filtered)
    assert not any('[hp]' in ln for ln in filtered)   # 历史行(无键)被过滤
    assert query.query_obs_conflicts(tmp_path, 'run_b') == ['  (无记录)']
    # 全量(空 run_id)= 历史行 + 新行都在
    full = query.query_obs_conflicts(tmp_path, '')
    assert any('[hp]' in ln for ln in full) and any('[gold]' in ln for ln in full)


# ===== ③ 简报行 run_id 归属(局间缓冲)=====

def test_briefing_before_first_run_lands_in_next_run(tmp_path: Path,
                                                     monkeypatch) -> None:
    """锁③a:进程首局(无 live run)简报行不再被丢 → start_run 后以新 id 补写,
    ts 保留采集时点(归属滞后/丢失双修)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='')
    recorder.record_exogenous(0, 'briefing', detail='affixes=[甲] bosses=[乙]')
    # 局前:不落盘,只缓冲
    assert _rows(tmp_path, 'exogenous.jsonl') == []
    assert len(telstate._PENDING_BRIEFING_ROWS) == 1
    buffered_ts = telstate._PENDING_BRIEFING_ROWS[0]['ts']
    # 新局开局:缓冲以新 run_id 补写
    # 分包期 6:恢复兜底族归 sim/ledger_hooks(DESIGN §4.4 hooks 行),
    # telstate.start_run 经 _lh. 属性查找调用 → 桩点随生产引用址重钉
    monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                        lambda: None)
    new_rid = telstate.start_run('A8')
    assert new_rid.startswith('run_')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1
    assert rows[0]['run_id'] == new_rid
    assert rows[0]['kind'] == 'briefing'
    assert rows[0]['ts'] == buffered_ts   # ts=采集时点,非补写时点
    assert telstate._PENDING_BRIEFING_ROWS == []


def test_briefing_after_run_closed_lands_in_next_run(tmp_path: Path,
                                                     monkeypatch) -> None:
    """锁③b:局终 summary 后(run 关闭位)简报行不再挂旧 run_id(W576 组5.1
    归属滞后的根因面)→ 缓冲到下一局。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_old')
    telstate.record_run_summary('loss', 2, 8, 3)
    assert telstate._RUN_CLOSED is True
    recorder.record_exogenous(0, 'briefing', detail='d1')
    # 旧 run_id 不再直接吃行
    assert _rows(tmp_path, 'exogenous.jsonl') == []
    monkeypatch.setattr(ledger_hooks, 'recover_dangling_run_summaries',
                        lambda: None)
    new_rid = telstate.start_run('A8')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1 and rows[0]['run_id'] == new_rid
    # 开局复位关闭位:局中简报(cw_loop 位面分支)照常直写
    assert telstate._RUN_CLOSED is False


def test_briefing_mid_run_writes_directly_other_kinds_noop(tmp_path: Path,
                                                           monkeypatch) -> None:
    """锁③c:live run 内 briefing 直写不变;其余 kind 维持原 no-op 门
    (局外事件族不归属下一局,行为面不外溢)。"""
    _setup_recorder(monkeypatch, tmp_path, run_id='run_live')
    recorder.record_exogenous(3, 'briefing', detail='plane2')
    rows = _rows(tmp_path, 'exogenous.jsonl')
    assert len(rows) == 1
    assert rows[0]['run_id'] == 'run_live' and rows[0]['kind'] == 'briefing'
    assert telstate._PENDING_BRIEFING_ROWS == []
    # 其余 kind 维持原 no-op 门(仅局外/无 live run 时丢,不入缓冲)
    monkeypatch.setattr(telstate, '_CURRENT_RUN_ID', '')
    recorder.record_exogenous(0, 'node_enter', detail='局外弹窗')
    assert len(_rows(tmp_path, 'exogenous.jsonl')) == 1
    assert telstate._PENDING_BRIEFING_ROWS == []


