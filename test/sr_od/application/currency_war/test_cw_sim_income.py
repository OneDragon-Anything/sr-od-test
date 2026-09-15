"""sim 重做 S3(M04 轮首收入 + M15 连胜经济)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md``;锁面 = U04 败轮金(被败节点基础
奖励 + 利息,平面感知取键)/U05 补给轮照发/U06 无事件金/三分支单一源
值分解/连胜双账转移/持卡收入修饰聚合链。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import LostNodeRef
from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    register_sig_actors,
)
from sr_od.application.currency_war.sim.cw_sim_income import (
    IncomeApplied,
    apply_round_start_income,
    income_modifiers_of,
    streak_income_after,
    streak_signed_after,
)

register_sig_actors('TestSigWriter')


def _bs(gold: int, strategies: list[str] | None = None) -> GameState:
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    bs.observe(bs.gold, gold, sig=sig)
    if strategies:
        bs.observe(bs.active_strategies, list(strategies), sig=sig)
    return bs


# ============================================================ 三分支值分解

def test_supply_branch_pays_base_plus_interest_u05() -> None:
    """U05:补给轮照发基础奖励 + 利息,连胜分量恒 0(连胜计数不动是
    转移面的事,收入分支不发)。"""
    applied = apply_round_start_income(_bs(25), plane=1, round_num=5,
                                       node_type='supply', streak=3)
    assert applied.row.branch == 'supply'
    assert applied.row.base == 5 and applied.row.interest == 2
    assert applied.row.streak == 0 and applied.row.total == 7
    assert applied.gold_after == 32


def test_reward_branch_streak_paid_including_zero_counter() -> None:
    """奖励轮连胜照发(含 counter0=表首档 1,「连胜×0 仍发 1」85/85
    实证口径,M15);基础奖励平面感知键。"""
    hot = apply_round_start_income(_bs(25), plane=1, round_num=5,
                                   node_type='reward', streak=2)
    assert hot.row.streak == 2, 'streak_gold(2)=2'
    cold = apply_round_start_income(_bs(25), plane=1, round_num=5,
                                    node_type='reward', streak=0)
    assert cold.row.streak == 1, 'counter0 照发表首档'


def test_combat_branch_win_income() -> None:
    """常规战斗胜轮 = 基础 + 息 + 连胜×倍率(缺省倍率 1)。"""
    applied = apply_round_start_income(_bs(30), plane=1, round_num=6,
                                       node_type='battle', streak=4)
    assert applied.row.branch == 'combat'
    assert applied.row.base == 5 and applied.row.interest == 3
    assert applied.row.streak == 2, 'streak_gold(4)=2'
    assert applied.row.total == 10


def test_no_event_gold_component_u06() -> None:
    """U06:total 恒等于三分量之和,无第四随机分量(全分支)。"""
    for node_type in ('supply', 'reward', 'battle'):
        applied: IncomeApplied = apply_round_start_income(
            _bs(47), plane=1, round_num=4, node_type=node_type, streak=1)
        assert applied.row.total == (applied.row.base + applied.row.interest
                                     + applied.row.streak)


# ============================================================ U04 败轮金

def test_loss_comp_pays_lost_node_base_u04() -> None:
    """U04:败补 = 被败节点基础奖励(平面感知键)+ 利息,连胜分量强制
    0;类型表(LOSS_GOLD_BY_NODE)路径不在收入面。"""
    applied = apply_round_start_income(
        _bs(25), plane=1, round_num=3, node_type='battle', streak=2,
        pending_loss=LostNodeRef(plane=1, round_num=1, node_type='reward'))
    assert applied.row.branch == 'loss_comp'
    assert applied.row.base == 3, '被败节点 = P1r1 → 基础奖励键 3(非当前轮 5)'
    assert applied.row.streak == 0, '败补支连胜分量恒 0'
    assert applied.row.total == 3 + 2


def test_loss_pending_retained_on_supply_reward_rounds() -> None:
    """败态归宿:supply/reward 轮分支优先(收入 = 该轮自身查表),败态
    不传入 kernel(保留待下一战斗轮消费,模块 docstring 契约)。"""
    applied = apply_round_start_income(
        _bs(25), plane=1, round_num=5, node_type='supply', streak=2,
        pending_loss=LostNodeRef(plane=1, round_num=4, node_type='battle'))
    assert applied.row.branch == 'supply', '分支优先级:supply 先于败补'
    assert applied.row.base == 5, '基础奖励 = 当前节点键(非被败节点)'


# ============================================================ 连胜双账转移(M15)

def test_streak_transfers_combat_only() -> None:
    """战斗类胜 +1/败归零(带符号取负向计数);奖励/补给轮两账都不动。"""
    assert streak_income_after(3, node_type='battle', won=True) == 4
    assert streak_income_after(3, node_type='battle', won=False) == 0
    assert streak_income_after(3, node_type='reward', won=True) == 3
    assert streak_income_after(3, node_type='supply', won=False) == 3
    assert streak_signed_after(3, node_type='battle', won=True) == 4
    assert streak_signed_after(3, node_type='battle', won=False) == -1
    assert streak_signed_after(-2, node_type='battle', won=False) == -3
    assert streak_signed_after(-2, node_type='reward', won=False) == -2
    assert streak_signed_after(0, node_type='encounter', won=False) == -1


# ============================================================ 持卡收入修饰

def test_income_modifiers_from_strategies() -> None:
    """聚合链平移:息帽覆写取宽(利息上调 10)/连胜倍率取最大不叠乘
    (伟大征服 3.0)/每节点固定息求和。"""
    mult, flat, cap = income_modifiers_of(_bs(0, strategies=['利息上调']))
    assert (mult, flat, cap) == (1.0, 0, 10)
    mult, flat, cap = income_modifiers_of(_bs(0, strategies=['伟大征服']))
    assert mult == 3.0 and cap is None
    mult, flat, cap = income_modifiers_of(_bs(0, strategies=['狸财经狸']))
    assert flat == 2, '狸财经狸每节点固定息(+2)入 flat 分量'


def test_cap_override_changes_interest_math() -> None:
    """息帽覆写落账:持「利息上调」时 100 金息 = 10(缺省帽 5 档下
    封顶 5),经同一 round_start_income 分支。"""
    applied = apply_round_start_income(_bs(100, strategies=['利息上调']),
                                       plane=1, round_num=5,
                                       node_type='supply', streak=0)
    assert applied.row.interest == 10
