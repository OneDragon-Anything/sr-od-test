"""T-230 店开态种子分叉恢复路由回归锁(2026-09-15 T-227/T-251 邻接件)。

病理:T-251 把种子守卫的「粘性死循环」治成两形态出口(空账/接管待办),
但**非接管有账真分歧**(bug 嫌疑形态)仍走守卫 AssertionError → 节点级
异常重试 → 重入店开态 → 再炸的粘性环(守卫消息自注的「下一入口 heavy
读屏重建可归零」在该路径结构性不可达,T-227 §⑤2 定性待立项)。本批 =
恢复路由:守卫红后收店交回外循环 → 备战环 heavy 观察同帧重建两账 →
再入重判(对局预算一次,SEED_DIVERGENCE_RECOVER_LIMIT 论证;预算耗尽
单次停,0n 分支经 stopped 标记 round_fail 交兜底链)。

锁的五件事:
1. 分叉→恢复→续行:非接管有账真分歧在 run_buy_waves 段顶被拦截,收店
   动作恰发一次,返回 (None, ledger) 本 visit 收工(外循环交回语义),
   counters 计数落位 + 台账 recovered 行显影,两账零写(重建交备战环);
2. 恢复上限触发→停:预算已耗时返回 (round_fail, None)、stopped 标记
   置位、收店零调用(不再给第二次 = 防恢复循环);
3. 0n 消费谓词:stopped 标记三态(置位/未置/载体缺席)——外循环停机
   判据单一源;
4. 预算谓词边界(载体缺席/0/上限-1/上限)——判据禁内联拍值的单一源;
5. 载体缺席保持原语义:strategy_state 缺席(非 mandate 生产形态)时
   AssertionError 原样上抛(节点级重试链,与路由落地前行为逐位一致)。

附:守卫 seed 分支文案勘误锁(旧文案「tracked 主账为空」与实际条件
「双账多集不等任意方向」不符,T-227 §⑤5/T-251 §⑤2 继承件)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    guard_expected_vs_tracked,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards import (
    CW4_KEY_SEED_DIVERGENCE_RECOVERIES,
    CW4_KEY_SEED_DIVERGENCE_STOPPED,
    SEED_DIVERGENCE_RECOVER_LIMIT,
    recover_seed_divergence_by_close_shop,
    seed_divergence_recovery_budget,
    seed_divergence_stopped,
)
from sr_od.application.currency_war.telemetry import defects

# 分叉构造:tracked 有账(执行侧账面),容器 bench 不写(守卫 expected 侧
# 空)——多集真分歧,seed 守卫必红;非接管(无 cw_resume_seed_anchor)。
_TRACKED_3 = [('花火', 1), ('不死途', 3), ('艾丝妲', 1)]


def _tracked_bench() -> list:
    return [BenchChar(slot=i + 1, char_id=n, star=s)
            for i, (n, s) in enumerate(_TRACKED_3)]


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入(测试零真实副作用)+ 留调用记录供显影断言。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _run_buy_waves_divergent_host(monkeypatch: pytest.MonkeyPatch,
                                  tmp_path, counters: dict | None):
    """分叉形态离线宿主:复用 T-251 测试/budget 披露宿主的替身面。

    构造 = tracked 有账 + 容器 bench 未观察(真分歧)→ 段顶 T-251 出口
    走 'tracked_present' 红线(零读屏)→ 种子守卫 AssertionError →
    恢复路由接管。返回 (run_buy_waves 结果元组, counters, close_calls,
    session)。
    counters=None = 载体缺席形态(strategy_state 缺席)。
    """
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        assembly as assembly_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(run 态簇 + 缺陷台账去重键;台账行落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't230host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    class _IdleStrategy:
        """替身决策源:恢复路径在首动作前返回,decide 不可达。"""

        def decide_shop_action(self, session, config):
            raise AssertionError('恢复路径不可达决策循环')

    match = CurrencyWarMatch(_IdleStrategy(), StrategySession())
    # 载体确定态:显式覆盖(工厂注册态依赖 import 顺序,不可依赖);
    # cw4_segment_serial = run_buy_waves 段序号消费面(SimpleNamespace 动态属性)。
    match.session.strategy_state = (
        SimpleNamespace(cw4_counters=counters, cw4_segment_serial=0)
        if counters is not None else None)
    # 分叉构造:tracked 有账,容器 bench 零写(守卫 expected 侧空)。
    exec_state_of(match.session).tracked_bench_chars = _tracked_bench()

    class _Op:
        """离线宿主替身:run_buy_waves 消费面仅 ctx/screenshot/park_cursor。"""

        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

        def save_screenshot(self, prefix: str = '') -> str:
            return ''

        def round_fail(self, status: str = None, data=None, wait: float = None):
            return SimpleNamespace(status=status, is_success=False)

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    # T-251 出口读链替身(本分叉形态走 tracked_present 红线,不可达;
    # 段顶工厂构造仍需可用)。
    monkeypatch.setattr(buy_mod, 'make_seed_screen_bench_read',
                        lambda ctx, session: (lambda frame: []))
    monkeypatch.setattr(assembly_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)
    # 收店替身:记录调用(lazy import 每次取模块属性,monkeypatch 生效)。
    close_calls: list = []
    import sr_od.application.currency_war.operations.cw_op.cw_op_close_shop as close_mod
    monkeypatch.setattr(close_mod, 'close_shop',
                        lambda op: close_calls.append(op))

    result = buy_mod.run_buy_waves(_Op(), match)
    return result, counters, close_calls, match.session


def test_divergence_recovers_by_close_shop_and_visit_ends(monkeypatch,
                                                          tmp_path):
    """锁1 分叉→恢复→续行:守卫红被拦截,收店恰一次,visit 正常收工。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {}

    (rr, ledger), _c, close_calls, session = _run_buy_waves_divergent_host(
        monkeypatch, tmp_path, counters)

    assert rr is None          # (None, ledger) = 本 visit 收工交回外循环
    assert ledger is not None
    assert len(close_calls) == 1   # 收店动作恰发一次
    assert counters[CW4_KEY_SEED_DIVERGENCE_RECOVERIES] == 1   # 预算计数落位
    assert CW4_KEY_SEED_DIVERGENCE_STOPPED not in counters   # 未停机
    assert any(kind == 'seed_divergence_recovered' for _s, kind, _e, _o
               in rows)   # 台账 recovered 行显影(判读入口)
    # 两账零写:重建交备战环 heavy 观察,本路由不代偿(守卫只断言)。
    assert [(b.char_id, b.star) for b in
            (exec_state_of(session).tracked_bench_chars or [])
            if b is not None] == _TRACKED_3


def test_recovery_budget_exhausted_stops_once(monkeypatch, tmp_path):
    """锁2 恢复上限触发→停:预算已耗返回 (round_fail, None),收店零调用。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {CW4_KEY_SEED_DIVERGENCE_RECOVERIES:
                      SEED_DIVERGENCE_RECOVER_LIMIT}

    (rr, ledger), _c, close_calls, _session = _run_buy_waves_divergent_host(
        monkeypatch, tmp_path, counters)

    assert rr is not None and not rr.is_success   # round_fail 单次停
    assert ledger is None   # (round_fail, None) 停机钩子先例形态
    assert close_calls == []   # 不再恢复(防恢复循环)
    assert counters[CW4_KEY_SEED_DIVERGENCE_STOPPED] == 1   # 停机标记置位
    assert any(kind == 'seed_divergence_stop' for _s, kind, _e, _o in rows)


def test_stopped_marker_predicate_three_states():
    """锁3 0n 消费谓词三态:置位/未置/载体缺席(外循环判据单一源)。"""
    assert seed_divergence_stopped({CW4_KEY_SEED_DIVERGENCE_STOPPED: 1})
    assert not seed_divergence_stopped({CW4_KEY_SEED_DIVERGENCE_STOPPED: 0})
    assert not seed_divergence_stopped({})
    assert not seed_divergence_stopped(None)   # 载体缺席 = 无停机语义


def test_budget_predicate_boundaries():
    """锁4 预算谓词边界:载体缺席/0/上限-1/上限(禁调用点内联拍值)。"""
    assert not seed_divergence_recovery_budget(None)   # 载体缺席不恢复
    assert not seed_divergence_recovery_budget('not-a-dict')
    assert seed_divergence_recovery_budget({})
    assert seed_divergence_recovery_budget(
        {CW4_KEY_SEED_DIVERGENCE_RECOVERIES: SEED_DIVERGENCE_RECOVER_LIMIT - 1})
    assert not seed_divergence_recovery_budget(
        {CW4_KEY_SEED_DIVERGENCE_RECOVERIES: SEED_DIVERGENCE_RECOVER_LIMIT})


def test_carrier_absent_keeps_pre_route_assertion_semantics():
    """锁5 载体缺席保持原语义:strategy_state 缺席 → 断言原样重抛。

    (run_buy_waves 段顶行为面读点对 None 态本就显式炸错——mis-assembly
    信号契约;本锁钉恢复函数自身的缺席分支,防御不依赖调用点前置。)
    """
    session = StrategySession()
    session.strategy_state = None   # 载体缺席(非 mandate 生产形态)
    _err = AssertionError('seed diverged')
    with pytest.raises(AssertionError) as ei:
        recover_seed_divergence_by_close_shop(
            SimpleNamespace(save_screenshot=lambda prefix='': '',
                            round_fail=lambda status=None: None),
            SimpleNamespace(session=session), None, _err,
            close_fn=lambda: None)
    assert ei.value is _err   # 原样重抛(非包装、非吞)


def test_recover_fn_returns_fail_round_and_marks_stopped(monkeypatch):
    """锁6 停机支函数级:预算耗尽返 round_fail + 置标记 + close_fn 注入缝。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {CW4_KEY_SEED_DIVERGENCE_RECOVERIES:
                      SEED_DIVERGENCE_RECOVER_LIMIT}
    session = StrategySession()
    session.strategy_state = SimpleNamespace(cw4_counters=counters)
    close_calls: list = []

    rec = recover_seed_divergence_by_close_shop(
        SimpleNamespace(save_screenshot=lambda prefix='': '',
                        round_fail=lambda status=None, data=None,
                        wait=None: SimpleNamespace(status=status,
                                                   is_success=False)),
        SimpleNamespace(session=session), None,
        AssertionError('seed diverged'), close_fn=lambda: close_calls.append(1))

    assert rec is not None and not rec.is_success
    assert close_calls == []   # 停机支不收店
    assert counters[CW4_KEY_SEED_DIVERGENCE_STOPPED] == 1
    assert any(kind == 'seed_divergence_stop' for _s, kind, _e, _o in rows)


def test_guard_seed_message_errata():
    """锁7 文案勘误:消息与实际条件对齐(不再误称「tracked 主账为空」)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        board_state_of,
    )
    session = StrategySession()
    session.strategy_state = SimpleNamespace(cw4_counters={})
    exec_state_of(session).tracked_bench_chars = _tracked_bench()
    with pytest.raises(AssertionError) as ei:
        guard_expected_vs_tracked(board_state_of(session), session,
                                  stage='seed')
    msg = str(ei.value)
    assert '主账为空' not in msg   # 旧文案退役(T-227 §⑤5 勘误件)
    assert '多集真分歧' in msg   # 新文案 = 实际条件(多集不等任意方向)
    assert 'expected=' in msg and 'tracked=' in msg   # 凭据组成保留
