"""CW 商店腾席卖决策点动作语义锁(M3/刷新双通道可达性回归, T-238)。

出处 = mandate_v1/shop.py decide_shop_action 选择序(ADR-0517 §映射:
M4 腾席 → M2 → dominance → C1 → M3 → M6 → EV → R1 → 凑息卖 → 支付
支撑卖 → CloseShop 终结)+ ``_core_seat_vacate`` docstring(腾席支契约:
「卖 1 张即止,下一决策迭代席空,原臂原判据买入」)+ kernel/cw_vocab.py
SellBench docstring(发射点 = shop.py 卖出发射位,逐位带 expect 写入)
+ CloseShop docstring(契约语义 = 「无动作可做」的恒可用终结)。

锁的三件事:
1. 席满+缺员+店内缺员件帧,腾席位发射 SellBench(中间步动作,expect
   = 被卖燃料件)而非 CloseShop——把「有后续意图的中间步」表达成
   「终结」会让商店段提前收口,升级/刷新通道整段窒息(回归病灶:
   六处卖决策点改 ``return CloseShop()`` 后,M3 发射位大量帧不可达,
   sim 实证 levelup_binding=0/刷新 0 次/出口金=校准线 5.1 倍);
2. 腾席卖出真执行(逻辑态直写)后,单动作循环续评恢复买入,并可达
   M3 升级与 R1 刷新发射(通道可达性 = 本修复的验收核心);
3. **六处店内卖决策点逐一参数化锁**(T-243 追加,防 T-238 病灶任一
   处回退不红):M4 缺员腾席(mandate_v1/shop.py:1319 时点锚,语义位
   为准)/ m2_stockpile 臂①囤腿腾席(:1605)/ C1 未锁线恒买腾席
   (:1844)/ 凑息卖回拉(:2988)/ 支付支撑卖主路径(:3060)/ 支付支撑
   卖兜底③④持有变现(:3081)——各帧首动作 = SellBench 非 CloseShop。

帧构造边界(判据面,断言不依赖):deployed 非空(空板止损守卫
sell_gate.empty_board_sell_blocked 拒卖 = 独立在册语义,本锁不辖)、
bench 燃料件异名(同名同星互为合成素材被 G-S1 守卫拒入燃料集)、
hp 走 observation 源(logic 支 hp 帧被 hp_decision_trusted
fail-closed 拒升级,独立在册语义)、level < arm0_need(可上阵线内件
需求)使 M3 授权臂可用。xp 域 need 槽 = XP_TO_NEXT_LEVEL[等级](写端
xp_apply_clicks 元组不变量,design.md unified-action-factory §2.6)。
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
    ShopActionExecuted,
    ShopCard,
    ShopPayload,
    ShopSlot,
    Unit,
    apply_shop_action_logic,
    board_state_of,
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

register_sig_actors('cw-t238-test')

_LOGIC_SIG = ChannelSig(family='logic_action', actor='cw-t238-test',
                        mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-t238-test',
                      mode='synthesized')

_LEVEL = 3


def _build_session():
    """席满+缺员+店内缺员件+金足的备战帧(构造依据见模块 docstring)。"""
    comp = COMP_LIBRARY[0]
    line = set(comp.core_chars) | set(comp.shared_chars)
    member = comp.core_chars[0]
    # 燃料件 = 非线成员 1★,异名(互不为合成素材,G-S1 不拒入)
    fuels = [n for n in CHARACTERS if n not in line][:9]
    assert len(fuels) == 9

    sess = StrategySession(rng=random.Random('cw-t238'))
    bs = board_state_of(sess)
    bs.write_logic(bs.node, NodeKey(plane=1, round_num=3, kind='prep'),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.write_logic(bs.level, _LEVEL, produced_by='cw-t238-test',
                   sig=_LOGIC_SIG)
    bs.write_logic(bs.xp, (0, XP_TO_NEXT_LEVEL[_LEVEL]),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.write_logic(bs.gold, 60, produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.observe(bs.hp, 60, evidence='cw-t238-test', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=n, star=1, slot=i + 1))
             for i, n in enumerate(fuels)]
    bs.write_logic(bs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    # 上阵 3 名线成员:避开空板止损守卫(deployed 空帧禁卖)且使
    # lv3 板满(deployed==cap)命中 M3 授权臂
    bs.write_logic(bs.front_row,
                   [Unit(char_id=n, star=1, slot=i + 1)
                    for i, n in enumerate(comp.core_chars[1:4])],
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=member, faction='', cost=3,
                                    star=1, slot=1))]
    cards += [ShopSlot(kind='empty')] * 4
    bs.write_logic(bs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    state_of(sess).target_comp = comp
    return MandateV1Live(), sess, SimpleNamespace(ev_arm='full')


# ---- 六处卖决策点参数化锁(T-243 追加;语义位见模块 docstring 第 3 条)----

_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)


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
    """通用最小商店决策帧(bench/上场/店面卡/金/血可参;骨架同
    _build_session)。deployed_units 非空 = 避开空板止损守卫(板空帧
    卖通道独立拒,与本锁断言域无关)。"""
    comp = COMP_LIBRARY[0]
    sess = StrategySession(rng=random.Random('cw-t238'))
    bs = board_state_of(sess)
    bs.write_logic(bs.node, NodeKey(plane=1, round_num=3, kind=node_kind),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.write_logic(bs.level, _LEVEL, produced_by='cw-t238-test',
                   sig=_LOGIC_SIG)
    bs.write_logic(bs.xp, (0, XP_TO_NEXT_LEVEL[_LEVEL]),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.write_logic(bs.gold, gold, produced_by='cw-t238-test',
                   sig=_LOGIC_SIG)
    bs.observe(bs.hp, hp, evidence='cw-t238-test', sig=_OBS_SIG)
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=n, star=1, slot=i + 1))
             for i, n in enumerate(bench_units)]
    bs.write_logic(bs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    bs.write_logic(bs.front_row,
                   [Unit(char_id=n, star=1, slot=i + 1)
                    for i, n in enumerate(deployed_units)],
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    cards = [ShopSlot(kind='content',
                      card=ShopCard(name=n, faction='', cost=c,
                                    star=1, slot=i + 1))
             for i, (n, c) in enumerate(card_names)]
    cards += [ShopSlot(kind='empty')] * (5 - len(cards))
    bs.write_logic(bs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='cw-t238-test', sig=_LOGIC_SIG)
    state_of(sess).target_comp = comp
    return MandateV1Live(), sess, SimpleNamespace(ev_arm='full')


_MEMBER = COMP_LIBRARY[0].core_chars[0]   # 姬子·启行:成员,注册表费 3


def _frame_m4_missing_vacate():
    """1319 M4 缺员腾席:席满+缺员+店有缺员件(既有 _build_session 帧)。"""
    return _build_session()


def _frame_m2_stockpile_vacate():
    """1605 臂①囤腿腾席:成员持有恰 1 张(席满),店刷同员 1★ 第二张
    → 卖 1 燃料腾席,下一迭代由臂①原判据买入。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_MEMBER, 3)], gold=60)


def _frame_core_unlocked_vacate():
    """1845 C1 未锁线恒买腾席:店刷线外 registry_core 名,金可足、席满
    → 恒买腿席满转腾席支卖 1 燃料。"""
    fuels = _fuel_names(8)
    return _frame_session(
        bench_units=[_MEMBER] + fuels,
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:4]),
        card_names=[(_core_out_of_line(), 3)], gold=45)


def _frame_interest_sell():
    """2988 凑息卖回拉:金 47 = g*−3(缺口恰为单燃料退金),席不满、
    缺员件不在店 → 金位触发 + 目标量止盈卖 1 张。上场 1 人 = 板不满
    (arm1 等级驱动 M3 不授权)且非空板(止损守卫不拒卖)。"""
    return _frame_session(
        bench_units=_fuel_names(5),
        deployed_units=list(COMP_LIBRARY[0].core_chars[1:2]),
        card_names=[], gold=47)


def _frame_funding_support_sell():
    """3060 支付支撑卖主路径:金 0 < need(最廉成员费 1)且血线帧
    (凑息禁令弃射让位)、板非空、店无成员卡 → 卖燃料筹资。"""
    return _frame_session(
        bench_units=_fuel_names(8, exclude=(_fuel_names(1)[0],)),
        deployed_units=_fuel_names(1),
        card_names=[], gold=0, hp=10)


def _frame_funding_hold_fallback():
    """3081 支付支撑卖兜底:bench 仅 ③④静态持有 1★ 件(主路径资格空
    ∧ 仍需筹资)→ 兜底池单笔变现,convert_reason=funding_hold_liquidated。"""
    held = [_core_out_of_line()]
    held += [n for n in CORE_SINGLE_CARD_REGISTRY
             if n not in _LINE and n != held[0] and CHARACTERS.get(n)][:1]
    return _frame_session(
        bench_units=held,
        deployed_units=_fuel_names(1, exclude=tuple(held)),
        card_names=[], gold=0, hp=10)


_SITE_FRAMES = {
    'm4_missing_vacate': _frame_m4_missing_vacate,
    'm2_stockpile_vacate': _frame_m2_stockpile_vacate,
    'core_unlocked_vacate': _frame_core_unlocked_vacate,
    'interest_sell': _frame_interest_sell,
    'funding_support_sell': _frame_funding_support_sell,
    'funding_hold_fallback': _frame_funding_hold_fallback,
}


@pytest.mark.parametrize('case', list(_SITE_FRAMES))
def test_all_six_sell_launch_sites_emit_sellbench(case: str):
    """六处店内卖决策点逐一锁:各帧首动作 = SellBench 非 CloseShop。

    T-238 病灶 = 任一处卖决策点把中间步表达成终结,六处只锁一处时
    其余五处回退不红;本参数化逐处给帧构造,任一处回退即响亮红。"""
    strategy, sess, config = _SITE_FRAMES[case]()
    action = strategy.decide_shop_action(sess, config)
    assert type(action).__name__ == 'SellBench', (
        f'{case} 首动作 {type(action).__name__} 非 SellBench'
        '(回退 CloseShop = T-238 病灶形态)')


def test_m4_seat_vacate_emits_sellbench_not_closeshop():
    """腾席位发射 SellBench(中间步动作),不返回 CloseShop(终结动作)。

    锁的语义 = 「席满但有后续买入意图」必须表达为卖出动作(卖出真
    执行腾位,下一决策迭代续评),CloseShop 的契约语义是「无动作可
    做」——错配会把商店段提前收口(T-238 回归病灶)。
    """
    strategy, sess, config = _build_session()
    action = strategy.decide_shop_action(sess, config)
    assert type(action).__name__ == 'SellBench'
    # expect = 提案生成时被卖槽位的期望名(ADR-0317 代际校验写入端
    # 契约:发射位逐位带 expect,''=不校验)
    assert action.expect in CHARACTERS


def test_sellbench_m3_refresh_chain_reachable():
    """腾席卖出真执行后,单动作循环续评恢复买入,M3 通道可达。

    T-245 语义演进(改锁重推记录):旧断言另含「RefreshShop 段内出现
    = R1 发射位可达」——旧语义下该段 R1 帧走必花域全域 yielded 放行
    (账超预算也刷)。账前件恢复后(零产出烧金段修复),本段 R1 帧按
    计划账拦 = 正确决策而非通道窒息(拒因分键可辨);R1 通道活性由
    test_cw_refresh_ledger::TestHorizonClosedYield(末轮豁免发射)与
    TestInBudgetRefresh(域内账内常规发射)承载,本锁不再混锁该通道。

    序列断言写语义不锁巧合:腾席(SellBench)先于买入(BuyCard);
    升级(LevelUpShop)与刷新(RefreshShop)在段内出现 = M3/R1 发射
    位可达。逐动作 apply_shop_action_logic 直写期望态(与生产单动作
    循环同推进语义,bridge.decide_shop_screen 驱动器同路)。
    """
    strategy, sess, config = _build_session()
    bs = board_state_of(sess)
    seq: list[str] = []
    for _ in range(24):   # 防御上界:不收敛 = 响亮红而非挂死
        action = strategy.decide_shop_action(sess, config)
        name = type(action).__name__
        seq.append(name)
        if name == 'CloseShop':
            break
        outcome = apply_shop_action_logic(
            bs, action,
            executed=ShopActionExecuted(bought_count=1, levelup_clicks=1),
            produced_by='cw-t238-test', sig=_LOGIC_SIG)
        if not outcome.applied:
            break
    assert 'SellBench' in seq, f'腾席卖出缺失: {seq}'
    assert 'BuyCard' in seq, f'腾席后买入未恢复: {seq}'
    sell_idx = seq.index('SellBench')
    buy_idx = seq.index('BuyCard')
    assert sell_idx < buy_idx, f'腾席必须先于买入: {seq}'
    assert 'LevelUpShop' in seq, f'M3 升级发射位不可达: {seq}'
    # R1 断言移除(语义演进见 docstring):R1 通道活性由
    # test_cw_refresh_ledger 的末轮豁免/账内常规两发射锁承载。
