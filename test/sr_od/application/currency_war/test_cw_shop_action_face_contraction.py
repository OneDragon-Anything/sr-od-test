"""CW 商店期动作面收缩锁(判例 = screens-actions-capability §5)。

判例:商店期动作面 = **买牌/刷新/关店**——卖备战(CwActionSellBenchParam)与买经验
(CwActionLevelUpParam/CwActionLevelUpShopParam)收缩至备战期决策(策略归属 = strategy-docs
22/23 号篇);腾位/筹资/凑息动机的「先卖后做」由跨段状态 substrate
承载(``shop.decide_shop_action`` 尾声明),框架侧不做动机判断。

本文件前身 = test_cw_sell_bench_m3_reach.py(六处店内卖
决策点发射 CwActionSellBenchParam 锁 + M3 发射位可达锁)——该发射面随收缩退役,
违例形态锁不保留,本文件改锁收缩后的目标形态:

1. 商店域决策形态帧逐一参数化锁(原六处卖射位的席位/缺金形态全保):
   首动作 ∈ {CwActionBuyCardParam, CwActionRefreshShopParam, CwActionCloseShopParam},恒不发射 CwActionSellBenchParam/
   CwActionLevelUpShopParam(任一处发射面复活即红);
2. 席满缺员帧 = 关店交回 + 义务残差状态在(bench_full_buy_abandon 计数
   + ``cw4_shop_wanted_pending`` 置位)——「交回+状态在」锁到框架
   边界;备战期消费臂(wanted_closure_emit)评估腾席/重开归策略侧;
   筹资形态的 funding_close_defer 分键计数随本锁同承(原筹资专锁并入);
3. 腾位链牌面持久契约锁:节点内关店→重开不刷新牌面
   (research/economy.md §2.1)——同 session 同店面 payload,关店
   交回 → 备战腾席(bench 移除一件)→ 重开重判,原缺员件在店且被
   买入(腾位/筹资/凑息往返不损失已刷牌面)。

帧构造边界(判据面,断言不依赖):deployed 非空(空板帧语义独立,
本锁不辖)、bench 燃料件异名(同名同星互为合成素材被 G-S1 守卫拒入
燃料集)、hp 走 observation 源、xp 域 need 槽 = XP_TO_NEXT_LEVEL[等级]
(写端 xp_apply_clicks 元组不变量)。
"""

import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_card_identity import (
    CORE_SINGLE_CARD_REGISTRY,
    TIER_UNRELATED,
    line_identity_tier,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_economy import XP_TO_NEXT_LEVEL
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
    register_sig_actors,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

register_sig_actors('cw-t271-test')

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-t271-test',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-t271-test',
                      mode='synthesized')

_LEVEL = 3

_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
_MEMBER = COMP_LIBRARY[0].core_chars[0]   # 线成员(注册表费 3)


def _fuel_names(count: int, exclude: tuple[str, ...] = ()) -> list[str]:
    """TIER_UNRELATED 燃料名(非线内 ∧ 两注册表外;注册表现算防漂移)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and n not in exclude
           and line_identity_tier(n) == TIER_UNRELATED]
    assert len(out) >= count, 'TIER_UNRELATED 燃料名不足'
    return out[:count]


def _core_out_of_line() -> str:
    """线外 registry_core 名(C1 恒买/③④静态持有件夹具;现算防漂移)。"""
    return next(n for n in CORE_SINGLE_CARD_REGISTRY
                if n not in _LINE and CHARACTERS.get(n))


def _frame_session(*, bench_units: list[str], deployed_units: list[str],
                   card_names: list[tuple[str, int]], gold: int,
                   hp: int = 60, node_kind: str = 'prep'):
    """通用最小商店决策帧(bench/上场/店面卡/金/血可参)。deployed_
    units 非空 = 板空帧语义独立(本锁断言域不辖)。"""
    comp = COMP_LIBRARY[0]
    sess = StrategySession(rng=random.Random('cw-t271'))
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind=node_kind),
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.level, _LEVEL, produced_by='cw-t271-test',
                   sig=_LOGIC_SIG)
    gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[_LEVEL]),
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-t271-test',
                   sig=_LOGIC_SIG)
    gs.observe(gs.hp, hp, evidence='cw-t271-test', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=n, star=1, slot=i + 1))
             for i, n in enumerate(bench_units)]
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.front_row,
                   [Unit(char_id=n, star=1, slot=i + 1)
                    for i, n in enumerate(deployed_units)],
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=n, faction='', cost=c,
                                    star=1, slot=i + 1))
             for i, (n, c) in enumerate(card_names)]
    cards += [ShopSlot(kind='empty')] * (5 - len(cards))
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    state_of(sess).target_comp = comp
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of as _gso,
    )
    live = MandateV1Live(_gso(sess), SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    live.state = state_of(sess)   # 状态同源接线:会话播种对象(零参口决策读 self.state)
    return live, sess, SimpleNamespace(ev_arm='full')


# ---- 原六处卖射位的席位/缺金形态帧(发射面退役,形态保留供收缩锁)----

def _frame_m4_missing_vacate():
    """M2 缺员遇席满:席满(9 燃料)+缺员(member 不在场)+店有缺员件
    → 关店交回(腾位链第一步)。"""
    fuels = [n for n in CHARACTERS if n not in _LINE][:9]
    assert len(fuels) == 9
    return _frame_session(
        bench_units=fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60)


def _frame_m2_stockpile_vacate():
    """囤腿遇席满:成员持有恰 1 张,店刷同员 1★ 第二张 → 关店交回。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60)


def _frame_core_unlocked_vacate():
    """C1 恒买遇席满:店刷线外 registry_core 名,金可足、席满 → 关店交回。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_core_out_of_line(), 3)], gold=45)


def _frame_interest_sell():
    """凑息回拉形态:金贴息线下、席不满、缺员件不在店 → 零卖射,收工
    关店交回备战(金位回拉归备战期 ②(a) 接线)。"""
    return _frame_session(
        bench_units=_fuel_names(5),
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:2]),
        card_names=[], gold=47)


def _frame_funding_support_sell():
    """筹资形态(主路径):缺员+金不足最廉可买形态 → 关店交回备战筹资。"""
    return _frame_session(
        bench_units=_fuel_names(8, exclude=(_fuel_names(1)[0],)),
        deployed_units=_fuel_names(1),
        card_names=[], gold=0, hp=10)


def _frame_funding_hold_fallback():
    """筹资形态(③④持有件在场):缺员+金不足 → 同一关店交回形态。"""
    held = [_core_out_of_line()]
    held += [n for n in CORE_SINGLE_CARD_REGISTRY
             if n not in _LINE and n != held[0] and CHARACTERS.get(n)][:1]
    return _frame_session(
        bench_units=held,
        deployed_units=_fuel_names(1, exclude=tuple(held)),
        card_names=[], gold=0, hp=10)


_FORM_FRAMES = {
    'm4_missing_vacate': _frame_m4_missing_vacate,
    'm2_stockpile_vacate': _frame_m2_stockpile_vacate,
    'core_unlocked_vacate': _frame_core_unlocked_vacate,
    'interest_pullback': _frame_interest_sell,
    'funding_support': _frame_funding_support_sell,
    'funding_hold_fallback': _frame_funding_hold_fallback,
}

_SHOP_ACTION_FACE = {'CwActionBuyCardParam', 'CwActionRefreshShopParam', 'CwActionCloseShopParam'}


@pytest.mark.parametrize('case', list(_FORM_FRAMES))
def test_shop_forms_stay_in_contracted_action_face(case: str):
    """收缩锁(六形态逐一;参数化纪律沿袭):各形态帧首动作 ∈
    买牌/刷新/关店闭集,恒不发射 CwActionSellBenchParam/CwActionLevelUpShopParam——任一处卖射/
    升级射复活(策略面回退)即响亮红。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    name = type(action).__name__
    assert name in _SHOP_ACTION_FACE, (
        f'{case} 首动作 {name} 越出商店期动作面闭集 '
        f'{sorted(_SHOP_ACTION_FACE)}(CwActionSellBenchParam/CwActionLevelUpShopParam 已收缩至'
        '备战期,复活 = 商店收缩回退)')


def test_bench_full_close_hands_back_with_defer_state():
    """腾位形态流锁(交回+状态在):席满缺员帧 = CwActionCloseShopParam 交回 +
    义务残差跨段状态置位(wanted_pending)——备战期消费臂评估腾席/
    重开归策略侧,框架只锁「交回发生且状态在」。筹资形态计数腿(并入,
    原筹资专锁):缺员+金不足 = CwActionCloseShopParam 交回备战筹资
    (funding_close_defer 分键),零卖射。"""
    strategy, sess, config = _frame_m4_missing_vacate()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionCloseShopParam'
    st = state_of(sess)
    assert st.cw4_shop_wanted_pending is not None, \
        '关店交回但 wanted 残差缺席 = 备战侧消费臂失去闭环输入'
    ct = st.cw4_counters
    assert ct.get('bench_full_buy_abandon', 0) == 1
    # 筹资形态计数腿(并入):同形关店交回,分键计数归属正确
    strategy_f, sess_f, config_f = _frame_funding_support_sell()
    action_f = strategy_f.decide_shop_action()
    assert type(action_f).__name__ == 'CwActionCloseShopParam'
    assert state_of(sess_f).cw4_counters.get('funding_close_defer', 0) == 1, (
        '筹资形态关店交回,分键 = funding_close_defer(零卖射)')


def test_vacate_chain_reopen_keeps_shop_face_and_buys():
    """腾位链牌面持久契约锁:节点内关店→重开不刷新牌面
    (research/economy.md §2.1)——同一 session/同一店面 payload 下:
    席满帧关店交回 → 备战腾席(bench 移除一件,店面 payload 不动)
    → 重开重判,原缺员件在店且被买入。牌面若被重开刷新(跨节点语义
    误用到节点内),缺员件不在店,本锁红。"""
    strategy, sess, config = _frame_m4_missing_vacate()
    act1 = strategy.decide_shop_action()
    assert type(act1).__name__ == 'CwActionCloseShopParam'
    gs = game_state_of(sess)
    # 备战期腾席:bench 移除一件燃料(逻辑态直写,同容器转移函数通道);
    # 店面 payload 与 gold/缺员语境全不动 = 「节点内重开」的决策级建模。
    fuels = [b for b in gs.bench.value.slots
             if b is not None and b.unit is not None
             and (b.unit.char_id or '') != _MEMBER]
    kept = fuels[0]
    rest = [s for s in gs.bench.value.slots if s is not kept]
    gs.write_logic(gs.bench, BenchView(slots=rest, capacity=9),
                   produced_by='cw-t271-test', sig=_LOGIC_SIG)
    act2 = strategy.decide_shop_action()
    assert type(act2).__name__ == 'CwActionBuyCardParam', (
        f'重开后未恢复买入(得 {type(act2).__name__})= 牌面持久被破坏'
        '或腾位链断')
    assert act2.card.name == _MEMBER, (
        f'重开买入 {act2.card.name!r} 非原在店缺员件 = 牌面被刷新'
        '(跨节点自动刷新语义误用到节点内)')

# (收口整删)原 test_funding_form_closes_with_defer_counter「筹资形态
# 专锁」删:funding_close_defer 分键计数腿并入上方腾位形态流锁(同形
# 关店交回,分键归属面由同锁分腿承重)。
