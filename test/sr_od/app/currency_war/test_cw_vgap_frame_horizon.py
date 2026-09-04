"""修 A 批测试:R1 刷新门 V̄ 比较项换帧级 horizon 现算(P53/dd-025)。

锁(出处=P53-frame-horizon-vgap.md §2/§3 + dd-025):
- 链锚:r=5 时 V̄_net 逐位等于旧静态注入 24.7(连续性锚——修 A 是
  horizon 口径修正不是标定更换);对 r 严格递增;r≤0 归零;
  连胜金下界 = STREAK_GOLD_TABLE 表值(禁复制字面量);
- 门形态:同一帧态下短视界深缺口关(shop_r1_account_over_vgap)/
  长视界开(RefreshShop 发射)——按视界单调,与 P40 ⑤「本期刷窗
  用尽即停」方向一致;
- 槽位语义:V_GAP 槽位保持 fail-closed 开闸通道,槽位数值不再是比较项
  (注入 0.0 长视界仍开/注入大值短视界仍关 = 比较项已帧级化的判别锁)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import vbar
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, get_comp
from sr_od.application.currency_war.kernel.cw_economy import STREAK_GOLD_TABLE
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
    ShopCard,
)

# ===== 测试基建(与 test_cw_zero_refresh_fix 同款桩)=====


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _session(comp=None, plane_lengths=None):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = comp
    s.cw4_line_state = proof.LineState()
    if plane_lengths is not None:
        s.plane_lengths_seen = list(plane_lengths)
    return s


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _decide(state: GameState, session) -> list:
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )

    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    from types import SimpleNamespace
    return strat.decide_shop_screen(session, SimpleNamespace(ev_arm='full'))


class TestVBarNetChain:
    """链锚(单测纯数面;P53 §2)。"""

    def test_continuity_anchor_r5_equals_old_injection(self):
        """连续性锚:V̄_net(r=5)=24.7 = calib_vuh_v1 v_bar_e2(旧静态
        注入值)——修 A 只换 horizon 因子,链与标定带连续。"""
        assert abs(vbar.v_bar_net(DEFAULT_REGISTRY, 5) - 24.7) < 0.05

    def test_monotone_in_horizon(self):
        """单调性:r∈[1,20] 严格递增(跨期流价值随视界线性增长)。"""
        vals = [vbar.v_bar_net(DEFAULT_REGISTRY, r) for r in range(1, 21)]
        assert all(b > a for a, b in zip(vals, vals[1:]))

    def test_formula_anchors_from_registry(self):
        """零新自由参数:逐因子 = 注册表现读(rung_value[2] + Δp(e0→e1)
        × 单战价值)× r,禁出现与注册表脱钩的第二处数值。"""
        reg = DEFAULT_REGISTRY
        dp = reg.h3_win_rate[1] - reg.h3_win_rate[0]
        pb = reg.expected_battle_loss * reg.hp_to_gold \
            + vbar.streak_floor_gold()
        for r in (1, 5, 12, 17):
            assert vbar.v_bar_net(reg, r) == pytest.approx(
                (reg.rung_value[2] + dp * pb) * r)

    def test_streak_floor_is_table_value(self):
        """连胜金下界 = STREAK_GOLD_TABLE 连胜 2-4 档表值 min(=2)——
        真源在 cw_economy,禁在本链复制字面量。"""
        assert vbar.streak_floor_gold() == min(STREAK_GOLD_TABLE[2:5])
        assert vbar.streak_floor_gold() == 2

    def test_zero_horizon_is_zero(self):
        """视界耗尽 ⇒ V̄_net=0 ⇒ 门恒关(P40 ⑤「本期刷窗用尽即停」)。"""
        assert vbar.v_bar_net(DEFAULT_REGISTRY, 0) == 0.0


class TestR1FrameHorizonGate:
    """门形态(行为锁;出处=P53 §3 开门形态 + dd-025)。

    帧态构造:lv5、目标成员 1★×1(j=1)、gold=61——REFRESH_CFO_CHECKPOINT
    arm2 seed22 r4 的同型帧(该帧旧静态门账 46.3 vs 24.7 被拦)。视界用
    ``plane_lengths_seen`` 控制:plane=2、node=2、seen=[9,L2,L3] ⇒
    r=(L2−1)+L3,可覆盖 r∈[1,17]。
    """

    @staticmethod
    def _frame(r_target: int) -> tuple[GameState, object]:
        comp = _comp()
        m1 = _members(comp)[0]
        bench = [_bc(m1)] + [_bc(m, slot=i + 2)
                             for i, m in enumerate(_members(comp)[1:5])]
        st = GameState(gold=61, level=5, round_num=2)
        st.plane = 2
        st.shop = [ShopCard(x=100, name='垫', cost=3, star=1)]
        st.bench = bench
        st.deployed = []
        # r=(L2-1)+L3;L2/L3 各夹 [1,9]
        l2 = min(9, r_target)
        l3 = max(1, r_target - (l2 - 1))
        assert (l2 - 1) + l3 == r_target
        sess = _session(comp, plane_lengths=[9, l2, l3])
        return st, sess

    @staticmethod
    def _gate_open(r_target: int) -> bool:
        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=24.7, ci_lo=16.7, ci_hi=24.7, injected_form=True))
            st, sess = TestR1FrameHorizonGate._frame(r_target)
            acts = _decide(st, sess)
            return any(isinstance(a, RefreshShop) for a in acts)
        finally:
            provisional.reset('V_GAP')

    def test_short_horizon_deep_gap_closed(self):
        """短视界(r=5)同型深缺口帧:承诺账 > V̄_net(5)=24.7 ⇒ 关门 +
        ``shop_r1_account_over_vgap`` 分键——报告 §4 反例帧(账 46.3
        被 24.7 拦)在帧级口径下的短视界对照面。"""
        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=24.7, ci_lo=16.7, ci_hi=24.7, injected_form=True))
            st, sess = self._frame(5)
            acts = _decide(st, sess)
            assert not [a for a in acts if isinstance(a, RefreshShop)]
            assert sess.cw4_counters.get('shop_r1_account_over_vgap', 0) >= 1
        finally:
            provisional.reset('V_GAP')

    def test_long_horizon_same_frame_opens(self):
        """长视界(r=14)同一帧态:V̄_net(14)≈69 > 承诺账 ⇒ 开门发射
        (修前静态门此帧恒拦;报告 §6「r≥14 全开」分层的单帧锁)。"""
        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=24.7, ci_lo=16.7, ci_hi=24.7, injected_form=True))
            st, sess = self._frame(14)
            acts = _decide(st, sess)
            assert any(isinstance(a, RefreshShop) for a in acts)
        finally:
            provisional.reset('V_GAP')

    def test_horizon_monotone_no_reclose(self):
        """按视界单调:同帧态 r=5 关 → r=7 关 → r=14 开;且 r≥开门点后
        不再回关(阈值线性增长压过饱和的息损账项)。"""
        assert not self._gate_open(5)
        assert not self._gate_open(7)
        assert self._gate_open(14)
        assert self._gate_open(17)

    def test_slot_value_is_not_threshold(self):
        """槽位数值不再是比较项(判别锁):注入 0.0 + 长视界仍开 / 注入
        1000 + 短视界仍关——比较项=帧级 V̄_net(r),槽位只承载开闸。"""
        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=0.0, injected_form=True))
            st, sess = self._frame(14)
            assert any(isinstance(a, RefreshShop) for a in _decide(st, sess))
        finally:
            provisional.reset('V_GAP')
        provisional.reset('V_GAP')
        try:
            provisional.inject('V_GAP', provisional.CalibValue(
                value=1000.0, injected_form=True))
            st, sess = self._frame(5)
            assert not [a for a in _decide(st, sess)
                        if isinstance(a, RefreshShop)]
        finally:
            provisional.reset('V_GAP')
