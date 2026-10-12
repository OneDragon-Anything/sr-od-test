"""战斗窗 exit 结算观测覆盖度守卫锁(T-23;2026-09-15 局深检 §8-1 形态根治)。

病理:长战斗形态整窗零「结算观测」行实锤(run_20260915_054718 深检:488s
主战 hp 3→0 扣血链零观测,复盘断节不可知)。修 = 战斗链收口守卫面
(cw_loop ``_on_battle_wait`` 出口归一点)计数留证:窗口单元 success 出口
+ 出战开窗在 + 本窗零结算观测行 → 缺陷台账 L1 行(只计数不停机)。

锁三面:
1. 守卫判定真值表(两 success 出口触发;bail/已观测/无窗开锚三静默臂);
2. 结算观测行写点刷新窗锚 + 结算真值传导(锚写点缺失 = 守卫永久静默的
   失效形态;顺带锁 hp_after → gs.hp 观察覆盖直入);
3. cw_loop 战斗分支接线消费守卫(接线断 = 覆盖度检测静默失效)。

驱动 = 裸实例 + 全桩面(零真实副作用;先例 = test_cw_loop_boss_frame_
exclusion 的 CwLoop ``__new__`` 装配)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from test.harness.fixture_controller import (
    fast_sleep,
)
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_telemetry_exit import (
    SEVERITY_L1_ALERT,
)
from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_battle_wait as bw_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
    count_settlement_obs_coverage_miss,
)
from sr_od.application.currency_war.telemetry import defects as _defects_mod

_FRAME = object()   # 稳定帧哨兵(桩只验判定流,不断言内容)


def test_guard_truth_table(monkeypatch) -> None:
    """锁1 守卫真值表:两 success 出口 + 窗锚失配 → L1 行;bail/已观测/
    无窗开锚(battle_ts=None)三静默臂不落行。"""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(_defects_mod, 'record_defect',
                        lambda *a, **k: calls.append((a, k)))
    # 触发臂①:白名单出口,本窗(出战开窗 100)零观测行(锚 = None)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=None),
        'back_to_loop') is True
    # 触发臂②:终局出口,锚滞留上一窗(150 ≠ 当前 200)= 本窗未写过
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=200.0, settled_battle_ts=150.0),
        'terminal_lobby') is True
    assert len(calls) == 2
    args0, kwargs0 = calls[0]
    assert args0[:2] == ('settlement', 'settle_obs_coverage_miss')
    assert kwargs0.get('severity') == SEVERITY_L1_ALERT
    # 静默臂①:本窗已观测(锚 = 窗锚)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=100.0),
        'back_to_loop') is False
    # 静默臂②:bail 出口不在窗口单元出口集(帧锚可重入续同窗,计则假阳)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=None),
        '战斗等待连续未识别,bail 交主循环兜底') is False
    # 静默臂③:接管局/残留屏帧锚入窗,无出战开窗锚
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=None, settled_battle_ts=None),
        'back_to_loop') is False
    assert len(calls) == 2


def test_record_round_outcome_refreshes_window_anchor(
        test_context, monkeypatch) -> None:
    """锁2 结算观测行写点刷新窗锚 + hp_after 传导:结算屏读点经生产链路
    (read_round_outcome → performance.record → apply_settlement_cover)
    后,窗锚 = 当前 battle_ts、gs.hp = 结算真值。"""
    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(get_ocr_result_list=lambda **k: []),
                        raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(bw_mod, 'read_phase_round',
                        lambda ctx, scr, round_caps=None: (1, 1))
    monkeypatch.setattr(
        bw_mod, 'read_round_outcome',
        lambda ctx, scr, **k: RoundOutcome(
            round_num=1, plane=1, node_type='普通战斗', comp_tag='c',
            hp_after=3, hp_confidence=1.0, killed=False))
    op._record_round_outcome(_FRAME)
    assert st.settled_battle_ts == 1234.0, \
        '结算观测行写点必须刷新窗锚(缺失 = 覆盖度守卫永久静默)'
    assert st.saw_settlement is True
    assert game_state_of(session).hp.value == 3, \
        '结算观测 hp_after 经结算覆盖写端直入 gs(观察赢唯一真值入口)'


class _BattleWaitStub:
    """battle_wait 替身:execute 返回 back_to_loop(窗口单元 success 出口)。"""

    journal = ''

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self):
        return SimpleNamespace(success=True, status='back_to_loop')


def _make_op(test_context, monkeypatch, settle: SettlementState) -> CwLoop:
    """CwLoop 裸装配 + 全桩面,战斗窗驻留闩置位(先例 = boss 帧排除锁)。"""
    op = CwLoop.__new__(CwLoop)
    op.ctx = test_context
    op._iter = 3                # 3+1=4:跳过 iter1 预检/焦点检查/首读分支
    op._stop_at_prep = False
    op._max_rounds = None
    op._battle_wait_active = True   # 战斗窗驻留闩(出战成功形态)
    op._battle_ts = 1234.0
    op._cw_resume_candidate = False
    op._cw_locked_resume = False
    op._settle = settle
    op._battle_wait = _BattleWaitStub(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_ocr',
                        lambda scr, text, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(cw_loop_mod, 'get_match_screen_name',
                        lambda ctx, scr, screen_name_list=None: None)
    monkeypatch.setattr(cw_loop_mod, 'save_decision_frame',
                        lambda *a, **k: None)
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda *a, **k: None)
    return op


def test_battle_branch_exit_consumes_coverage_guard(
        test_context, monkeypatch) -> None:
    """锁3 收口接线:战斗分支 op 返回 back_to_loop → 守卫被消费,零观测窗
    落 L1 行;已观测窗(锚匹配)不落行。"""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(_defects_mod, 'record_defect',
                        lambda *a, **k: calls.append((a, k)))
    # 场景①:出战开窗(battle_ts 注入)且本窗零观测行 → 守卫落行
    op = _make_op(test_context, monkeypatch,
                  SettlementState(battle_ts=1234.0, settled_battle_ts=None))
    with fast_sleep():
        _run_node(test_context, op, op.loop)
    assert len(calls) == 1, f'收口点应消费覆盖度守卫并落行:{calls}'
    args0, kwargs0 = calls[0]
    assert args0[:2] == ('settlement', 'settle_obs_coverage_miss')
    assert kwargs0.get('severity') == SEVERITY_L1_ALERT
    # 场景②:本窗已观测(锚 = 窗锚)→ 零行
    calls.clear()
    op2 = _make_op(test_context, monkeypatch,
                   SettlementState(battle_ts=1234.0,
                                   settled_battle_ts=1234.0))
    with fast_sleep():
        _run_node(test_context, op2, op2.loop)
    assert calls == [], '已观测窗 exit 不落覆盖度行'
