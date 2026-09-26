"""死库存买入防线消费接线 + dominance band 否决分键的店侧单测。

出处与语义单一源:
- ``mandate.dead_stock_pair_buy_reject_reason`` 拒因本体(谓词侧逐 C 值
  真值边界已由 test_cw_buy_dead_stock_pair.py 锁定;本文件锁**消费接线**):
  dominance 臂(zero_overlap 检查后,落地报告 §④ 接线点 1)与
  dead_gold_press_buy 臂 prio2 燃料类(接线点 2)拒成对第二张,计数
  分键 ``dominance_dead_stock_pair_blocked`` / ``press_dead_stock_pair_
  blocked``(判据本体单点,计数归消费位);prio0(缺口)/prio1(持有档)
  = 义务通道豁免不接;
- ``mandate.dominance_buy_eligible`` band 否决(eligible=False)分键
  ``dominance_band_wait``(验收观察:否决此前静默,观测面只剩
  发射频次差;金带外 False = 非必花域常态,不计)。

帧构造边界(判据面,断言不依赖):target_comp 给线(dominance 契约
前提 k_members 非空);燃料名取注册表 TIER_UNRELATED 现算集(阿格莱雅
= 病灶名:sim 实证同名 1★×2 对经 press 臂 R1 形成后,被 G-S1
合成素材守卫永久锁卖锁席)。拒帧的后续臂动作(M6 压库豁免通道等)
不在本文件断言域——closed set 见 mandate.dominance_buy_eligible
docstring 辖域注。
"""

import random
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_UNRELATED,
    line_identity_tier,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
    cap_resolved_of_session,
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    ShopCard,
    ShopPayload,
    ShopSlot,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionBuyCardParam
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-t243-test',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-t243-test',
                      mode='synthesized')

_LEVEL = 3
_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
# 息饱和线 g*(裸 session 恒 = 默认息帽派生,与帧构造无关;10 的倍数)
_G_STAR = saturation_line(cap_resolved_of_session(
    StrategySession(rng=random.Random('cw-t243'))))
# press 帧 gold:g* 之下且死金残段 = 3(g* 恒 10 的倍数 ⇒ −37 尾数恒 3),
# 恰容单张 3 费压库卡
_PRESS_GOLD = _G_STAR - 37
# dominance 帧 gold:溢余带内(_G_STAR 之上)
_DOM_GOLD = _G_STAR + 10


def _fuel_names(count: int) -> list[str]:
    """TIER_UNRELATED 燃料名(非线内 ∧ 两注册表外;注册表现算防漂移)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and line_identity_tier(n) == TIER_UNRELATED]
    assert len(out) >= count, 'TIER_UNRELATED 燃料名不足'
    return out[:count]


def _single_card_session(node_kind: str, gold: int,
                         bench_names: list[str], card_name: str):
    """最小商店决策帧:线 = COMP_LIBRARY[0],bench 全 1★ 燃料,店单张
    1★ 3 费卡(余槽 empty)。

    板空边界:卖臂被 empty_board_sell_blocked 守卫独立兜住,本文件
    断言域(买因/计数键)不消费卖面。"""
    sess = StrategySession(rng=random.Random('cw-t243'))
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind=node_kind),
                   produced_by='cw-t243-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.level, _LEVEL, produced_by='cw-t243-test',
                   sig=_LOGIC_SIG)
    gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[_LEVEL]),
                   produced_by='cw-t243-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-t243-test',
                   sig=_LOGIC_SIG)
    gs.observe(gs.hp, 60, evidence='cw-t243-test', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=n, star=1))
             for i, n in enumerate(bench_names)]
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-t243-test', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=card_name, faction='', cost=3,
                                    star=1, slot=1))]
    cards += [ShopSlot(kind='empty')] * 4
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-t243-test', sig=_LOGIC_SIG)
    state_of(sess).target_comp = COMP_LIBRARY[0]
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso,
    )
    live = MandateV1Live(_gso(sess), SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    live.state = state_of(sess)   # 状态同源接线:会话播种对象(零参口)
    return live, sess, SimpleNamespace(ev_arm='full')


class TestDominanceArmWiring:
    """dominance 臂死库存拒(§④ 接线点 1)+ band 否决分键。"""

    def test_second_copy_rejected_with_key(self):
        """C=1:同名第二张拒买,dominance_dead_stock_pair_blocked 计 1;
        C=0 对照:首张照常发射 dominance_buy,两新键零计数(防误伤面)。

        溢余带帧(gold > g* ∧ bench_free ≥ 2 = 资格门开),店刷 bench
        已持同名 1★ 的第二张——接线点在 zero_overlap 之后,拒后不发射
        dominance_buy(拒后余臂行为属各臂自身辖域,不断言)。"""
        fuels = _fuel_names(2)
        strategy, sess, config = _single_card_session(
            'prep', _DOM_GOLD, fuels, fuels[0])
        action = strategy.decide_shop_action()
        counters = state_of(sess).cw4_counters
        assert counters.get('dominance_dead_stock_pair_blocked') == 1
        assert not (isinstance(action, CwActionBuyCardParam)
                    and action.reason == 'dominance_buy')
        # C=0 对照:首张照常发射(原对照锁迁并)
        fuels0 = _fuel_names(3)
        strategy0, sess0, config0 = _single_card_session(
            'prep', _DOM_GOLD, fuels0[1:], fuels0[0])
        action0 = strategy0.decide_shop_action()
        counters0 = state_of(sess0).cw4_counters
        assert isinstance(action0, CwActionBuyCardParam)
        assert action0.reason == 'dominance_buy'
        assert not counters0.get('dominance_dead_stock_pair_blocked')
        assert not counters0.get('dominance_band_wait')

    def test_band_veto_key_on_seat_band(self):
        """bench_free=1 溢余帧:资格门 False 不再静默,dominance_band_wait 计 1。

        否决带 = gold > g* ∧ bench_free ≤ 1(ADR-0616 命题 4,资格门
        后半合取);金带外(False = 非必花域常态)不计,由 press 组
        对照帧覆盖。"""
        fuels = _fuel_names(8)
        strategy, sess, config = _single_card_session(
            'prep', _DOM_GOLD, fuels, fuels[0])
        action = strategy.decide_shop_action()
        counters = state_of(sess).cw4_counters
        assert counters.get('dominance_band_wait') == 1
        assert not (isinstance(action, CwActionBuyCardParam)
                    and action.reason == 'dominance_buy')


class TestPressArmWiring:
    """dead_gold_press_buy 臂 prio2 燃料类死库存拒(§④ 接线点 2)。"""

    def test_prio2_second_copy_rejected_with_key(self):
        """C=1:燃料类第二张拒买,press_dead_stock_pair_blocked 计 1;
        C=0 对照:燃料类首张照常经 prio2 发射(防误伤面)。

        帧型 = 可辨奖励帧(②(b) 外门三条件:prio0 缺口/prio1 持有档
        均不命中,行进至 prio2 燃料类合取——实机局 s77091 R1 形成路径
        同构);拒后不发射 dead_gold_press_buy。"""
        fuels = _fuel_names(2)
        strategy, sess, config = _single_card_session(
            'reward', _PRESS_GOLD, fuels, fuels[0])
        action = strategy.decide_shop_action()
        counters = state_of(sess).cw4_counters
        assert counters.get('press_dead_stock_pair_blocked') == 1
        # 金带外(gold < g*)band 否决键零计数:否则键只辖溢余带帧
        assert not counters.get('dominance_band_wait')
        assert not (isinstance(action, CwActionBuyCardParam)
                    and action.reason == 'dead_gold_press_buy')
        # C=0 对照:首张照常经 prio2 发射(原对照锁迁并)
        fuels0 = _fuel_names(3)
        strategy0, sess0, config0 = _single_card_session(
            'reward', _PRESS_GOLD, fuels0[1:], fuels0[0])
        action0 = strategy0.decide_shop_action()
        counters0 = state_of(sess0).cw4_counters
        assert isinstance(action0, CwActionBuyCardParam)
        assert action0.reason == 'dead_gold_press_buy'
        assert counters0.get('dead_gold_press_buy_hit') == 1
        assert not counters0.get('press_dead_stock_pair_blocked')
