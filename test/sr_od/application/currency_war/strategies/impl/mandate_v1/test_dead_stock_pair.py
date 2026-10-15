"""死库存对(G-S1)防线行为测试:买入拒真值表 / 消费接线与分键 / 退出
通道与获取账。三段同机制归并(原三文件按机制并入,判据规格出处 =
三合取 + 遥测三键族;数学论证 = proofs P96 帧级支配 + N=3 载体寿命):

1. **买入拒真值表**(语义单一源 = ``mandate.
   dead_stock_pair_buy_reject_reason``,方向② G-S1 买侧对偶:非定向
   1★ 买入禁制造同名 1★×2 死库存对,拒因键 ``dead_stock_pair``)+
   dominance_buy 席位外部性否决带(ADR-0616 命题 4,bench_free ≤ 1
   fail-closed,≥ 2 零干涉)。校验资格谓词真值边界,不断言分布数值。
2. **消费接线**(拒因本体谓词侧由本文件段 1 锁定;本段校验**消费接线**):
   dominance 臂(zero_overlap 后,落地报告接线点 1)与 dead_gold_press_
   buy 臂 prio2 燃料类(接线点 2)拒成对第二张,计数分键
   ``dominance_dead_stock_pair_blocked`` / ``press_dead_stock_pair_
   blocked``;prio0(缺口)/prio1(持有档)= 义务通道豁免不接;band 否决
   分键 ``dominance_band_wait``(否决此前静默)。帧构造边界:target_
   comp 给线;燃料名取注册表 TIER_UNRELATED 现算集(阿格莱雅 = 病灶
   名:sim 实证同名 1★×2 对经 press 臂 R1 形成后被 G-S1 合成素材守卫
   永久锁卖锁席)。
3. **退出通道行为测试**(判据⑤;载体 = ``sell_gate.
   dead_pair_exit_release`` 单点函数 + 持久获取账 ``register_
   acquisition``,写端 = shop._emit_buy 发射位):行为测试①-⑤ + N1/N4
   收编面(N3 = 注释级同参钉死,消费位同参传参由测试①装配路径覆盖;
   N2 kept_young 分键由测试②辖)。帧构造边界:素材名取注册表
   TIER_UNRELATED 现算集(与段 2 同款防漂移);测试①②③④ 走备战域
   ``run_mandate`` M4 腾席臂(设计 flagship 场景 = 死锁帧腾席),判据
   单元直调 ``dead_pair_exit_release``;黑板 node 必写(位面/轮轴 =
   判据 (c) 读源,缺写 = fail-closed 保留 = 释放恒不可达)。
"""
import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_UNRELATED,
    line_identity_tier,
    transition_release_names,
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionBuyCardParam
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    sell_gate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    MandateFrame,
    run_mandate,
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
_ROUND = 5
_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
# 息饱和线 g*(裸 session 恒 = 默认息帽派生,与帧构造无关;10 的倍数)
_G_STAR = saturation_line(cap_resolved_of_session(
    StrategySession(rng=random.Random('cw-t243'))))
# press 帧 gold:g* 之下且死金残段 = 3(g* 恒 10 的倍数 ⇒ −37 尾数恒 3),
# 恰容单张 3 费压库卡
_PRESS_GOLD = _G_STAR - 37
# dominance 帧 gold:溢余带内(_G_STAR 之上)
_DOM_GOLD = _G_STAR + 10

# TIER_UNRELATED 非线内名(注册表现算防漂移):[0] = 素材对名,[1] = 垫件,
# [2] = 商店买卡名(写端测试三名互异;排除④放行档转线名)。
_FUELS = [n for n in sorted(CHARACTERS)
          if n not in _LINE and n not in transition_release_names()
          and line_identity_tier(n) == TIER_UNRELATED]
assert len(_FUELS) >= 3, 'TIER_UNRELATED 燃料名不足'
_PAIR = _FUELS[0]
_FILLER = _FUELS[1]


def _bench_char(char_id: str, star: int = 1, slot: int = 1) -> BenchSlot:
    """构造最小 bench 占席条目(容器形状;仅 char_id/star 参与判据;
    slot = 备战栏 1-based 物理槽,判据不消费)。"""
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=star))


def _fuel_names(count: int) -> list[str]:
    """TIER_UNRELATED 燃料名(非线内 ∧ 两注册表外;注册表现算防漂移)。"""
    out = [n for n in CHARACTERS
           if n not in _LINE and line_identity_tier(n) == TIER_UNRELATED]
    assert len(out) >= count, 'TIER_UNRELATED 燃料名不足'
    return out[:count]


def _transition_pair_name() -> str:
    """④ 放行档名(测试③;非线内,身份段静态持有集成员)。"""
    out = sorted(n for n in transition_release_names() if n not in _LINE)
    assert out, '④ 放行档非线内名不足'
    return out[0]


# ============================================================
# 段 1:买入拒真值表 + dominance 席位外部性否决带(资格谓词侧)
# ============================================================


class TestDeadStockPairBuyReject:
    """死库存买入防线:拒因键真值边界(逐 C 值一格,合并真值表)。"""

    def test_reject_reason_truth_table(self):
        """拒因真值表(七格并一):C=0 首张放行(买入后 C=1,单张全额
        可退零锁席);C=1 第二张拒(拒因键 dead_stock_pair,买入后成 ×2
        死对);C=2 第三张买入即满 3 自动合成 2★(消对)放行禁误伤;
        线内名(义务基座成员)同名对 = 合法合成素材任意 C 放行;辖星
        = 1,2★ 直出不成对恒放行;计数域 = bench∪deployed(deployed 域
        同名 1★ 同样构成 C=1);空名(装备/纯标签件无同名语义)放行
        防误伤。"""
        # C=0 首张放行
        bench = [_bench_char('阿格莱雅')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '缇宝', 1, bench, [], ()) == ''
        # C=1 第二张拒
        bench1 = [_bench_char('阿格莱雅'), _bench_char('缇宝')]
        deployed1 = [Unit(char_id='青雀', star=2)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, bench1, deployed1, ()) == 'dead_stock_pair'
        # C=2 第三张(合成消对)放行
        bench2 = [_bench_char('阿格莱雅'), _bench_char('阿格莱雅')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, bench2, [], ()) == ''
        # 线内名对放行
        k = ('停云',)
        bench_line = [_bench_char('停云')]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '停云', 1, bench_line, [], k) == ''
        # 2★ 恒放行
        bench_star2 = [_bench_char('阿格莱雅', star=2)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 2, bench_star2, [], ()) == ''
        # deployed 域计数
        deployed = [Unit(char_id='阿格莱雅', star=1)]
        assert mandate.dead_stock_pair_buy_reject_reason(
            '阿格莱雅', 1, [], deployed, ()) == 'dead_stock_pair'
        # 空名放行
        assert mandate.dead_stock_pair_buy_reject_reason(
            '', 1, [_bench_char('阿格莱雅')], [], ()) == ''


class TestDominanceBuyEligibleSeatBand:
    """ADR-0616 命题 4:dominance_buy 席位外部性否决带边界。

    支配论证锚(ADR-0611 换锚重写,mandate.dominance_buy_eligible
    docstring):1★ 全额退净成本 0 的金维支配性与 g*=10×cap_resolved
    参数化金位门不变,本组只校验席位维带界。
    """

    def test_seat_band_truth_table(self):
        """席位带真值表(四格并一):金 ≤ g* 恒不可发射(金维门原样,
        与席位维无关);V_slot>0 带(bench_free=1)fail-closed 否决;
        bench_free=0 原物理门语义保留(否决带含边界);bench_free ≥ 2
        域 P41② 支配论证原样有效零干涉(集成测试留接线段)。"""
        assert mandate.dominance_buy_eligible(30, 5, cap_resolved=4) is False
        assert mandate.dominance_buy_eligible(80, 1, cap_resolved=4) is False
        assert mandate.dominance_buy_eligible(80, 0, cap_resolved=4) is False

    @pytest.mark.parametrize('bench_free', [2])
    def test_bench_free_two_plus_untouched(self, bench_free: int):
        """bench_free ≥ 2 域:P41② 支配论证原样有效,零干涉(参数化
        收敛为带界代表值;带宽语义由谓词本体与集成测试承压)。"""
        assert mandate.dominance_buy_eligible(
            80, bench_free, cap_resolved=4) is True


# ============================================================
# 段 2:消费接线 + 否决分键(店侧)
# ============================================================


def _single_card_session(node_kind: str, gold: int,
                         bench_names: list[str], card_name: str):
    """最小商店决策帧:线 = COMP_LIBRARY[0],bench 全 1★ 燃料,店单张
    1★ 3 费卡(余槽 empty)。

    板空边界:卖臂被 empty_board_sell_blocked 守卫独立兜住,本段
    断言域(买因/计数键)不消费卖面。"""
    sess = StrategySession(rng=random.Random('cw-t243'))
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind=(
        'reward' if node_kind == 'prep' else node_kind)),   # 3.6:奖励帧抑制会话内升级
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
    live = MandateV1Live(game_state_of(sess), SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    live.state = state_of(sess)   # 状态同源接线:会话播种对象(零参口)
    return live, sess, SimpleNamespace(ev_arm='full')


class TestDominanceArmWiring:
    """dominance 臂死库存拒(接线点 1)+ band 否决分键。"""

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
        # C=0 对照:首张照常发射(原对照测试迁并)
        fuels0 = _fuel_names(3)
        strategy0, sess0, config0 = _single_card_session(
            'prep', _DOM_GOLD, fuels0[1:], fuels0[0])
        action0 = strategy0.decide_shop_action()
        counters0 = state_of(sess0).cw4_counters
        assert isinstance(action0, CwActionBuyCardParam)
        # 3.6 位次申报:同一首张燃料件可经序 4 垫件补位支(溢余帧第二
        # 触发域)先行发射——买面行为不变,臂身份按新序可交换。
        assert action0.reason in ('dominance_buy', 'fuel_filler_stall')
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
    """dead_gold_press_buy 臂 prio2 燃料类死库存拒(接线点 2)。"""

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
        # C=0 对照:首张照常经 prio2 发射(原对照测试迁并)
        fuels0 = _fuel_names(3)
        strategy0, sess0, config0 = _single_card_session(
            'reward', _PRESS_GOLD, fuels0[1:], fuels0[0])
        action0 = strategy0.decide_shop_action()
        counters0 = state_of(sess0).cw4_counters
        assert isinstance(action0, CwActionBuyCardParam)
        assert action0.reason == 'dead_gold_press_buy'
        assert counters0.get('dead_gold_press_buy_hit') == 1
        assert not counters0.get('press_dead_stock_pair_blocked')


# ============================================================
# 段 3:退出通道行为测试(判据⑤;测试①-⑤ + 写端 + 判据单元)
# ============================================================


def _prep_frame(*, pair_ledger_round: int | None,
                pair: str = _PAIR,
                k_members: tuple[str, ...] = tuple(sorted(_LINE)),
                gold: int = 200) -> tuple[StrategySession, object,
                                          MandateFrame]:
    """死锁备战帧:bench 满(2× 1★ 对成员 + 7× 2★ 垫件),上阵 1 人
    (免空板守卫),线缺员(bench 无线内名),黑板 node 位面 1 轮 5;
    ``pair_ledger_round`` 非 None 时预登记获取账(同位面)。垫件 2★ 出
    燃料资格 ⇒ 对成员是唯一 1★ 候选,卖出对象确定。"""
    sess = StrategySession()
    gs = game_state_of(sess)
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND, kind='reward'),   # 3.6:奖励帧抑制会话内升级(翻转行为差隔离——本测试辖买面登记)
                   produced_by='cw-t253-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-t253-test', sig=_LOGIC_SIG)
    # P4 容器形种子:bench = 占席条目(BenchSlot,槽序),deployed = 行域 Unit
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id=pair, star=1)),
             BenchSlot(kind='unit',
                       unit=Unit(char_id=pair, star=1))]
    slots += [BenchSlot(kind='unit',
                        unit=Unit(char_id=_FILLER, star=2))
              for i in range(3, 10)]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                   produced_by='cw-t253-test', sig=_LOGIC_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit(char_id='刃', star=1)], []),
                   produced_by='cw-t253-test', sig=_LOGIC_SIG)
    if pair_ledger_round is not None:
        assert sell_gate.register_acquisition(
            sess, pair, plane=1, round_num=pair_ledger_round, star=1)
    frame = MandateFrame(
        gold=gold, level=7, bench=[s for s in slots
                                   if s.kind != 'empty'],
        deployed=[Unit(char_id='刃', star=1)],
        deploy_cap=7, node_type='battle', stop_flag=False,
        k_members=k_members, round_num=_ROUND)
    return sess, gs, frame


def _sell_actions(out: list) -> list:
    return [e for e in out if type(e.action).__name__ == 'CwActionSellBenchParam']


class TestLock1DeadlockDominance:

    def test_aged_pair_member_sold_to_free_seat(self):
        """行为测试①(2.1.3 死锁帧支配语义):非重买集素材对(账龄 ≥N)+
        缺口件死锁帧 → M4 卖对成员腾席。

        校验 2.1.3:B 弱支配 A(帧内持有收益 0 成本 V_slot>0);卖出腿 =
        m4_fuel_sell,释放/卖出两键显影,腾出席位不再耗竭。释放集单点
        函数直读:对成员入集(判据 (a)(b)(c) 合取正例),kept 面零计数。"""
        sess, gs, frame = _prep_frame(pair_ledger_round=2)
        out = run_mandate(frame, sess, state=gs)
        sells = _sell_actions(out)
        assert len(sells) == 1 and sells[0].action.bench_idx == 0, \
            f'释放对成员未被腾席臂卖出: {out!r}'
        ct = state_of(sess).cw4_counters
        assert ct.get('dead_pair_exit_released') == 1
        assert ct.get('dead_pair_exit_sold_m4_fuel') == 1
        assert not ct.get('m2_retry_exhausted')
        # 释放集单点直读(原单点测试迁并)
        release = sell_gate.dead_pair_exit_release(
            sess, frame.k_members, frame.bench, frame.deployed, _ROUND,
            counters=state_of(sess).cw4_counters)
        assert release == frozenset({_PAIR})
        assert not any(k.startswith('dead_pair_exit_guard_kept')
                       for k in ct)


class TestLock2AgeLowerBound:

    def test_young_and_fresh_pair_kept_and_guard_counts(self):
        """行为测试②:N 下界(账龄 <N 不卖)两格(锁 N 下界 + ADR-0558
        案发回归形态):账龄 1 < N=3 的同构死锁帧 → 不卖(守卫照常拒入
        并按既有键计数);新购对(获取账登记轮 == 当前轮,age 0)被燃料
        臂立即触达 → 守卫照常拒、零卖出(原案不复活;新购 ⇒ 当轮窗/
        获取账合取保持)。"""
        # 账龄 1 < N
        sess, gs, frame = _prep_frame(pair_ledger_round=4)
        out = run_mandate(frame, sess, state=gs)
        assert not _sell_actions(out)
        ct = state_of(sess).cw4_counters
        # N2 拆分:真窗内保留走 kept_young(非 kept_no_entry)
        assert ct.get('dead_pair_exit_guard_kept_young') == 1
        assert ct.get('merge_material_guard_blocked') == 1
        assert not ct.get('dead_pair_exit_released')
        assert ct.get('m2_retry_exhausted') == 1
        # 新购对 age 0 立即触达仍拒
        sess2, bs2, frame2 = _prep_frame(pair_ledger_round=_ROUND)
        out2 = run_mandate(frame2, sess2, state=bs2)
        assert not _sell_actions(out2)
        ct2 = state_of(sess2).cw4_counters
        assert ct2.get('merge_material_guard_blocked') == 1
        assert ct2.get('dead_pair_exit_guard_kept_young') == 1
        assert not ct2.get('dead_pair_exit_released')


class TestLock3IdentityAuthority:

    def test_transition_pair_released_but_not_sold(self):
        """行为测试③:身份段权威(③④ 名义对入释放集仍不卖;旁路先、
        装配后):④ 名义素材对:过 (a)(b)(c) 入释放集(released 计 1),
        身份段在下游装配排除 → 零卖出(序列断言:旁路在子谓词内先行,
        装配 A 照旧收口)。腾席面空集 → 诚实停摆计数。"""
        tname = _transition_pair_name()
        sess, gs, frame = _prep_frame(pair=tname, pair_ledger_round=2)
        out = run_mandate(frame, sess, state=gs)
        assert not _sell_actions(out)
        ct = state_of(sess).cw4_counters
        assert ct.get('dead_pair_exit_released') == 1
        assert ct.get('dead_pair_exit_guard_kept_identity') == 1
        assert ct.get('m2_retry_exhausted') == 1


class TestLock5LedgerLifecycleDecoupling:

    def test_entry_survives_all_four_registry_exits(self):
        """行为测试⑤:获取账与发射登记簿四出口生命周期解耦——发射登记簿
        四出口销账(轮界/合成/部署/换线)后获取账条目仍在(校验退出判据
        读源修法本体:与易失登记簿生命周期解耦)。"""
        sess = StrategySession()
        name = _PAIR
        assert sell_gate.register_launch(
            sess, name, cause='press', round_num=_ROUND)
        assert sell_gate.register_acquisition(
            sess, name, plane=1, round_num=_ROUND, star=1)
        # 出口②′ 合成销
        assert sell_gate.consume_on_merge(sess, name) == 1
        # 出口② 部署销(先重开账再销,保持「登记簿有账」前提;press 类
        # 无资格断言,hold 类须静态持有集成员故不适用)
        assert sell_gate.register_launch(
            sess, name, cause='press', round_num=_ROUND)
        assert sell_gate.prune_on_deploy(sess, [name]) == 1
        # 换线闭合销:义务类登记出基座,经装配 A 读点触发
        assert sell_gate.register_launch(
            sess, name, cause='obligation', round_num=_ROUND)
        sell_gate.sell_exclusions(sess, ('线外名',), channel='interest')
        # 出口③ 轮界销(再开账后由 active_window 读端就地过期)
        assert sell_gate.register_launch(
            sess, name, cause='press', round_num=_ROUND)
        sell_gate.active_window(sess, _ROUND + 1)
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert ledger.get(name) == (1, _ROUND), \
            f'获取账条目被发射登记簿出口连带销账: {ledger!r}'

    def test_ledger_own_closures(self):
        """获取账自身闭合(位面):跨位面条目在下一读点清除、判据
        fail-closed 不出集(r2 测试面缺口半边:自身闭合行为钉住)。"""
        sess = StrategySession()
        assert sell_gate.register_acquisition(
            sess, _PAIR, plane=1, round_num=_ROUND, star=1)
        bs2 = game_state_of(sess)
        bs2.write_logic(bs2.node, NodeKey(plane=2, round_num=_ROUND + 1,
                                          kind='prep'),
                        produced_by='cw-t253-test', sig=_LOGIC_SIG)
        release = sell_gate.dead_pair_exit_release(sess, (), [], [],
                                                   _ROUND + 1)
        assert release == frozenset()
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert _PAIR not in ledger, '跨位面条目未被位面闭合清除'


class TestWriteEnd:

    def test_shop_buy_writes_ledger(self):
        """写端:任一臂买入(经发射位)后获取账含该名 =(位面, 买入轮)
        ——全因类写端活路径证据(dominance 臂 C=0 首张买入)。"""
        sess = StrategySession(rng=random.Random('cw-t253'))
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),   # 3.6:奖励帧抑制会话内升级(本测试辖买面登记)
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        gs.write_logic(gs.level, 3, produced_by='cw-t253-test',
                       sig=_LOGIC_SIG)
        gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[3]),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        gs.write_logic(gs.gold, _G_STAR + 10,
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        gs.observe(gs.hp, 60, evidence='cw-t253-test', sig=_OBS_SIG)
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=_FILLER, star=1))
                 for i in range(5)]
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        cards = [ShopSlot(kind='content',
                          card=ShopCard(name=_FUELS[2], faction='', cost=3,
                                        star=1, slot=1))]
        cards += [ShopSlot(kind='empty')] * 4
        gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        state_of(sess).target_comp = COMP_LIBRARY[0]
        _live = MandateV1Live(gs, SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
        _live.state = state_of(sess)   # 状态同源接线:会话播种对象(零参口)
        action = _live.decide_shop_action()
        assert isinstance(action, CwActionBuyCardParam), f'帧未发射买入: {action!r}'
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert ledger.get(action.card.name) == (1, 3), \
            f'买入后获取账缺登记: {ledger!r}'

    def test_register_acquisition_star_confined(self):
        """N1 星级辖定:覆盖写星级辖 1★——2★ 拒登记(不刷新在场 1★ 对
        轮戳);同名重获取覆盖为最新轮(对时钟起点语义)。"""
        sess = StrategySession()
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=2, star=1)
        assert not sell_gate.register_acquisition(
            sess, _PAIR, plane=1, round_num=_ROUND, star=2), \
            '2★ 买入覆盖写 1★ 条目 = N1 违例'
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=_ROUND, star=1)
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert ledger[_PAIR] == (1, _ROUND), '同名重获取未覆盖为最新轮'


class TestCriterionUnits:

    def test_kept_truth_table_chain_and_k(self):
        """kept 面真值表(保留判据两格):N4 同名 2★ 在 **bench**(非
        deployed)滞留 → kept_chain 保留(场上域钉 bench∪deployed 全场域;
        deployed-only 判读 = 漏保护向);(b) 基准 = 义务重买集:线内名
        (未锁态 base = k_members)对 → kept_k,不入释放集(买家空集
        论证辖域外)。"""
        # N4:bench 侧 2★ 链腿
        sess = StrategySession()
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND,
                                        kind='prep'),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        bench = [BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1)),
                 BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1)),
                 BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=2))]
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=1, star=1)
        release = sell_gate.dead_pair_exit_release(
            sess, (), bench, [], _ROUND,
            counters=state_of(sess).cw4_counters)
        assert release == frozenset(), 'bench 侧 2★ 链腿未被保留(N4 漏保护)'
        assert state_of(sess).cw4_counters.get(
            'dead_pair_exit_guard_kept_chain') == 1
        # (b):线内名对 → kept_k
        member = sorted(_LINE)[0]
        sess_k = StrategySession()
        gs_k = game_state_of(sess_k)
        gs_k.write_logic(gs_k.node, NodeKey(plane=1, round_num=_ROUND,
                                            kind='prep'),
                         produced_by='cw-t253-test', sig=_LOGIC_SIG)
        bench_k = [BenchSlot(kind='unit', unit=Unit(char_id=member, star=1)),
                   BenchSlot(kind='unit', unit=Unit(char_id=member, star=1))]
        assert sell_gate.register_acquisition(sess_k, member, plane=1,
                                              round_num=1, star=1)
        release_k = sell_gate.dead_pair_exit_release(
            sess_k, tuple(sorted(_LINE)), bench_k, [], _ROUND,
            counters=state_of(sess_k).cw4_counters)
        assert release_k == frozenset()
        assert state_of(sess_k).cw4_counters.get(
            'dead_pair_exit_guard_kept_k') == 1

    def test_interest_channel_bypass(self):
        """通道旁路单元:释放成员入资格集(凑息回拉 + 燃料腾席迁并对照;
        仅 G-S1 子谓词被旁路,跨档止盈判据不受旁路影响)。凑息帧 =
        缺口恰容一张(gold = 档线 − refund,单件退金 ≥ 缺口可行),卖出
        对象确定;燃料:显式传释放集 ⇒ 腾席资格集放行且拒因零计数。
        上阵 1 人免空板止损守卫(守卫先于资格循环)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
            sell_refund,
        )
        sess = StrategySession()
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND,
                                        kind='prep'),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        bench = [BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1)),
                 BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1))]
        # 凑息守卫读容器上阵域(非形参):front_row 必写,免空板止损守卫
        gs.write_logic(gs.deployed, _dvs([Unit(char_id='刃', star=1)], []),
                       produced_by='cw-t253-test', sig=_LOGIC_SIG)
        deployed = [Unit(char_id='刃', star=1)]
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=1, star=1)
        release = sell_gate.dead_pair_exit_release(sess, (), bench,
                                                   deployed, _ROUND)
        refund = sell_refund(1, bench_char_cost(mandate._slot_unit(bench[0])))
        gold = saturation_line(7) - refund   # 缺口 = refund:单张恰好跨档
        slots, _key = crit_sell.sell_for_interest(
            gold, bench, 7, (), gs, merge_guard_release=release)
        sold_names = {mandate._slot_cid(bench[s]) for s in slots}
        assert sold_names == {_PAIR}
        # 燃料通道旁路对照(原零漂移测试旁路半迁并)
        sess_f, gs_f, frame_f = _prep_frame(pair_ledger_round=2)
        ct_release: dict = {}
        base_kwargs = {'k_members': frame_f.k_members, 'state': gs_f,
                       'exclude_names': frozenset()}
        cands = mandate.fuel_sell_candidates(
            frame_f.bench, counters=ct_release, dedup_names=set(),
            merge_guard_release=frozenset({_PAIR}), **base_kwargs)
        assert [mandate._slot_cid(b) for b in cands] == [_PAIR, _PAIR]
        assert not ct_release.get('merge_material_guard_blocked')
