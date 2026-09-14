"""CW 商店腾席卖决策点动作语义锁(M3/刷新双通道可达性回归, T-238)。

出处 = mandate_v1/shop.py decide_shop_action 选择序(ADR-0517 §映射:
M4 腾席 → M2 → dominance → C1 → M3 → M6 → EV → R1 → 凑息卖 → 支付
支撑卖 → CloseShop 终结)+ ``_core_seat_vacate`` docstring(腾席支契约:
「卖 1 张即止,下一决策迭代席空,原臂原判据买入」)+ kernel/cw_vocab.py
SellBench docstring(发射点 = shop.py 卖出发射位,逐位带 expect 写入)
+ CloseShop docstring(契约语义 = 「无动作可做」的恒可用终结)。

锁的两件事:
1. 席满+缺员+店内缺员件帧,腾席位发射 SellBench(中间步动作,expect
   = 被卖燃料件)而非 CloseShop——把「有后续意图的中间步」表达成
   「终结」会让商店段提前收口,升级/刷新通道整段窒息(回归病灶:
   六处卖决策点改 ``return CloseShop()`` 后,M3 发射位大量帧不可达,
   sim 实证 levelup_binding=0/刷新 0 次/出口金=校准线 5.1 倍);
2. 腾席卖出真执行(逻辑态直写)后,单动作循环续评恢复买入,并可达
   M3 升级与 R1 刷新发射(通道可达性 = 本修复的验收核心)。

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

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
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
    """腾席卖出真执行后,单动作循环续评恢复买入,M3/刷新双通道可达。

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
    assert 'RefreshShop' in seq, f'R1 刷新发射位不可达: {seq}'
