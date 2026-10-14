"""CW 商店期动作面锁(迭代 2026-10-12-prep-shop-workflow-redesign 批 3.6)。

2026-09-14 收缩裁定(判例 = screens-actions-capability §5「卖备战/买
经验收缩至备战期」)随 3.6 会话重写**废止**(用户裁定 2026-10-13:旧
代码直接删废弃替换):店内动作面 = **买牌/刷新/关店/卖备战席/购买经验
整批**(shop_session §1 能力面与用户裁定 2026-10-12)。本文件前身 =
test_cw_sell_bench_m3_reach → test_cw_shop_action_face_contraction(收缩
锁),本批改锁重排后的目标形态:

1. 商店域决策形态帧逐一参数化锁:各形态帧首动作 ∈ 扩展闭集
   {买牌, 刷新, 关店, 卖备战席(置换/筹资/变现通道), 购买经验整批};
2. 席满买入 = **店内置换账**(shop_session §3):value(X) > value(Y)
   同口径直比成立 → 首动作卖 Y(reason=shop_swap);「关店→备战卖→
   重开」腾位链废止(不再有关店交回 + wanted 残差置位形态);
3. 席满恒买豁免(C1 支配语义):核心在售即买,腾位按价值让位直接
   发生(c1_make_room 场景卖首位);
4. 筹资形态:缺员 + 金不足 + 活期件在场 → 会话内筹资卖出
   (session_funding),不再关店交回复战;
5. 牌面持久契约锁(承继):节点内卖出腾位 → 买入原在店件,牌面不
   因店内卖出/重开刷新(research/economy.md §2.1)。

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
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
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

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-36-test',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-36-test',
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
    """线外 registry_core 名(C1 恒买夹具;现算防漂移)。"""
    return next(n for n in CORE_SINGLE_CARD_REGISTRY
                if n not in _LINE and CHARACTERS.get(n))


def _frame_session(*, bench_units: list[str], deployed_units: list[str],
                   card_names: list[tuple[str, int]], gold: int,
                   hp: int = 60, node_kind: str = 'prep'):
    """通用最小商店决策帧(bench/上场/店面卡/金/血可参)。deployed_
    units 非空 = 板空帧语义独立(本锁断言域不辖)。金位账面随种子锚定
    (读数协议③稳态;失效行为测试显式置 None)。"""
    comp = COMP_LIBRARY[0]
    sess = StrategySession(rng=random.Random('cw-36'))
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind=node_kind),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.level, _LEVEL, produced_by='cw-36-test',
                   sig=_LOGIC_SIG)
    gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[_LEVEL]),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-36-test',
                   sig=_LOGIC_SIG)
    gs.observe(gs.hp, hp, evidence='cw-36-test', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=n, star=1))
             for i, n in enumerate(bench_units)]
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit(char_id=n, star=1)
                     for i, n in enumerate(deployed_units)], []),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=n, faction='', cost=c,
                                    star=1, slot=i + 1))
             for i, (n, c) in enumerate(card_names)]
    cards += [ShopSlot(kind='empty')] * (5 - len(cards))
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    state_of(sess).target_comp = comp
    st = state_of(sess)
    st.gold_ledger = gold
    st.node_boundary_last_pos = (1, 3)
    live = MandateV1Live(gs, SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    live.state = st   # 状态同源接线:会话播种对象(零参口决策读 self.state)
    return live, sess, SimpleNamespace(ev_arm='full')


# ---- 形态帧(席满置换/恒买腾位/凑息/筹资;3.6 重排后语义)----

def _frame_m4_missing_vacate():
    """M2 缺员遇席满:席满(9 燃料)+缺员(member 不在场)+店有缺员件
    → 置换账:卖首燃料(value(X) 线成员 > value(Y) 燃料,同口径直比
    成立)。"""
    fuels = [n for n in CHARACTERS if n not in _LINE][:9]
    assert len(fuels) == 9
    return _frame_session(
        bench_units=fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60, node_kind='reward')


def _frame_m2_stockpile_vacate():
    """囤腿遇席满:成员持有恰 1 张,店刷同员 1★ 第二张 → 置换账卖燃料。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60, node_kind='reward')


def _frame_core_unlocked_vacate():
    """C1 恒买遇席满:店刷线外 registry_core 名,金可足、席满 → 恒买
    豁免价值比较(c1_make_room 直接卖首位让位候选)。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_core_out_of_line(), 3)], gold=45, node_kind='reward')


def _frame_interest_sell():
    """凑息回拉形态:金贴息线下、席不满、缺员件不在店 → 店内零凑息
    卖射(凑息 = 备战第 7 步接线),收工关店交回备战。"""
    return _frame_session(
        bench_units=_fuel_names(5),
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:2]),
        card_names=[], gold=47)


def _frame_funding_support_sell():
    """筹资形态(主路径):缺员在店 + 金不足 + bench 活期件在场 →
    会话内筹资卖出(session_funding;凑够即买下一帧接手)。"""
    fuels = _fuel_names(8, exclude=(_fuel_names(1)[0],))
    return _frame_session(
        bench_units=fuels,
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


def _frame_funding_hold_fallback():
    """筹资穷尽形态:缺员在店 + 金不足 + bench 空仓(活期/兜底池全
    空)→ 候选与兜底双穷尽 → 记录金不足机会清单收工(shop_session
    §2.3;义务类兜底可卖持有件〔腿①〕的形态由同文件卖出锁辖,本帧
    锁穷尽边界)。"""
    return _frame_session(
        bench_units=[],
        deployed_units=_fuel_names(1),
        card_names=[(_MEMBER, 3)], gold=1, hp=10)


_FORM_FRAMES = {
    'm4_missing_vacate': _frame_m4_missing_vacate,
    'm2_stockpile_vacate': _frame_m2_stockpile_vacate,
    'core_unlocked_vacate': _frame_core_unlocked_vacate,
    'interest_pullback': _frame_interest_sell,
    'funding_support': _frame_funding_support_sell,
    'funding_hold_fallback': _frame_funding_hold_fallback,
}

#: 3.6 重排后的商店域动作面闭集(店内卖备战席与购买经验整批启用,
#: shop_session §1 店内动作边界)。
_SHOP_ACTION_FACE = {'CwActionBuyCardParam', 'CwActionRefreshShopParam',
                     'CwActionCloseShopParam', 'CwActionSellBenchParam',
                     'CwActionLevelUpShopParam'}

#: 席满买入三形态(置换账/恒买腾位/筹资)的首动作 = 店内卖出。
_SELL_FIRST_FORMS = {'m4_missing_vacate', 'm2_stockpile_vacate',
                     'core_unlocked_vacate', 'funding_support'}


@pytest.mark.parametrize('case', list(_FORM_FRAMES))
def test_shop_forms_stay_in_reordered_action_face(case: str):
    """动作面锁(六形态逐一;参数化纪律沿袭):各形态帧首动作 ∈ 扩展
    闭集(买/刷/关/卖备战席/购买经验整批)——2026-09-14 收缩裁定的
    「商店期零卖射零升级射」废止,席满置换/筹资/店内升级为在产形态;
    闭集外类型(部署/卖场上等店内禁做面)发射即红。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    name = type(action).__name__
    assert name in _SHOP_ACTION_FACE, (
        f'{case} 首动作 {name} 越出商店期动作面闭集 '
        f'{sorted(_SHOP_ACTION_FACE)}(店内禁做面 = 卖场上/点消耗品/'
        '拖角色上阵,发射即策略面回退)')


@pytest.mark.parametrize('case', sorted(_SELL_FIRST_FORMS))
def test_bench_blocked_forms_sell_in_shop(case: str):
    """席满/缺金形态的店内卖出锁:置换账(value 比较)与恒买豁免
    (c1_make_room)与筹资(session_funding)首动作 = CwActionSellBenchParam,
    「关店→备战卖→重开」腾位链废止——帧内一步完成,不再产生
    wanted 残差跨段状态(S2 机器退役)。"""
    strategy, sess, config = _FORM_FRAMES[case]()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionSellBenchParam', (
        f'{case} 席满/缺金形态首动作 {type(action).__name__} 非店内卖出'
        '(置换账/筹资/恒买腾位未接产)')
    assert action.reason in ('shop_swap', 'session_funding', 'c1_make_room'), \
        action.reason
    # (原 wanted 残差断言已随 S2 字段族退役删除——批 3.7 死码清理,
    # 会话循环无跨段残差形态。)


def test_vacate_chain_reopen_keeps_shop_face_and_buys():
    """牌面持久契约锁(置换形态;承继 research/economy.md §2.1):同一
    session/同一店面 payload 下:席满帧置换卖出(bench 移除一件,
    店面 payload 不动)→ 下帧重判,原缺员件在店且被买入。牌面若被
    卖出/重开刷新(跨节点语义误用到节点内),缺员件不在店,本锁红。"""
    strategy, sess, config = _frame_m4_missing_vacate()
    act1 = strategy.decide_shop_action()
    assert type(act1).__name__ == 'CwActionSellBenchParam'
    gs = game_state_of(sess)
    # 置换卖出的落地建模:bench 移除被卖槽(逻辑态直写,同容器转移
    # 函数通道);店面 payload 与 gold/缺员语境全不动。
    kept_idx = act1.bench_idx
    slots = list(gs.bench.value.slots)
    slots[kept_idx] = BenchSlot(kind='empty')
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    # 卖出上报(筹资/置换卖出腿的容器投影;回金入账面)
    gs.write_logic(gs.gold, gs.gold.value + (action_income(act1) or 0),
                   produced_by='cw-36-test', sig=_LOGIC_SIG)
    state_of(sess).gold_ledger = gs.gold.value
    act2 = strategy.decide_shop_action()
    assert type(act2).__name__ == 'CwActionBuyCardParam', (
        f'腾位后未恢复买入(得 {type(act2).__name__})= 牌面持久被破坏'
        '或置换链断')
    assert act2.card.name == _MEMBER, (
        f'腾位后买入 {act2.card.name!r} 非原在店缺员件 = 牌面被刷新'
        '(跨节点自动刷新语义误用到节点内)')


def action_income(act) -> int:
    """卖出动作的预期回金(income 记录字段;未标 = 0 保守)。"""
    return int(getattr(act, 'income', 0) or 0)


def test_funding_hold_fallback_records_opportunity():
    """筹资兜底腿②拒形态:核心件持有账 > 0 → 不卖;该牌进未消费机会
    清单(拦因 = 金不足),收工关店(读数协议 §4.2 清单闭环)。"""
    strategy, sess, config = _frame_funding_hold_fallback()
    action = strategy.decide_shop_action()
    assert type(action).__name__ == 'CwActionCloseShopParam'
    st = state_of(sess)
    ct = st.cw4_counters
    assert ct.get('session_funding_exhausted', 0) >= 1, \
        '筹资候选穷尽分键缺席(兜底腿②拒后应记录)'
    recs = st.shop_opportunities
    assert any(r.card_name == _MEMBER and r.blocked_by == 'gold_short'
               for r in recs), \
        f'金不足机会清单记录缺席:实际 {recs}'
