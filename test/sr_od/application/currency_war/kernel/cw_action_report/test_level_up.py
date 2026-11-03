"""等级帽覆写行为锁(镜像 src = kernel/cw_action_report/level_up.py 满级门
+ kernel/cw_economy 两推进算子 level_cap 形参消费链;登记面锁 =
cw_investments/test_strategy_kongzhi_guimo_entry.py,解析/聚合锁 =
kernel/test_economy.py,宝钻联动锁 = sim/cw_sim_backend/test_strategy_
pick_diamond_grant_sim_chain.py,本文件只锁行为面)。

测试面依据 = 迭代设计 designs/T-324-kongzhi-guimo.md §4 锁 3:
- 直构 gs(level=7 持控制规模)→ 满级门 applied=False reason='level_cap'
  零写 + 推进算子两件零推进(持卡世界等级轴 7 封顶);
- 无卡对照同参推进成功(跨 7 级断言——帽缺省 = MAX_PLAYER_LEVEL,
  门与算子对无卡局零扰);
- 边界 level=6 持卡升至 7 恰停(帽截断等级推进,溢出照常 cur 结转)。

建模语义 = 持卡生效的进度轴上限改写(cap-only,不回退已达等级;策略侧
lv 判据读注册表 level_max 系另一把尺,世界面拒发与规划失配 = 决策质量
议题,本锁不辖)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_level_up_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    MAX_PLAYER_LEVEL,
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    xp_apply_amount,
    xp_apply_clicks,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionLevelUpOp',
                  mode='compute')

_CARD = '控制规模'


def _hold(gs, cards: list[str]) -> None:
    """持卡播种(active_strategies 容器直写,终态契约单一源)。"""
    gs.write_logic(gs.active_strategies, list(cards),
                   produced_by='test', evidence='t:hold', sig=_SIG)


def _clicks_to(level: int) -> int:
    """恰跨 level 门槛的击数(表派生,禁手抄经验常数)。"""
    return XP_TO_NEXT_LEVEL[level] // XP_PER_BUY


def test_gate_blocks_at_held_cap_and_writes_nothing() -> None:
    """满级门随帽提前(锁 3 正面):level=7 持卡 → applied=False
    reason='level_cap',金/xp/level 零写(门在金写之前,整帧零投影)。"""
    gs = cw4_gs(gold=30, level=7, xp=(0, XP_TO_NEXT_LEVEL[7]))
    _hold(gs, [_CARD])
    gold_before = int(gs.gold.value)
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=5))
    assert out.applied is False and out.reason == 'level_cap'
    assert int(gs.gold.value) == gold_before, '门拦截帧应零金写'
    assert int(gs.level.value) == 7 and int(gs.xp.value[0]) == 0, '零推进'


def test_no_card_control_advances_past_seven() -> None:
    """无卡对照(锁 3):同参(level=7 cur=0,恰跨门槛击数)无卡局跨 7
    升 8——帽缺省 = MAX_PLAYER_LEVEL,门与算子对无卡局零扰。"""
    gs = cw4_gs(gold=30, level=7, xp=(0, XP_TO_NEXT_LEVEL[7]))
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=_clicks_to(7)))
    assert out.applied is True
    assert int(gs.level.value) == 8, f'无卡局应跨 7 升 8: {gs.level.value!r}'
    assert int(gs.xp.value[0]) == 0, '恰满门槛跨级清零'


def test_boundary_six_to_seven_stops_exactly() -> None:
    """边界(锁 3):level=6 持卡,超量击数推进恰停在 7(帽截断**推进**,
    不截累计——溢出留在当前级条内作 cur 结转,语义与无卡溢出结转同式,
    仅等级不再越 7)。"""
    gs = cw4_gs(gold=30, level=6, xp=(0, XP_TO_NEXT_LEVEL[6]))
    _hold(gs, [_CARD])
    clicks = _clicks_to(6) * 4
    out = report_action_level_up_param(
        gs, SimpleNamespace(cost=0), _SIG,
        executed=SimpleNamespace(levelup_clicks=clicks))
    assert out.applied is True
    assert int(gs.level.value) == 7, f'恰停 7: {gs.level.value!r}'
    assert int(gs.xp.value[0]) == clicks * XP_PER_BUY - XP_TO_NEXT_LEVEL[6], \
        '溢出结转进当前级条(帽只截等级推进)'


def test_operators_cap_param_zero_advance_at_cap() -> None:
    """推进算子两件帽形参(锁 3):xp_apply_clicks/xp_apply_amount 传
    level_cap=7 在 7 级零推进;缺省(无卡既有语义)对照推进成功。"""
    assert xp_apply_clicks(7, 0, 20, level_cap=7) == (7, 0)
    assert xp_apply_amount(7, 0, 500, level_cap=7) == (7, 0)
    assert xp_apply_clicks(7, 0, _clicks_to(7)) == (8, 0)
    assert xp_apply_amount(7, 0, XP_TO_NEXT_LEVEL[7]) == (8, 0)
    assert MAX_PLAYER_LEVEL == 10, '无卡缺省帽自证(语义单一源)'
