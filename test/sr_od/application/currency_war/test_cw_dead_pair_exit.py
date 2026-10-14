"""G-S1 死库存退出通道行为锁(判据⑤)。

出处与语义单一源:
- 判据规格 =
  三合取 + 遥测三键族),数学论证 = proofs P96(帧级支配 + N=3 载体寿命);
- 载体 = ``sell_gate.dead_pair_exit_release`` 单点函数 + 持久获取账
  (``register_acquisition``,写端 = shop._emit_buy 发射位);
- 本文件锁**行为锁①-⑤ + 通道旁路单元(凑息/换线/燃料迁并)+ N1/N4
  收编面**(N3 = 注释级同参钉死,无独立行为锁;消费位同参传参由锁①
  装配路径覆盖;N2 kept_young 分键由锁②辖,缺登记 kept_no_entry 对照
  已退役)。

帧构造边界:素材名取注册表 TIER_UNRELATED 现算集(与
test_cw_dead_stock_pair_wiring 同款防漂移);锁①②③④ 走备战域
``run_mandate`` M4 腾席臂(设计 flagship 场景 = 死锁帧腾席),判据单元
直调 ``dead_pair_exit_release``;黑板 node 必写(位面/轮轴 = 判据 (c)
读源,缺写 = fail-closed 保留 = 释放恒不可达)。
"""

import random
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_UNRELATED,
    line_identity_tier,
    transition_release_names,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    NodeKey,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)

_SIG = ChannelSig(family='logic_action', actor='cw-t253-test', mode='compute')
_OBS_SIG = ChannelSig(family='obs', actor='cw-t253-test', mode='synthesized')


_ROUND = 5
_LINE = set(COMP_LIBRARY[0].core_chars) | set(COMP_LIBRARY[0].shared_chars)
# TIER_UNRELATED 非线内名(注册表现算防漂移):[0] = 素材对名,[1] = 垫件,
# [2] = 商店买卡名(写端测试三名互异)。
_FUELS = [n for n in sorted(CHARACTERS)
          if n not in _LINE and n not in transition_release_names()
          and line_identity_tier(n) == TIER_UNRELATED]
assert len(_FUELS) >= 3, 'TIER_UNRELATED 燃料名不足'
_PAIR = _FUELS[0]
_FILLER = _FUELS[1]


def _transition_pair_name() -> str:
    """④ 放行档名(锁③;非线内,身份段静态持有集成员)。"""
    out = sorted(n for n in transition_release_names() if n not in _LINE)
    assert out, '④ 放行档非线内名不足'
    return out[0]


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
    gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND, kind='reward'),   # 3.6:奖励帧抑制会话内升级(翻转行为差隔离——本锁辖买面登记)
                   produced_by='cw-t253-test', sig=_SIG)
    gs.write_logic(gs.gold, gold, produced_by='cw-t253-test', sig=_SIG)
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
                   produced_by='cw-t253-test', sig=_SIG)
    gs.write_logic(gs.deployed, _dvs([Unit( char_id='刃', star=1)], []),
                   produced_by='cw-t253-test', sig=_SIG)
    if pair_ledger_round is not None:
        assert sell_gate.register_acquisition(
            sess, pair, plane=1, round_num=pair_ledger_round, star=1)
    frame = MandateFrame(
        gold=gold, level=7, bench=[s for s in slots
                                   if s.kind != 'empty'],
        deployed=[Unit( char_id='刃', star=1)],
        deploy_cap=7, node_type='battle', stop_flag=False,
        k_members=k_members, round_num=_ROUND)
    return sess, gs, frame


def _sell_actions(out: list) -> list:
    return [e for e in out if type(e.action).__name__ == 'CwActionSellBenchParam']


# ===== 行为锁①:死锁帧支配语义(2.1.3;释放对成员腾席)=====


class TestLock1DeadlockDominance:

    def test_aged_pair_member_sold_to_free_seat(self):
        """非重买集素材对(账龄 ≥N)+ 缺口件死锁帧 → M4 卖对成员腾席。

        锁 2.1.3:B 弱支配 A(帧内持有收益 0 成本 V_slot>0);卖出腿 =
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
        # 释放集单点直读(原单点锁迁并)
        release = sell_gate.dead_pair_exit_release(
            sess, frame.k_members, frame.bench, frame.deployed, _ROUND,
            counters=state_of(sess).cw4_counters)
        assert release == frozenset({_PAIR})
        assert not any(k.startswith('dead_pair_exit_guard_kept')
                       for k in ct)


# ===== 行为锁②:N 下界(账龄 <N 不卖)=====


class TestLock2AgeLowerBound:

    def test_young_and_fresh_pair_kept_and_guard_counts(self):
        """账龄下界两格(锁 N 下界 + ADR-0558 案发回归形态):账龄
        1 < N=3 的同构死锁帧 → 不卖(守卫照常拒入并按既有键计数);
        新购对(获取账登记轮 == 当前轮,age 0)被燃料臂立即触达 → 守卫
        照常拒、零卖出(原案不复活;新购 ⇒ 当轮窗/获取账合取保持)。"""
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


# ===== 行为锁③:身份段权威(③④ 名义对入释放集仍不卖;旁路先、装配后)=====


class TestLock3IdentityAuthority:

    def test_transition_pair_released_but_not_sold(self):
        """④ 名义素材对:过 (a)(b)(c) 入释放集(released 计 1),身份段
        在下游装配排除 → 零卖出(序列断言:旁路在子谓词内先行,装配 A
        照旧收口)。腾席面空集 → 诚实停摆计数。"""
        tname = _transition_pair_name()
        sess, gs, frame = _prep_frame(pair=tname, pair_ledger_round=2)
        out = run_mandate(frame, sess, state=gs)
        assert not _sell_actions(out)
        ct = state_of(sess).cw4_counters
        assert ct.get('dead_pair_exit_released') == 1
        assert ct.get('dead_pair_exit_guard_kept_identity') == 1
        assert ct.get('m2_retry_exhausted') == 1


# ===== 行为锁⑤:获取账与发射登记簿四出口生命周期解耦 =====


class TestLock5LedgerLifecycleDecoupling:

    def test_entry_survives_all_four_registry_exits(self):
        """发射登记簿四出口销账(轮界/合成/部署/换线)后获取账条目仍在
        (锁退出判据读源修法本体:与易失登记簿生命周期解耦)。"""
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
        fail-closed 不出集(r2 锁面缺口半边:自身闭合行为钉住)。"""
        sess = StrategySession()
        assert sell_gate.register_acquisition(
            sess, _PAIR, plane=1, round_num=_ROUND, star=1)
        bs2 = game_state_of(sess)
        bs2.write_logic(bs2.node, NodeKey(plane=2, round_num=_ROUND + 1,
                                          kind='prep'),
                        produced_by='cw-t253-test', sig=_SIG)
        release = sell_gate.dead_pair_exit_release(sess, (), [], [],
                                                   _ROUND + 1)
        assert release == frozenset()
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert _PAIR not in ledger, '跨位面条目未被位面闭合清除'


# ===== 写端(shop._emit_buy)与 N1 星级辖定 =====


class TestWriteEnd:

    def test_shop_buy_writes_ledger(self):
        """任一臂买入(经发射位)后获取账含该名 =(位面, 买入轮)——
        全因类写端活路径证据(dominance 臂 C=0 首张买入)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            XP_TO_NEXT_LEVEL,
            cap_resolved_of_session,
        )
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BenchSlot,
            BenchView,
            ShopCard,
            ShopPayload,
            ShopSlot,
        )
        from sr_od.application.currency_war.kernel.cw_vocab import CwActionBuyCardParam
        g_star = saturation_line(cap_resolved_of_session(
            StrategySession(rng=random.Random('cw-t253'))))
        sess = StrategySession(rng=random.Random('cw-t253'))
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),   # 3.6:奖励帧抑制会话内升级(本锁辖买面登记)
                       produced_by='cw-t253-test', sig=_SIG)
        gs.write_logic(gs.level, 3, produced_by='cw-t253-test', sig=_SIG)
        gs.write_logic(gs.xp, (0, XP_TO_NEXT_LEVEL[3]),
                       produced_by='cw-t253-test', sig=_SIG)
        gs.write_logic(gs.gold, g_star + 10,
                       produced_by='cw-t253-test', sig=_SIG)
        gs.observe(gs.hp, 60, evidence='cw-t253-test', sig=_OBS_SIG)
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=_FILLER, star=1))
                 for i in range(5)]
        gs.write_logic(gs.bench, BenchView(slots=slots, capacity=9),
                       produced_by='cw-t253-test', sig=_SIG)
        cards = [ShopSlot(kind='content',
                          card=ShopCard(name=_FUELS[2], faction='', cost=3,
                                        star=1, slot=1))]
        cards += [ShopSlot(kind='empty')] * 4
        gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                       produced_by='cw-t253-test', sig=_SIG)
        state_of(sess).target_comp = COMP_LIBRARY[0]
        _live = MandateV1Live(gs, SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
        _live.state = state_of(sess)   # 状态同源接线:会话播种对象(零参口)
        action = _live.decide_shop_action()
        assert isinstance(action, CwActionBuyCardParam), f'帧未发射买入: {action!r}'
        ledger = getattr(state_of(sess), sell_gate.ACQUISITION_LEDGER_ATTR)
        assert ledger.get(action.card.name) == (1, 3), \
            f'买入后获取账缺登记: {ledger!r}'

    def test_register_acquisition_star_confined(self):
        """N1:覆盖写星级辖 1★——2★ 拒登记(不刷新在场 1★ 对轮戳);
        同名重获取覆盖为最新轮(对时钟起点语义)。"""
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


# ===== 判据单元:N4/(b)/通道旁路 =====


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
                       produced_by='cw-t253-test', sig=_SIG)
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
                         produced_by='cw-t253-test', sig=_SIG)
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
        缺口触发/目标量止盈语义零改,仅 G-S1 子谓词被旁路)。凑息:缺口
        恰容一张,卖出对象确定;燃料:显式传释放集 ⇒ 腾席资格集放行且
        拒因零计数。上阵 1 人免空板止损守卫(守卫先于资格循环)。"""
        from sr_od.application.currency_war.kernel.cw_economy import (
            bench_char_cost,
            sell_refund,
        )
        sess = StrategySession()
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND,
                                        kind='prep'),
                       produced_by='cw-t253-test', sig=_SIG)
        bench = [BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1)),
                 BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1))]
        # 凑息守卫读容器上阵域(非形参):front_row 必写,免空板止损守卫
        gs.write_logic(gs.deployed, _dvs([Unit( char_id='刃', star=1)], []),
                       produced_by='cw-t253-test', sig=_SIG)
        deployed = [Unit( char_id='刃', star=1)]
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=1, star=1)
        release = sell_gate.dead_pair_exit_release(sess, (), bench,
                                                   deployed, _ROUND)
        refund = sell_refund(1, bench_char_cost(mandate._slot_unit(bench[0])))
        gold = saturation_line(7) - refund - 1
        slots, _key = crit_sell.sell_for_interest(
            gold, bench, 7, (), gs, merge_guard_release=release)
        sold_names = {mandate._slot_cid(bench[s]) for s in slots}
        assert sold_names == {_PAIR}
        # 燃料通道旁路对照(原零漂移锁旁路半迁并)
        sess_f, gs_f, frame_f = _prep_frame(pair_ledger_round=2)
        ct_release: dict = {}
        base_kwargs = {'k_members': frame_f.k_members, 'state': gs_f,
                       'exclude_names': frozenset()}
        cands = mandate.fuel_sell_candidates(
            frame_f.bench, counters=ct_release, dedup_names=set(),
            merge_guard_release=frozenset({_PAIR}), **base_kwargs)
        assert [mandate._slot_cid(b) for b in cands] == [_PAIR, _PAIR]
        assert not ct_release.get('merge_material_guard_blocked')

    def test_line_switch_channel_bypass(self):
        """换线塌缩通道旁路单元:旧线成员对在换线帧(∉新线 = ∉ base)
        经释放旁路入塌缩对象集;未释放对照帧守卫照拒(零漂移向)。
        上阵 1 人免空板止损守卫。塌缩出口在 u/V_ms【拟】None 期整体
        fail-closed 关闭(注入即解锁,槽位注记明文)——注入形态值解锁
        比较臂,测试终了 reset 复原(改全局态必须复原纪律)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
            provisional,
        )
        sess = StrategySession()
        gs = game_state_of(sess)
        gs.write_logic(gs.node, NodeKey(plane=1, round_num=_ROUND,
                                        kind='prep'),
                       produced_by='cw-t253-test', sig=_SIG)
        bench = [BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1)),
                 BenchSlot(kind='unit', unit=Unit(char_id=_PAIR, star=1))]
        # 塌缩守卫读容器上阵域(非形参):front_row 必写,免空板止损守卫
        gs.write_logic(gs.deployed, _dvs([Unit( char_id='刃', star=1)], []),
                       produced_by='cw-t253-test', sig=_SIG)
        deployed = [Unit( char_id='刃', star=1)]
        assert sell_gate.register_acquisition(sess, _PAIR, plane=1,
                                              round_num=1, star=1)
        release = sell_gate.dead_pair_exit_release(sess, (), bench,
                                                   deployed, _ROUND)
        provisional.inject('U_X', provisional.CalibValue(
            1.0, injected_form=True))
        provisional.inject('V_MS', provisional.CalibValue(
            1.0, injected_form=True))
        try:
            slots, _key = crit_sell.line_switch_sell(
                (_PAIR,), (), bench, deployed, gs, k_switched=True,
                merge_guard_release=release)
            assert slots == [0, 1]   # 紧缩位键(0 基)
            slots_guarded, _key2 = crit_sell.line_switch_sell(
                (_PAIR,), (), bench, deployed, gs, k_switched=True)
            assert slots_guarded == []
        finally:
            provisional.reset('U_X')
            provisional.reset('V_MS')
