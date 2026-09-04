"""P56 可变现息线下界 + T1 凑息卖语义重写 + P57 双读法参数化(单帧锁)。

出处(锁纪律:新锁必引设计出处)= docs/develop/currency_war/strategy/
13_buy_face_design.md:§2.2(P56 下界构造 + T1 三项语义重写 + 「已落地并
可对拍」验收定义 R2-N4 三断言 + R2-N1 发射约束)/§2.3(T1 短路径布尔门
退役 + P57 双读法)/§3.2(分键遥测四字段 R3-R5)。
"""
from __future__ import annotations

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
    vbar,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
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
        """M6 买入金约束=P56 可变现下界:线成型帧(无活期卡 ⇒
        s_reserve=g*=50)下,cost2 件买后 49<50 ⇒ 拒 + 'm6_s_reserve_
        reject' 计数;cost1 件买后 50≥50 ⇒ 发射。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
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
            s.cw4_counters = {}
            s.target_comp = comp
            s.cw4_line_state = proof.LineState()
            strat = MandateV1Strategy(registry=sim_decision_registry())
            s.shop_state_frame = st
            return strat.decide_shop_screen(s, _Cfg()), s

        # cost2:拒(51−2=49 < s_reserve=g*=50,无活期卡背书)
        acts, s = _run(2)
        assert not [a for a in acts if isinstance(a, BuyCard)]
        assert s.cw4_counters.get('m6_s_reserve_reject', 0) == 1
        # cost1:过(50 ≥ 50 边界),发射 M6 买入
        acts2, s2 = _run(1)
        assert any(isinstance(a, BuyCard) and a.reason == 'm6_stockpile'
                   for a in acts2)
        assert 'm6_s_reserve_reject' not in s2.cw4_counters

    def test_pullback_fires_after_spending(self):
        """回拉发射位接线:买/花后投影金 < g* ⇒ 发射凑息卖
        (reason='sell_for_interest'),分键遥测四字段落 session counters。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
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
        sess.cw4_counters = {}
        sess.target_comp = comp
        sess.cw4_line_state = proof.LineState()
        strat = MandateV1Strategy(registry=sim_decision_registry())
        sess.shop_state_frame = st
        acts = strat.decide_shop_screen(sess, object())
        # reason 载在 Emitted 包装层(非动作属性);本帧无 M4/M2 腾席
        # 路径 ⇒ SellBench 唯一来源=回拉发射位
        pulls = [a for a in acts if isinstance(a, SellBench)]
        assert len(pulls) == 1
        ct = sess.cw4_counters
        assert ct.get('t1_interest_emit_frames') == 1
        assert ct.get('t1_interest_gap_total') == 10      # g*=50 − 40
        assert ct.get('t1_interest_sellback_total') == 3  # 单张未注册名退 3
        assert ct.get('t1_pullback_gold_ge_gstar', 0) == 0


class TestP57VbarReading:
    """P57 双读法参数化:窗口门 V̄ 读法可配置,生产默认读法②。"""

    def _reg(self):
        from sr_od.application.currency_war.sim.engine_p1 import (
            sim_decision_registry,
        )
        return sim_decision_registry()

    def test_default_reading_is_frame_horizon(self):
        assert vbar.DEFAULT_VBAR_READING == 'frame_horizon'
        assert set(vbar.VBAR_READINGS) == {'per_step', 'frame_horizon'}

    def test_two_readings_values(self):
        reg = self._reg()
        assert vbar.window_vbar(reg, 7, 'per_step') \
            == vbar.v_bar_net(reg, 1, 1)
        assert vbar.window_vbar(reg, 7, 'frame_horizon') \
            == vbar.v_bar_net(reg, 7, 1)
        assert vbar.window_vbar(reg, 7, 'frame_horizon') \
            > vbar.window_vbar(reg, 7, 'per_step')
        # 脏读法回落缺省读法②(不放大为行为分叉)
        assert vbar.window_vbar(reg, 7, 'bogus') \
            == vbar.window_vbar(reg, 7, 'frame_horizon')

    def test_windows_differ_between_readings(self):
        """两读法窗口集分立(P57 差异域实锚;L6 档级:读法①下全档
        p<2/V̄₁步 被剔,读法②视界 V̄ 大 ⇒ 全正概率档入窗)。"""
        reg = self._reg()
        v_step = vbar.window_vbar(reg, 20, 'per_step')
        v_frame = vbar.window_vbar(reg, 20, 'frame_horizon')
        assert odds.tier_search_window(6, v_step) \
            != odds.tier_search_window(6, v_frame)
        assert odds.card_search_window(7, v_step) \
            != odds.card_search_window(7, v_frame)

    def test_frame_window_diff_fingerprint(self):
        """P57 窗口集指纹(分键遥测):两读法窗口集不同的帧计数落键。"""

        class _StubReg:
            win_rate_dp_by_plane = {1: 1.0 / 11.59, 2: 0.0}
            vbar_hp_value_transitional = 9.59

        class _Sess:
            plane_lengths_seen = [9, 9, 9]

        st = GameState(gold=30, level=6, round_num=1)
        st.plane = 1
        ct: dict = {}
        tier_w, card_w = shop._frame_search_windows(
            _Sess(), st, _StubReg(), 'per_step', ct)
        # 斜率 V̄=1 ⇒ 阈值 2.0 ⇒ L6 全档被剔(空窗);视界 V̄=1×r 大 ⇒ 非空
        assert tier_w == frozenset()
        assert ct.get('p57_tier_window_diff_frames') == 1
        st2 = GameState(gold=30, level=6, round_num=1)
        st2.plane = 1
        ct2: dict = {}
        tier_w2, _ = shop._frame_search_windows(
            _Sess(), st2, _StubReg(), 'frame_horizon', ct2)
        assert tier_w2 == odds.tier_search_window(
            6, vbar.window_vbar(_StubReg(), 27, 'frame_horizon'))


class TestOddsWindowBackcompat:
    """窗口函数 vbar 参数化向后兼容:vbar=None 保留 V_MS 槽读旧调用面
    (对拍锚测试语义不变;T1 后生产消费位传帧级现算值)。"""

    def test_vbar_none_reads_v_ms(self):
        try:
            assert odds.tier_search_window(7) == frozenset()
            provisional.inject('V_MS', provisional.CalibValue(24.7))
            assert odds.tier_search_window(7, None) == frozenset(
                {1, 2, 3, 4})
            assert odds.card_search_window(7, None) == frozenset({2, 3})
        finally:
            provisional.reset('V_MS')
