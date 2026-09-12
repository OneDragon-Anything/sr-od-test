"""标定批锁(T-278 两段 + T-214 值域守卫,ADR-0639)。

设计出处 = ``.debug/temp/currency_war/T-278-标定设计.md`` + ADR-0639;
正本 = math_proofs P38 §推导⑤层(金位递推显式定义 + B<0 分支 +
升级金买牌 XP 抵扣)/ P76 §3.4(ε₂ 二阶带)+ §4.4(夹界余量)+
§7 #1(Δ 值因子挂 V_ms 同源)。

数值锚纪律:递推公式在测试内按 P38 原式独立重推(kernel 原语直调,
锁公式不锁实现);标定值只锁「注入形态/幂等/值域」,数值巧合的复现
载体 = ``tools/cw/proofs/p76_e2_band_check.py``(确定性包络重算)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_shop_odds import SHOP_SLOTS
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_CLICK_COST_FALLBACK,
    cap_resolved_of_session,
    get_node_goal,
    interest,
    round_base_income,
    saturation_line,
    streak_gold,
)
from sr_od.application.currency_war.kernel.cw_plane_table import r_remaining
from sr_od.application.currency_war.kernel.cw_state import (
    XP_TO_NEXT_LEVEL,
    GameState,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    proof,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    calibration,
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    budget,
    odds,
)

_COMP = COMP_LIBRARY[0]          # 列车同行,form_tiers = {'列车同行': 4}


def _session(target: object = _COMP) -> SimpleNamespace:
    """桩 session(策略态经 ``state_of`` 惰建载体,与生产读口同源)。"""
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = target
    return s


@pytest.fixture(autouse=True)
def _clean_slots():
    """provisional 槽位全局态隔离(测试纪律:改全局态必须复原)。"""
    provisional.reset()
    yield
    provisional.reset()


# ===== ① P38 ⑤层金位递推(budget.py 单一源)=====

def _recalc_plan(state: GameState, session: SimpleNamespace,
                 purchase: float, missing: int) -> tuple[int, int, bool]:
    """P38 ⑤层原式独立重推(kernel 原语直调;与被测实现零共享代码):
    返回 (R, int(B), B<0)。不动点按同款种子与保守端规则重演。"""
    plane = state.plane
    round_num = state.round_num
    gold = state.gold
    cap = cap_resolved_of_session(session)
    floor = saturation_line(cap)
    refresh_cost = state.shop_refresh_cost or 2
    t_horizon = max(0, r_remaining(session, plane, round_num))
    lvl = budget.next_level_xp_cost(state, missing)
    streak_term = (streak_gold(state.streak)
                   if isinstance(state.streak, int) and state.streak > 0
                   else budget.STREAK_PLAN_MEDIAN)

    def b_of(r_plan: int) -> float:
        g = float(gold)
        inc = 0.0
        it_total = 0.0
        for i in range(1, t_horizon + 1):
            base = round_base_income(round_num + i)
            it = interest(g, cap)
            inc += base + streak_term
            it_total += it
            spend = (purchase / t_horizon + refresh_cost * r_plan / t_horizon
                     + (lvl if i == 1 else 0.0))
            g = g + base + streak_term + it - spend
        return gold - floor + inc + it_total - purchase - lvl

    r_prev = max(0, (gold - floor) // refresh_cost)
    r_next = max(0, int(b_of(r_prev)) // refresh_cost) \
        if b_of(r_prev) > 0 else 0
    for _ in range(4):
        if r_next == r_prev:
            break
        r_prev, r_next = r_next, (max(0, int(b_of(r_next)) // refresh_cost)
                                  if b_of(r_next) > 0 else 0)
    r_final = min(r_prev, r_next)
    b_final = b_of(r_final)
    return r_final, int(b_final), b_final < 0


class TestP38BudgetRecursion:

    def test_budget_formula_and_fixed_point(self):
        """递推公式锁:B/RC 逐位等于测试内 P38 原式独立重推(种子 =
        静态口径,不动点保守端同规则)。"""
        sess = _session()
        st = GameState(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        plan = budget.p38_budget_recursion(st, sess, purchase_cost=11.0,
                                           missing_copies=4)
        r, b, exhausted = _recalc_plan(st, sess, 11.0, 4)
        assert plan.refreshes == r
        assert plan.budget == b
        assert plan.exhausted is exhausted is False

    def test_exhausted_domain_cards_unaffordable(self):
        """B<0 分支(P38「买到即计数前提破产」):巨额缺口 + 低金 ⇒
        exhausted=True / R=0 / B<0。"""
        sess = _session()
        st = GameState(gold=30, level=7, round_num=3, plane=1, board={},
                       shop=[])
        plan = budget.p38_budget_recursion(st, sess, purchase_cost=1000.0,
                                           missing_copies=5)
        assert plan.exhausted is True
        assert plan.refreshes == 0
        assert plan.budget < 0

    def test_monotone_in_gold(self):
        """P38 单调性(G↑ → R↑ 不减;证据门硬要求的过程量面)。"""
        sess = _session()
        plans = []
        for gold in (40, 60, 90, 130):
            st = GameState(gold=gold, level=7, round_num=3, plane=1,
                           board={}, shop=[])
            plans.append(budget.p38_budget_recursion(
                st, sess, purchase_cost=11.0, missing_copies=4))
        rs = [p.refreshes for p in plans]
        assert rs == sorted(rs)

    def test_levelup_schedule_condition_and_deduction(self):
        """升级金 = 日程条件 × XP 抵扣:日程(target ≤ 当前)不扣;
        追级帧按 ⌈(need−cur−4·Σm)⁺/4⌉×单击价,买牌 XP 抵扣生效。"""
        st_stay = GameState(gold=60, level=7, round_num=3, plane=1,
                            board={}, shop=[])
        # 日程先验 _expected_level(3, P1)=5 ≤ 7 ⇒ 视界内无升级
        assert get_node_goal(1, 3).target_level <= 7
        assert budget.next_level_xp_cost(st_stay, 4) == 0
        st_push = GameState(gold=60, level=4, round_num=3, plane=1,
                            board={}, shop=[])
        # target=5 > 4:need=XP_TO_NEXT_LEVEL[4]=6,cur=0,买 0 张
        # ⇒ clicks=⌈6/4⌉=2,单击价 = 兜底 4
        assert budget.next_level_xp_cost(st_push, 0) \
            == 2 * XP_CLICK_COST_FALLBACK
        # 买牌送 XP 抵扣:2 张 ×4 XP 盖过 need 6 ⇒ 0
        assert budget.next_level_xp_cost(st_push, 2) == 0
        # xp_progress 现读 + 抵扣:lv5(round 6,target 6>5)need20
        # cur4,买 1 张(−4)⇒ remain 12 ⇒ clicks 3 × 兜底 4 = 12
        st_prog = GameState(gold=60, level=5, round_num=6, plane=1,
                            board={}, shop=[])
        st_prog.xp_progress = (4, XP_TO_NEXT_LEVEL[5])
        assert get_node_goal(1, 6).target_level == 6
        assert budget.next_level_xp_cost(st_prog, 1) == 12


# ===== ② T-214 值域守卫(provisional.inject 通道)=====

class TestProvisionalValueGuard:

    def test_delta_domain_positive(self):
        """丁.4 域:Δ≤0 注入必拒(守卫语义见 provisional._VALUE_GUARDS);
        合法正值通过且槽值原样。"""
        for bad in (0.0, -1.0):
            with pytest.raises(ValueError, match='值域守卫'):
                provisional.inject('V_C_MINUS_V_F',
                                   provisional.CalibValue(bad))
        provisional.inject('V_C_MINUS_V_F', provisional.CalibValue(109.0))
        assert provisional.get('V_C_MINUS_V_F').value == 109.0

    def test_e2_probability_band(self):
        """ε₂ 合法域 [0,1](概率尺度):越域必拒,带内通过。"""
        for bad in (-0.1, 1.5):
            with pytest.raises(ValueError, match='值域守卫'):
                provisional.inject('E2_CONCENTRATION_BAND',
                                   provisional.CalibValue(bad))
        provisional.inject('E2_CONCENTRATION_BAND',
                           provisional.CalibValue(0.46))
        assert provisional.get('E2_CONCENTRATION_BAND').value == 0.46

    def test_unregistered_slots_keep_semantics(self):
        """未登记守卫的槽位 = 既有语义不变(无值域知识不装假守卫):
        THETA 仍接受任意值。"""
        provisional.inject('THETA', provisional.CalibValue(-7.0))
        assert provisional.get('THETA').value == -7.0

    def test_reset_clears(self):
        """注入后 reset 复原(测试隔离契约;None = fail-closed 缺省)。"""
        provisional.inject('E2_CONCENTRATION_BAND',
                           provisional.CalibValue(0.1))
        provisional.reset()
        assert provisional.get('E2_CONCENTRATION_BAND') is None


# ===== ③ 标定注入(calibration.apply)=====

class TestCalibrationApply:

    def test_apply_injects_calibrated_values(self):
        """apply 注入 Δ/ε₂ 两槽:值与 CI 逐字段(标定值推导链见
        calibration 模块 docstring 与 ADR-0639;数值巧合复现 =
        p76_e2_band_check.py)。"""
        assert provisional.get('V_C_MINUS_V_F') is None
        calibration.apply()
        delta = provisional.get('V_C_MINUS_V_F')
        assert delta is not None
        assert (delta.value, delta.ci_lo, delta.ci_hi) == (122.0, 0.0, 260.0)
        e2 = provisional.get('E2_CONCENTRATION_BAND')
        assert e2 is not None
        assert e2.value == 0.65

    def test_apply_idempotent_never_overwrites(self):
        """幂等申报:槽已有时 apply 不覆写(sim A/B 重注入优先);
        空槽照常补齐(两槽互不影响)。"""
        provisional.inject('V_C_MINUS_V_F', provisional.CalibValue(7.0))
        calibration.apply()
        assert provisional.get('V_C_MINUS_V_F').value == 7.0
        assert provisional.get('E2_CONCENTRATION_BAND').value == 0.65

    def test_e2_band_domain_fail_closed(self, monkeypatch):
        """ε₂ 辖域检查(r1 返工:带外 fail-closed,P76 丙.4「带外
        不声明」落码):强制辖域 = 注册表有界维(m/r_rem;R 维全轴
        数值验证覆盖,不作强制)。谓词格 = 两维逐维出格即 False;
        积分格 = monkeypatch 收紧 needs 域后,真实帧(m≥域值)出
        unavailable[e2_domain](needs 上界系注册表量,域外不可自然
        构造,以域收紧模拟注册表漂移)。"""
        assert calibration.band_in_domain(6, 27) is True
        assert calibration.band_in_domain(7, 10) is False   # m 出 needs 域
        assert calibration.band_in_domain(3, 28) is False   # r_rem 出日程域
        calibration.apply()
        sess = _session()
        st = GameState(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        monkeypatch.setattr(calibration, 'E2_DOMAIN_M_MAX', 3)
        _missing, _trials, frame = proof.assemble_lock_frame(st, sess)
        assert frame.band_domain_ok is False   # 列车同行缺 4 张 > 3
        ok, reason = proof.evaluate_evidence_gate(st, sess)
        assert ok is False
        assert 'e2_domain' in reason, reason

    def test_e2_band_domain_in_domain_frame_ok(self):
        """域内常规帧不触带外成因(与上锁对偶,防守卫过宽)。"""
        calibration.apply()
        sess = _session()
        st = GameState(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        _missing, _trials, frame = proof.assemble_lock_frame(st, sess)
        assert frame.band_domain_ok is True
        _ok, reason = proof.evaluate_evidence_gate(st, sess)
        assert 'e2_domain' not in reason, reason

    def test_shadow_causes_after_apply(self):
        """注入后影子分键:unavailable 成因恰 = {o_plus, d_death}
        (delta/e2 成因消失;门恒不可评语义不变,ADR-0637 敞口①兑现
        ——判读禁把 unavailable 读成门判负)。"""
        calibration.apply()
        sess = _session()
        st = GameState(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        ok, reason = proof.evaluate_evidence_gate(st, sess)
        assert ok is False
        assert reason.startswith('sandwich_unavailable')
        ct = state_of(sess).cw4_counters
        assert ct['evidence_gate_unavailable'] == 1
        for cause in ('o_plus', 'd_death'):
            assert ct[f'evidence_gate_unavailable_{cause}'] == 1, cause
        for gone in ('delta', 'e2'):
            assert f'evidence_gate_unavailable_{gone}' not in ct, gone


# ===== ④ 装配试验数升级(assemble_lock_frame × ⑤层)=====

class TestAssembleTrialsUpgrade:

    def _expected_purchase(self, comp, st: GameState) -> tuple[float, int]:
        """缺口件期望购买成本与张数的独立重推(公开单一源直调:
        tier_progress 缺口 × slot_q_tag_by_cost 分费档概率加权单价)。"""
        from sr_od.application.currency_war.kernel import cw_line_switch
        prog = cw_line_switch.tier_progress(comp, _bridge(st))
        level = st.level
        purchase = 0.0
        copies = 0
        for tag, (need_t, held_t, shelf_t) in prog.items():
            m = need_t - held_t - shelf_t
            if m <= 0:
                continue
            bd = odds.slot_q_tag_by_cost(tag, level, {}, {})
            q = sum(bd.values())
            if q <= 0 or not bd:
                continue
            purchase += m * sum(c * p_c for c, p_c in bd.items()) / q
            copies += m
        return purchase, copies

    def test_trials_match_recursion_plan(self):
        """试验数 = SHOP_SLOTS×(R_全局 + ⑤层递推 R):plan 输入
        (期望购账/张数)由公开单一源独立重推后直调递推,与装配
        输出逐位一致。"""
        sess = _session()
        st = GameState(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        purchase, copies = self._expected_purchase(_COMP, st)
        plan = budget.p38_budget_recursion(st, sess, purchase, copies)
        _missing, trials, _frame = proof.assemble_lock_frame(st, sess)
        r_rem = r_remaining(sess, 1, 3)
        assert not plan.exhausted
        assert trials == SHOP_SLOTS * max(0, r_rem + plan.refreshes)

    def test_exhausted_frame_zero_probability(self):
        """B<0 域装配:trials=0 且 P=e_p_next=0(P38「买到即计数前提
        破产」;本域耗尽的是购卡预算,刷新预算解耦语义不回归)。
        场景 = P3 末段赤贫帧(T≈1,收入远小于 floor 储备+缺口购账);
        标定注入先行(生产姿态 = 策略器构造即 apply)。
        门内落点申报(r1 修正,原 below_nec 表述不实):exhausted ⇒
        e_p_next=0 ⇒ θ̂_nec=0,`p<th_nec` 恒假 ⇒ 实际落 sandwich_band,
        典型格落 suff 截 0=无条件放行锁——P=0 域 suff 放行的显式裁决
        已列入装配批义务清单(ADR-0639 §4),禁靠截 0 语义默认放行。
        影子期(P76 修正 5 形态)o_plus/d_death 未装配 ⇒ 门恒不可评,
        实质裁决同样到装配批才可见;本域可观测语义 = 装配零试验 +
        unavailable 成因 {o_plus,d_death}。"""
        calibration.apply()
        sess = _session()
        st = GameState(gold=0, level=7, round_num=8, plane=3, board={},
                       shop=[])
        missing, trials, frame = proof.assemble_lock_frame(st, sess)
        assert missing
        assert trials == 0
        assert frame.e_p_next == 0.0
        ok, reason = proof.evaluate_evidence_gate(st, sess)
        assert ok is False
        assert reason.startswith('sandwich_unavailable'), reason
        ct = state_of(sess).cw4_counters
        assert ct.get('evidence_gate_unavailable_o_plus') == 1
        assert ct.get('evidence_gate_unavailable_d_death') == 1
