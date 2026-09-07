"""P56 可变现息线下界 + T1 凑息卖语义重写 + P57 双读法参数化(单帧锁)。

出处(锁纪律:新锁必引设计出处)= docs/develop/currency_war/strategy/
13_buy_face_design.md:§2.2(P56 下界构造 + T1 三项语义重写 + 「已落地并
可对拍」验收定义 R2-N4 三断言 + R2-N1 发射约束)/§2.3(T1 短路径布尔门
退役 + P57 双读法)/§3.2(分键遥测四字段 R3-R5)。
"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    buy as crit_buy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    sell as crit_sell,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    stockpile as crit_stockpile,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    odds,
)

# ===== 测试基建(与 test_cw4_shop_line 同构)=====


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 3, star: int = 1, x: int = 100) -> ShopCard:
    return ShopCard(x=x, name=name, cost=cost, star=star)


class TestT1PullbackSemantics:
    """T1 凑息卖语义重写(R2-N4「已落地并可对拍」验收定义三断言)。"""

    #: 未注册名 ⇒ bench_char_cost 保守估 3 ⇒ 1★ 全额退 3 金/张(确定性)
    BENCH = [_bc('燃料A', slot=1), _bc('燃料B', slot=2),
             _bc('燃料C', slot=3)]
    K = ('线内件',)

    def test_no_gap_frame_zero_emission(self):
        """断言③:非缺口帧零发射(gold ≥ g* ⇒ 'not_needed')。"""
        slots, key = crit_sell.sell_for_interest(
            50, self.BENCH, 5, self.K, state=GameState())
        assert key == 'not_needed' and slots == []
        slots2, _ = crit_sell.sell_for_interest(
            60, self.BENCH, 5, self.K, state=GameState())
        assert slots2 == []

    def test_gap_frame_target_amount_stop(self):
        """断言②:卖回 Σrefund ≥ 缺口且不多卖一张(remaining 递减贪心
        止盈;缺口 6 = 两张 3 金件,缺口 4 = 第二张后 Σ=6 为最小覆盖)。"""
        slots, key = crit_sell.sell_for_interest(
            44, self.BENCH, 5, self.K, state=GameState())
        assert key == '' and slots == [1, 2]     # 3+3=6 ≥ 缺口 6
        slots2, _ = crit_sell.sell_for_interest(
            46, self.BENCH, 5, self.K, state=GameState())
        assert slots2 == [1, 2]                  # 3 < 4 ⇒ 需第二张;6 ≥ 4 止
        # 缺口 3 = 一张够:恰卖一张(不多卖)
        slots3, _ = crit_sell.sell_for_interest(
            47, self.BENCH, 5, self.K, state=GameState())
        assert slots3 == [1]

    def test_emit_frames_equal_gap_frames(self):
        """断言①:发射帧数 = 缺口帧数;分键遥测字段随 counters 落键
        (R3-R5:发射帧/缺口累计/卖回累计/回拉后金位轨迹)。"""
        ct: dict = {}
        emits = []
        for gold in (50, 55, 44, 30):
            slots, key = crit_sell.sell_for_interest(
                gold, self.BENCH, 5, self.K, state=GameState(),
                counters=ct)
            if not key:
                emits.append(gold)
        assert emits == [44, 30]
        assert ct['t1_interest_emit_frames'] == 2
        assert ct['t1_interest_gap_total'] == (50 - 44) + (50 - 30)
        # 缺口 6:卖 6(覆盖);缺口 20:全卖 9(<g*,不覆盖)
        assert ct['t1_interest_sellback_total'] == 6 + 9
        assert ct['t1_pullback_gold_ge_gstar'] == 1

    def test_prefer_bought_names_first(self):
        """R2-N1 发射约束:刚买件首卖(连带卖出损失=0 的实现形态;
        帧投影架构下按名匹配同资格在册件)。"""
        bench = [_bc('燃料A', slot=1), _bc('燃料B', slot=2)]
        slots, key = crit_sell.sell_for_interest(
            44, bench, 5, ('线内件',), state=GameState(),
            prefer_names=('燃料B',))
        assert key == '' and slots == [2, 1]

    def test_qualification_predicate_unchanged(self):
        """资格谓词不变:线内件(零重叠不过)不入卖回集。"""
        bench = [_bc('线内件X', slot=1), _bc('燃料A', slot=2)]
        slots, _ = crit_sell.sell_for_interest(
            44, bench, 5, ('线内件X',), state=GameState())
        assert slots == [2]


class TestP56RealizableFloor:
    """P56 可变现息线下界:s_reserve := g* − Σ活期退金投影。"""

    def test_stockpile_s_reserve_boundary(self):
        """金约束边界:gold − cost ≥ g* − Σrefund 过,差 1 拒(未注册名
        退金 3/张 → s_reserve=50−3=47);T_SEARCH_A 布尔门退役 ⇒ 任何
        注入态都不再返回 't_search_unavailable'(T1 短路径)。"""
        s_reserve = 50 - 3
        assert crit_stockpile.stockpile_buy(
            50, s_reserve, 2, 1, 1, frozenset({1, 2, 3})) == (True, '')
        assert crit_stockpile.stockpile_buy(
            48, s_reserve, 2, 1, 1, frozenset({1, 2, 3})) == (True, '')
        ok, why = crit_stockpile.stockpile_buy(
            47, s_reserve, 2, 1, 1, frozenset({1, 2, 3}))
        assert ok is False and why == 's_reserve'
        # 布尔门退役:provisional 全 None 期窗口由消费位现算传入,判据
        # 本体不再探 T_SEARCH_A
        try:
            provisional.reset()
            ok2, why2 = crit_stockpile.stockpile_buy(
                50, 0, 2, 1, 1, frozenset({1, 2, 3}))
            assert ok2 and why2 == ''
        finally:
            provisional.reset()

    def test_ev_buy_s_reserve_reject_counter(self):
        """EV 买面 P56 拒因分键(R3-R5):s_reserve 过滤逐卡计数。"""
        ct: dict = {}
        try:
            provisional.inject('U_X', provisional.CalibValue(1.0))
            out, key = crit_buy.ev_buy_candidates(
                49, 47, [_card('散件X', cost=3)], (), level=4,
                window=frozenset({1, 2, 3}), counters=ct)
            assert key == '' and out == []
            assert ct.get('ev_buy_s_reserve_reject') == 1
            out2, _ = crit_buy.ev_buy_candidates(
                50, 47, [_card('散件X', cost=3)], (), level=4,
                window=frozenset({1, 2, 3}), counters=ct)
            assert len(out2) == 1
            assert ct.get('ev_buy_s_reserve_reject') == 1  # 不重复计
        finally:
            provisional.reset('U_X')


class TestShopWiringP56T1:
    """shop 线接线锁:M6 P56 拒因计数 + 回拉发射位随帧落键。"""

    def test_m6_p56_reject_counter(self):
        """M6 买入金约束=P56 可变现下界(锁重推导,14号稿 §3 臂①落码后):
        线成型帧下 1★ 线成员副本已归臂①义务囤腿(m2_stockpile,不走息律
        门——P56 s_reserve 门是 M6 的,不辖 M2/M2b);本锁改两点:①副本帧
        断言臂①接手(息律门不再辖义务买);②M6 s_reserve 消费位判据本体
        直锁(stockpile_buy:cost+S 预留不足 ⇒ 's_reserve' 拒)。M6 剩余
        可达面与 dominance 门向竞态 = 已登记 D0/C2(14号稿 §8)。"""
        from sr_od.application.currency_war.kernel.cw_comps import (
            COMP_LIBRARY,
            get_comp,
        )
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.stockpile import (
            stockpile_buy,
        )

        class _Cfg:
            ev_arm = 'full'

        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        comp = get_comp(names[0])
        members = list(dict.fromkeys(
            list(comp.core_chars) + list(getattr(comp, 'shared_chars', [])
                                         or [])))
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(members)]

        def _run(cost: int) -> tuple[list, StrategySession]:
            st = GameState(gold=51, level=4, round_num=2)
            st.shop = [_card(members[0], cost=cost)]
            st.bench = list(bench)
            st.deployed = []
            s = StrategySession()
            state_of(s).cw4_counters = {}
            state_of(s).target_comp = comp
            state_of(s).cw4_line_state = proof.LineState()
            strat = MandateV1Strategy(registry=sim_decision_registry())
            s.shop_state_frame = st
            return strat.decide_shop_screen(s, _Cfg()), s

        # ①副本帧:臂①义务囤腿接手(不走息律门,gold 51 ≥ cost 2)
        acts, s = _run(2)
        assert any(isinstance(a, BuyCard) and a.reason == 'm2_stockpile'
                   for a in acts)
        assert 'm6_s_reserve_reject' not in state_of(s).cw4_counters
        # ②M6 s_reserve 消费位判据本体直锁:s_reserve=g*=50 语境,
        # cost2 买后 49 < 50 ⇒ 拒;cost1 买后 50 ≥ 50 ⇒ 过
        ok_r, key_r = stockpile_buy(51, 50, 4, 2, 1, frozenset({1, 2, 3}))
        assert ok_r is False and key_r == 's_reserve'
        ok_a, _ = stockpile_buy(51, 50, 4, 1, 1, frozenset({1, 2, 3}))
        assert ok_a is True

    def test_pullback_fires_after_spending(self):
        """回拉发射位接线:买/花后投影金 < g* ⇒ 发射凑息卖
        (reason='sell_for_interest'),分键遥测四字段落 session counters。"""
        from sr_od.application.currency_war.kernel.cw_comps import (
            COMP_LIBRARY,
            get_comp,
        )
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        names = [c.name for c in COMP_LIBRARY
                 if getattr(c, 'core_chars', None)]
        comp = get_comp(names[0])
        members = list(dict.fromkeys(
            list(comp.core_chars) + list(getattr(comp, 'shared_chars', [])
                                         or [])))
        bench = [_bc(m, slot=i + 1) for i, m in enumerate(members)]
        bench.append(_bc('燃料A', slot=len(members) + 1))
        st = GameState(gold=40, level=3, round_num=2)
        st.shop = []
        st.bench = bench
        st.deployed = []
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        state_of(sess).target_comp = comp
        state_of(sess).cw4_line_state = proof.LineState()
        strat = MandateV1Strategy(registry=sim_decision_registry())
        sess.shop_state_frame = st
        acts = strat.decide_shop_screen(sess, object())
        # reason 载在 Emitted 包装层(非动作属性);本帧无 M4/M2 腾席
        # 路径 ⇒ SellBench 唯一来源=回拉发射位
        pulls = [a for a in acts if isinstance(a, SellBench)]
        assert len(pulls) == 1
        ct = state_of(sess).cw4_counters
        # ADR-0517 计数粒度重锚:回拉遥测从「每波一次」改「每决策帧一次」
        # ——帧1 缺口 10(g*50−40)发卖;帧2 卖后金 43,缺口 7 仍在但
        # 合格集空(唯一燃料件已卖),emit 帧再计一次 ⇒ 帧数 2、缺口累计
        # 17(10+7);卖出量恒 1(单张未注册名退 3)。
        assert ct.get('t1_interest_emit_frames') == 2
        assert ct.get('t1_interest_gap_total') == 17
        assert ct.get('t1_interest_sellback_total') == 3  # 单张未注册名退 3
        assert ct.get('t1_pullback_gold_ge_gstar', 0) == 0


class TestWindowCollapseAnchor:
    """窗口判据 ADR-0516 重锚(塌缩带锚;P57 读法问题随 V̄ 退役消解):
    _frame_search_windows 帧级现算 = odds 两窗口函数在 registry.omega_
    collapse_ratio 下的取值;无读法参数、无 V̄/V_MS 消费。"""

    def test_frame_windows_match_odds_omega(self):
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )

        class _Sess:
            plane_lengths_seen = [9, 9, 9]

        st = GameState(gold=30, level=6, round_num=1)
        st.plane = 1
        reg = sim_decision_registry()
        ct: dict = {}
        tier_w, card_w = shop._frame_search_windows(_Sess(), st, reg, ct)
        assert tier_w == odds.tier_search_window(
            6, reg.omega_collapse_ratio)
        assert card_w == odds.card_search_window(
            6, reg.omega_collapse_ratio)
        # 无读法分叉:不再落 p57 分键遥测
        assert not [k for k in ct if k.startswith('p57_')]


class TestOddsWindowBackcompat:
    """窗口函数参数面向后兼容:旧调用面 card_search_window(level)
    (buy.py T_SEARCH_A 注入态契约路径)在 ω 锚下按缺省
    DEFAULT_REGISTRY.omega_collapse_ratio 取值。"""

    def test_default_call_matches_registry_omega(self):
        from sr_od.application.currency_war.kernel.cw_registry import (
            DEFAULT_REGISTRY,
        )

        assert odds.tier_search_window(7) == odds.tier_search_window(
            7, DEFAULT_REGISTRY.omega_collapse_ratio)
        assert odds.card_search_window(7) == odds.card_search_window(
            7, DEFAULT_REGISTRY.omega_collapse_ratio)


# ===== T-115 规则②:凑息卖 prep 接线 + 死金压库买入 + Z1 卖回切除 =====

def _prep_session():
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _prep_frame(gold, bench, *, node=None, k=(), round_num=2):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        mandate,
    )
    return mandate.MandateFrame(
        gold=gold, level=3, bench=bench, deployed=[], deploy_cap=4,
        node_type=node, stop_flag=False, k_members=k, round_num=round_num)


def _prep_state(gold):
    from sr_od.application.currency_war.kernel.cw_state import GameState
    return GameState(gold=gold, level=3, hp=80, plane=1, round_num=2)


class TestT115PrepInterestEmit:
    """规则②(a) prep 凑息接线(D5)+ Z1 卖回切除(ADR-0580)。"""

    def test_prep_gap_frame_emits_fuel_sell(self):
        """备战帧 gold 9 < g* ∧ bench 有 1★ 燃料 ⇒ 发射 SellBench
        (Emitted 分键 = t1_interest_prep_emit,载体 = prep 域无 reason
        字段的既有边界);同帧凑息臂与腾席环共享素材去重(每帧每素材
        至多 1)。state 必传(N1):漏传 = 血线地板 fail-closed 结构性
        哑火,本帧形 SellBench 断言即红。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        bench = [_bc('燃料件A', slot=1)]
        out = mandate_run(_prep_frame(9, bench), _prep_session(),
                          _prep_state(9))
        assert [e.action.slot for e in out
                if isinstance(e.action, SellBench)] == [1]

    def test_hold_class_excluded_from_sellback_with_red_proof(self):
        """Z1 静态排除:bench 唯一 ④放行件(藿藿,carry 档,1★ 零重叠
        无后台效果)⇒ 凑息臂资格空,零卖出发射。红证(断言翻红路径):
        直接调 sell_for_interest 不带 Z1 排除扩展 ⇒ 藿藿恰入卖出槽集
        ——「移除 exclude 扩展 → ④件被卖回」的机制复现(1★ 全额退金回
        原位,机械抵消裁定③④持有语义)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            sell as crit_sell,
        )
        bench = [_bc('藿藿', slot=1)]
        sess = _prep_session()
        out = mandate_run(_prep_frame(9, bench), sess, _prep_state(9))
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        assert not [e for e in out if isinstance(e.action, SellBench)]
        # 红证:无 Z1 排除扩展(仅义务集,此处 k=())→ 藿藿资格成立
        slots, key = crit_sell.sell_for_interest(
            9, bench, 5, (), state=_prep_state(9), exclude_names=())
        assert key == '' and slots == [1]

    def test_hold_class_exclusion_covers_in_sale_unbought(self):
        """Z1 覆盖「在售未买」态:registry 核心卡(希儿)在 bench(已买
        待持有形态)同不入凑息资格(静态两集对状态无歧义)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        bench = [_bc('希儿', slot=1)]
        out = mandate_run(_prep_frame(9, bench), _prep_session(),
                          _prep_state(9))
        assert not [e for e in out if isinstance(e.action, SellBench)]

    def test_buyout_cap_disables_prep_arm(self):
        """息帽维度(B2):买断制局 cap_resolved=0 ⇒ g*=0,gold<g* 恒假
        ⇒ (a) 备战臂零发射(帧凑息零收益卖件不做得 = 正确形态)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        sess = _prep_session()
        state_of(sess).cw4_cap_override = 0
        out = mandate_run(_prep_frame(9, [_bc('燃料件A', slot=1)]), sess,
                          _prep_state(9))
        assert not [e for e in out if isinstance(e.action, SellBench)]

    def test_locked_frame_wide_member_excluded_from_sellback(self):
        """Z1 锁线域残留红证(落地审低-1 修复,与 Z1 红证同构):锁线帧
        采购集宽成员(locked_buy_membership ⊋ line_members 的阵营/流派
        扩展成员)在 bench ⇒ prep 凑息臂不卖——排除集义务基座与 shop
        消费位同源(锁线宽集解析收在 sell_hold_exclusions 函数体内,
        两处调用只传各自 k_members)。红证 = 按窄集(line_members)装配
        排除时该成员恰入卖出槽集(宽−窄成员被卖 → shop 域 M2 重买 =
        Z1 锁线域病理复现)。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
            locked_buy_membership,
        )
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            sell as crit_sell,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
            predicates,
        )
        comp = get_comp('列车同行')
        ist = IntentionState()
        ist.phase = 'locked'
        ist.locked_comp = '列车同行'
        wide = set(locked_buy_membership(ist))
        narrow = set(predicates.line_members(comp))
        # 锁前提:宽集须真 ⊋ 窄集,且宽−窄成员存在(否则本锁空转)
        extra = wide - narrow
        assert extra, '锁前提失效:该 comp 锁定采购集无窄集外成员'
        member = sorted(extra)[0]
        bench = [_bc(member, slot=1)]
        k = tuple(sorted(narrow))
        sess = _prep_session()
        state_of(sess).v3_intention = ist
        out = mandate_run(_prep_frame(9, bench, k=k), sess, _prep_state(9))
        assert not [e for e in out if isinstance(e.action, SellBench)], \
            f'锁线宽集成员 {member} 被凑息臂卖出 = Z1 锁线域残留'
        # 红证:窄集排除(修复前 prep 位基座形态)→ 成员恰入卖出槽集
        slots, key = crit_sell.sell_for_interest(
            9, bench, 5, k, state=_prep_state(9), exclude_names=k)
        assert key == '' and slots == [1], \
            f'红证失效:{member} 未穿过窄集排除外的全部资格谓词'


def mandate_run(frame, sess, state):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        mandate,
    )
    return mandate.run_mandate(frame, sess, state=state)


class TestT115DeadGoldPressBuy:
    """规则②(b) 死金压库买入(B2 地板 + 诚实空转 + 买断制出辖)。"""

    @staticmethod
    def _shop_frame(gold, cards, *, node='reward'):
        from sr_od.application.currency_war.kernel.cw_state import GameState
        st = GameState(gold=gold, level=7, hp=80, plane=1, round_num=3)
        st.node_type = node
        st.shop = list(cards)
        return st

    @staticmethod
    def _shop_sess():
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        s = StrategySession()
        state_of(s).cw4_counters = {}
        return s

    def test_floor_blocks_cost5_releases_cost1_on_gold11(self):
        """gold 11 帧地板判据(方案回归帧):死金 = 11−10×1 = 1 ——
        5 费候选被地板拦、1 费候选放行;买入即登记名入会话级集合
        (Z1 动态排除载体)。"""
        from sr_od.application.currency_war.kernel.cw_state import BuyCard
        st = self._shop_frame(11, [_card('高价杂件', cost=5),
                                   _card('廉价杂件', cost=1)])
        sess = self._shop_sess()
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard) and act.card.name == '廉价杂件'
        assert act.reason == 'dead_gold_press_buy'
        assert state_of(sess).cw4_counters.get('dead_gold_press_buy_hit') == 1
        assert '廉价杂件' in state_of(sess).cw4_dead_gold_bought_names

    def test_honest_idle_when_no_candidate_fits_floor(self):
        """全不可达 = 诚实空转允许囤(禁为花而买垃圾):仅 5 费候选帧
        地板全拦 ⇒ CloseShop 收尾。"""
        from sr_od.application.currency_war.kernel.cw_state import CloseShop
        st = self._shop_frame(11, [_card('高价杂件', cost=5)])
        sess = self._shop_sess()
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, CloseShop)

    def test_buyout_cap_disables_shop_arm(self):
        """买断制局 g*=0 ⇒ (b) 触发带关闭(与 (a) 同 B2 语义);帧的
        其余既有买面(如 T5 止血买,自有息纪律)不在本锁辖域。"""
        st = self._shop_frame(11, [_card('廉价杂件', cost=1)])
        sess = self._shop_sess()
        state_of(sess).cw4_cap_override = 0
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        if isinstance(act, BuyCard):
            assert act.reason != 'dead_gold_press_buy'
        assert 'dead_gold_press_buy_hit' not in state_of(sess).cw4_counters

    def test_pullback_success_closes_press_arm(self):
        """双臂互斥·臂序(Z1):(a) 凑息回拉达标(gold ≥ g*)⇒ 后续
        商店帧 (b) 触发带自然关闭——「(a) 卖出后 (b) 买回」被金位切除
        (帧面其余既有买面如 T5 非本锁辖域)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench as PrepSellBench,
        )
        bench = [_bc('燃料件A', slot=1), _bc('燃料件B', slot=2)]
        sess = _prep_session()
        out = mandate_run(_prep_frame(45, bench), sess, _prep_state(45))
        sells = [e.action.slot for e in out
                 if isinstance(e.action, PrepSellBench)]
        assert sorted(sells) == [1, 2]   # 凑息臂卖两件:45+6 ≥ g*=50
        st = self._shop_frame(51, [_card('廉价杂件', cost=1)])
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        if isinstance(act, BuyCard):
            assert act.reason != 'dead_gold_press_buy'
        assert 'dead_gold_press_buy_hit' not in state_of(sess).cw4_counters

    def test_press_buy_registration_blocks_sellback_cross_frame(self):
        """Z1 动态排除·跨轮形态:前帧 (b) 买入登记件(廉价杂件)后续
        备战帧不入凑息资格;红证 = 无登记时该件恰入卖出槽集(移除
        排除扩展即「买回→卖回」零和对冲复现)。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            SellBench,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
            sell as crit_sell,
        )
        sess = self._shop_sess()
        st = self._shop_frame(11, [_card('廉价杂件', cost=1)])
        from sr_od.application.currency_war.kernel.cw_state import BuyCard
        act = shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))
        assert isinstance(act, BuyCard)
        bench = [_bc('廉价杂件', slot=1)]
        out = mandate_run(_prep_frame(9, bench), sess, _prep_state(9))
        assert not [e for e in out if isinstance(e.action, SellBench)]
        # 红证:无登记(排除扩展缺位)→ 廉价杂件入卖出槽集
        slots, key = crit_sell.sell_for_interest(
            9, bench, 5, (), state=_prep_state(9), exclude_names=())
        assert key == '' and slots == [1]
