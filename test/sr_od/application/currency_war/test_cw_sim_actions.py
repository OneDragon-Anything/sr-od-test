"""sim 重做 S5(M07/M08/M09 动作应用面 + XP 账本)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md``;锁面 = 动作必经单一转移函数(拒绝
语义在腿内)/免费刷先行记账/真值 cap=10 拒付(LEVEL_CAP 分歧反转)/
节点基础经验表与升级结转/买牌不产经验(M08)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    ShopPayload,
    ShopSlot,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionLevelUpShopParam,
    CwActionRefreshShopParam,
)
from sr_od.application.currency_war.sim.cw_sim_actions import (
    NODE_XP_BY_TYPE,
    apply_node_xp,
    apply_player_action,
    xp_apply_amount,
)
from sr_od.application.currency_war.sim.cw_sim_shop import deal_shop
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng

_OBS = ChannelSig(family='obs', actor='TestSigWriter')


def _prep_gs(gold: int = 20, level: int = 3) -> GameState:
    """最小备战态:金/等级/XP 进度 + 商店一张 3 费牌 + 空席。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, gold, sig=_OBS)
    gs.observe(gs.level, level, sig=_OBS)
    need = XP_TO_NEXT_LEVEL.get(level, 0)   # lv10 分母未定 → 0(U18 口径)
    gs.observe(gs.xp, (0, need), sig=_OBS)
    from sr_od.application.currency_war.kernel.cw_game_state import ShopCard
    payload = ShopPayload(cards=[ShopSlot(kind='content', card=ShopCard(
        name='花火', faction='盛会之星', cost=3, star=1, cost_source='roster',
        slot=1))], refresh_probs={1: 1.0})
    gs.observe(gs.shop, payload, sig=_OBS)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')
                                           for _ in range(9)], capacity=9),
               sig=_OBS)
    return gs


def test_buy_card_routes_through_transfer_function() -> None:
    """买牌 = 单一转移函数应用(扣金/落位/payload 挖洞);买牌不产经验
    (M08 机制口径,旧引擎买牌累加 XP 废弃)。"""
    gs = _prep_gs(gold=20)
    from sr_od.application.currency_war.kernel.cw_game_state import ShopCard
    action = CwActionBuyCardParam(card=ShopCard(name='花火', faction='盛会之星', cost=3,
                                   star=1, cost_source='roster', slot=1))
    outcome = apply_player_action(gs, action, node_tag='p1r2')
    assert outcome is not None and outcome.applied and outcome.bought_count == 1
    assert gs.gold.value == 17, '扣金 3'
    units = [s.unit for s in gs.bench.value.slots if s.unit is not None]
    assert len(units) == 1 and units[0].char_id == '花火'
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[3]), '买牌零经验'


def test_refresh_free_then_paid_bookkeeping() -> None:
    """刷新 = 免费额度先行(实付 0 喂 executed → gold 不写)→ 计数走
    效果账本免费帧闸;额度耗尽 → 基价 2 扣金 + 付费计数(2026-09-18
    迁入裁决:计数住效果账本,上报函数单口)。"""
    gs = _prep_gs(gold=10)
    gs.effects.grant_free_refreshes(1)
    outcome = apply_player_action(gs, CwActionRefreshShopParam(), node_tag='p1r2')
    assert outcome is not None and outcome.applied
    assert gs.gold.value == 10, '免费帧零扣金'
    assert gs.effects.refresh_paid == 0, '免费帧禁进付费计数'
    assert gs.effects.refresh_total == 1
    assert gs.effects.free_refresh_balance == 0
    outcome2 = apply_player_action(gs, CwActionRefreshShopParam(), node_tag='p1r2')
    assert outcome2 is not None and outcome2.applied
    assert gs.gold.value == 8, '第二刷 = 基价 2'
    assert gs.effects.refresh_paid == 1


def test_levelup_refuses_at_true_cap10() -> None:
    """§2.4.2 分歧反转:真值 cap=10,lv10 拒付(旧 sim lv9 冻结删除);
    转移函数满级门单一源。"""
    gs = _prep_gs(gold=100, level=10)
    outcome = apply_player_action(gs, CwActionLevelUpShopParam(cost=4), node_tag='p1r2')
    assert outcome is not None and not outcome.applied
    assert outcome.reason == 'level_cap'
    assert gs.gold.value == 100, '拒付零写'


def test_node_xp_table_and_carry() -> None:
    """M08 节点基础经验:战斗/奖励/遭遇 +2、补给 +0、BOSS +12(U17);
    升级结转同 xp_apply_clicks 规则(3 级门槛 4:两战斗节点攒 4 → 升 4 级)。"""
    assert NODE_XP_BY_TYPE == {'battle': 2, 'reward': 2, 'encounter': 2,
                               'supply': 0, 'boss': 12}
    gs = _prep_gs(level=3)
    assert apply_node_xp(gs, node_type='supply') == 0, '补给 +0'
    assert gs.xp.value == (0, 4)
    assert apply_node_xp(gs, node_type='battle') == 2
    assert gs.xp.value == (2, 4)
    apply_node_xp(gs, node_type='reward')
    assert gs.level.value == 4, '攒满门槛即升级'
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[4]), '溢出结转清零'


def test_xp_apply_amount_generic_and_cap() -> None:
    """通用量版推进(BOSS +12 非击数倍数):3 级 (0/4) +12 → 连跳两级
    余 2;cap10 满级零推进(U18:分母未定不累计)。"""
    assert xp_apply_amount(3, 0, 12) == (5, 2)
    assert xp_apply_amount(10, 0, 12) == (10, 0)
    assert xp_apply_amount(3, 0, 0) == (3, 0)


def test_deal_shop_after_refresh_refills_holes() -> None:
    """刷新重置整店 5 槽(买后留空洞被整店重发覆盖;定长 5 槽语义)。"""
    gs = _prep_gs(gold=50)
    from sr_od.application.currency_war.kernel.cw_game_state import ShopCard
    apply_player_action(gs, CwActionBuyCardParam(card=ShopCard(
        name='花火', faction='盛会之星', cost=3, star=1,
        cost_source='roster', slot=1)), node_tag='p1r2')
    assert gs.shop.value.cards[0].kind == 'empty', '买后留空不紧缩'
    deal_shop(gs, stream_rng(5, 'M05/deal/1/2'), level=1,
              tag='shop:deal:p1r2')
    assert len(gs.shop.value.cards) == 5
    assert all(s.kind == 'content' for s in gs.shop.value.cards), \
        'Lv1 纯 1 费池整店重发(洞被覆盖)'
