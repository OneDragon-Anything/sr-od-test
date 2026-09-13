"""经济核合同（kernel 判策第二层：金从哪来、到哪去、什么时候停手）。

被测模块：``kernel/cw_economy.py``（收入链/必花域/XP 链/刷新费/卖退）、
``kernel/cw_investments.py``（投资注册表——登记门归 data 域,此处只锁
经济面消费语义）。

合同面（从源码推导,数值 = 游戏规则换算标定真值,出处 = economy.md §3 与
BWIKI/实机核对记录,置信度分层见源码 docstring）：
- §1 回合收入链:基础收入/连胜金/利息/胜利奖励/败局补偿/聚合;
- §2 卖出退金真值表:cost×3^(star-1),star≥2∧cost≥2 减 1 手续费;
- §3 必花域与息线(金位判定 = 花钱决策的前置门);
- §4 XP 链:点击费用/点击转经验/升级剩余点击/血闸 XP;
- §5 刷新费递增;
- §6 节点目标(NodeGoal)与经济分(economy_score)区分力。
本文件不重复:预算核/排程/断供驱逐(test_cw_economy 预算节)、
阈值链(test_cw_hp_policy)、投资注册表值域(test_cw_data_tables)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import (
    blood_xp_full_clicks,
    clicks_to_next_level,
    in_must_spend_zone,
    interest,
    loss_compensation_base,
    net_income,
    refresh_cost_effective,
    reward_base_gold,
    round_base_income,
    round_start_income,
    sell_refund,
    streak_gold,
    xp_apply_clicks,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwSimFrame

# ============================================================ §1 回合收入链

def test_income_chain_true_values() -> None:
    """收入链标定真值:基础收入按轮号爬坡(封顶);连胜金阶梯;利息每 10 金
    +1 封顶 5(息线 = 10×cap)。"""
    assert round_base_income(1) == 3
    assert round_base_income(2) == 4
    assert round_base_income(3) == 5
    assert round_base_income(5) == 5, '基础收入封顶'
    assert streak_gold(0) == 1 and streak_gold(1) == 1
    assert streak_gold(2) == 2 and streak_gold(4) == 2 and streak_gold(5) == 3
    assert interest(0) == 0 and interest(10) == 1
    assert interest(30) == 3 and interest(50) == 5
    assert interest(60) == 5, '利息封顶(50 金 = 息线)'


def test_net_income_counts_streak_and_loss() -> None:
    """净收入 = 基础 + 连胜分量;败局节点另计补偿(lost_node_type 语义)。"""
    assert net_income(2, 0) == 5
    assert net_income(3, 2) == 7
    assert net_income(2, 0, lost_node_type='battle') >= net_income(2, 0), \
        '败局补偿非负(补偿基 = 平面轮函数)'


def test_reward_and_loss_compensation_by_plane() -> None:
    """胜利奖励/败局补偿基:随位面推进抬升(同轮跨位面对照);同位面内
    boss 节点与普通节点同基(差异在节点自身奖励,不在补偿基)。"""
    p1 = reward_base_gold(1, 5)
    assert reward_base_gold(2, 5) >= p1
    assert loss_compensation_base(1, 3, 'battle') \
        == loss_compensation_base(1, 3, 'boss')


def test_round_start_income_aggregates_components() -> None:
    """回合开始收入聚合:各行分项可加;连胜乘数放大胜利分量;
    利息平推(interest_flat)直接入账。"""
    base = round_start_income(plane=1, round_num=3, node_type='battle',
                              gold=30, streak=2)
    boosted = round_start_income(plane=1, round_num=3, node_type='battle',
                                 gold=30, streak=2, win_reward_mult=1.5)
    flat = round_start_income(plane=1, round_num=3, node_type='battle',
                              gold=30, streak=2, interest_flat=2)
    assert base.total == base.base + base.interest + base.streak
    assert boosted.total >= base.total, '胜利乘数不放低收入'
    assert flat.total == base.total + 2


# ============================================================ §2 卖出退金

def test_sell_refund_true_table() -> None:
    """卖出回金(economy.md §3):1星 = cost 原价;star≥2 = cost×3^(star-1)
    再减合成手续费(star≥2∧cost≥2 才减 1;cost=1 全额退,实机核对
    2★1费=+3)。值 = 游戏规则换算真值,置信度分层见源码 docstring。"""
    assert sell_refund(1, 1) == 1 and sell_refund(1, 2) == 2
    assert sell_refund(2, 1) == 3, 'cost=1 免手续费(实机:万敌出售+3)'
    assert sell_refund(2, 2) == 5, '2★2费 = 6-1'
    assert sell_refund(2, 3) == 8, '2★3费 = 9-1'
    assert sell_refund(3, 5) == 44, '3★5费 = 45-1'
    assert sell_refund(1, 0) == 1, 'cost 0 归 1 下界(max(cost,1))'


# ============================================================ §3 必花域

def test_must_spend_zone_gates_on_interest_line() -> None:
    """必花域(20 号稿 §2.1):gold > 饱和线 g*=10×cap 才 True(线上 = 利息
    已满,囤金无收益);线上取等不触发;买断制(cap≤0)恒 False 出辖。"""
    assert in_must_spend_zone(50, None) is False, 'cap=5 → 线=50,取等不触发'
    assert in_must_spend_zone(51, None) is True
    assert in_must_spend_zone(30, None) is False


# ============================================================ §4 XP 链

def test_xp_apply_clicks_carries_overflow() -> None:
    """XP 点击应用:点击数 × 每击经验;溢出经验作废(不跨级结转)。"""
    level, xp_cur = xp_apply_clicks(4, 0, 1, xp_per_buy=4)
    assert (level, xp_cur) == (4, 4), '未升级,经验累加(4 级门槛 6,一击 4 不够)'
    level0, xp0 = xp_apply_clicks(3, 2, 0, xp_per_buy=4)
    assert (level0, xp0) == (3, 2), '零点击零推进'
    level2, xp_cur2 = xp_apply_clicks(3, 6, 1, xp_per_buy=4)
    assert (level2, xp_cur2) == (5, 0), '连升两支:10 经验过 need(3)=4 升 4、过 need(4)=6 升 5 清零'


def test_blood_xp_full_clicks_scales_with_level() -> None:
    """血闸 XP 满击数随职级抬升(高等级升级更贵 = 血 XP 代价更高)。"""
    assert blood_xp_full_clicks(3) < blood_xp_full_clicks(7)


def test_clicks_to_next_level_uses_container_frame() -> None:
    """升级剩余点击:容器帧直算(等级/XP 现值 → 还需几击)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BS_SCHEMA_VERSION,
        ChannelSig,
        GameState,
        register_sig_actors,
    )
    register_sig_actors('TestSigWriter')
    sig = ChannelSig(family='obs', actor='TestSigWriter', mode='read')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.level, 3, sig=sig)
    bs.observe(bs.xp, (2, 8), sig=sig)
    n = clicks_to_next_level(bs)
    assert n is not None and n >= 1


# ============================================================ §5 刷新费

def test_refresh_cost_passes_through_observed_price() -> None:
    """刷价参数化(ADR-0622):bs 给定 = 现场识别值直通(免费帧不写保证
    非 0);bs 缺席 = CwSimFrame 契约价;再缺 = 建模基价显式缺省
    (原 ``or 2`` falsy 兜底消灭形态,数值恒同语义升级)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BS_SCHEMA_VERSION,
        ChannelSig,
        GameState,
        register_sig_actors,
    )
    register_sig_actors('TestSigWriter')
    sig = ChannelSig(family='obs', actor='TestSigWriter', mode='read')
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.observe(bs.shop_refresh_cost, 4, sig=sig)
    assert refresh_cost_effective(CwSimFrame(), 0, bs=bs) == 4, '现场值直通'
    bs_none = GameState(schema_version=BS_SCHEMA_VERSION)
    assert refresh_cost_effective(CwSimFrame(), 0, bs=bs_none) == 2, \
        '未读 → 建模基价缺省'
    st = CwSimFrame()
    st.shop_refresh_cost = 3
    assert refresh_cost_effective(st, 0) == 3, '帧契约价'


# ============================================================ §6 节点目标

def test_node_goal_returns_domain_object() -> None:
    """节点目标(plane, round → 该节点经济目标):对象域字段齐
    (目标等级/目标金),committed 臂改变目标档(承诺核开 = 目标更高)。"""
    from sr_od.application.currency_war.kernel.cw_economy import get_node_goal
    goal = get_node_goal(1, 3)
    assert goal is not None
    goal_committed = get_node_goal(1, 3, committed=True)
    goal_free = get_node_goal(1, 3, committed=False)
    assert goal_committed is not None and goal_free is not None
