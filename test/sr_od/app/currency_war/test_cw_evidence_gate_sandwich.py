"""P76 锁线夹界证据门锁(T-124;规约态语义修正,零生产消费点)。

设计出处 = math_proofs **P76**:§4.3/§4.4(锁线一帧临界等式与可计算
夹界 θ̂_suff/θ̂_nec)、§5.5(落码含义:§5.5.2 no_budget 预算解耦/
§5.5.3 序数门 pc>0 升格夹界下界形态)、§7 #1(θ* 点值与数值门禁消费
⇒ 【拟】槽位 None 封印)、A-丁.2(存在性条件与病态域出口)、修正 4
(C 项差分口径 H_{−*})。编排者裁决(进度账本 T-124 行,2026-09-10):
夹界结构+槽位封印形态;A/B 移交接线批同批;本批不接线——evidence_gate
全仓零调用点(P76 修正 5),本批 = 规约态语义修正,零生产行为变化。

数值锚全部走构造参数(锁语义不锁巧合):p_complete([(m,q)],B) 的
P 值由 (m,q,B) 直算,夹界阈值由帧项直算,断言只锁判定与 reason 分键。
"""

import pytest

from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    proof,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.proof import (
    LockSandwichFrame,
)

_MISS = [(1, 0.5)]          # 一张缺口、单格命中 0.5;B=1 ⇒ P=0.5
_BUDGET = 1


def _frame(**over) -> LockSandwichFrame:
    """全装配帧基线:P=0.5/θ̂_suff=0.25/θ̂_nec=0.1(带 Δ=10,ε₂=0 注入)。"""
    fields: dict[str, float | None] = {'e_p_next': 0.3, 'o_plus': 0.5,
                                       'f_plus': 0.5, 'b_plus': 0.5,
                                       'c_hold': 1.0, 'd_death': 1.0}
    fields.update(over)
    return LockSandwichFrame(**fields)


def _inject(delta: float = 10.0, e2: float = 0.0) -> None:
    provisional.inject('V_C_MINUS_V_F', provisional.CalibValue(delta))
    provisional.inject('E2_CONCENTRATION_BAND', provisional.CalibValue(e2))


@pytest.fixture(autouse=True)
def _clean_slots():
    """槽位全局态测试隔离(测试纪律:改全局态必须复原)。"""
    provisional.reset()
    yield
    provisional.reset()


class TestP76SandwichGate:
    """P76 §5.5 夹界形态逐条语义(先红后绿;出处见模块 docstring)。"""

    def test_complete_pass_unchanged(self) -> None:
        """无缺口 ⇒ 直接过门(P76 §5.5 未触及面;旧语义保持)。"""
        ok, reason = proof.evidence_gate([], 0, frame=None)
        assert ok is True
        assert reason == 'complete'

    def test_slots_registered_default_none(self) -> None:
        """Δ/ε₂ 两槽位在册且缺省 None(§7 #1 fail-closed 缺省)。"""
        names = provisional.slot_names()
        assert 'V_C_MINUS_V_F' in names
        assert 'E2_CONCENTRATION_BAND' in names
        assert provisional.get('V_C_MINUS_V_F') is None
        assert provisional.get('E2_CONCENTRATION_BAND') is None

    def test_no_budget_veto_retired(self) -> None:
        """§5.5.2 预算解耦:零预算不再构成否决——走夹界路径出
        必要侧拒,reason 词表无 no_budget(P=0 < θ̂_nec=0.1)。"""
        _inject()
        ok, reason = proof.evidence_gate(_MISS, 0, frame=_frame())
        assert ok is False
        assert 'no_budget' not in reason
        assert reason.startswith('sandwich_below_nec')

    def test_budget_enters_trials_only(self) -> None:
        """§5.5.2 正证:预算只作试验数条件——同帧同槽位,B=1 ⇒ P=0.5 ≥
        θ̂_suff=0.25 过门;B=0 ⇒ P=0 < θ̂_nec 必要侧拒(两臂均夹界键)。"""
        _inject()
        ok1, reason1 = proof.evidence_gate(_MISS, 1, frame=_frame())
        assert ok1 is True
        assert reason1.startswith('sandwich_suff')
        ok0, reason0 = proof.evidence_gate(_MISS, 0, frame=_frame())
        assert ok0 is False
        assert reason0.startswith('sandwich_below_nec')

    def test_default_frame_sealed_not_ordinal(self) -> None:
        """§5.5.3:无帧(接线批未装配)⇒ 不可评,**不是**旧序数 pc>0 放行
        (budget>0 帧旧实现过门——本锁变异红证序数回归)。"""
        ok, reason = proof.evidence_gate(_MISS, _BUDGET, frame=None)
        assert ok is False
        assert reason.startswith('sandwich_unavailable')

    def test_sealed_delta_slot_cause(self) -> None:
        """§7 #1:Δ 槽位 None ⇒ 门整体不可评 + delta 成因分键。"""
        ok, reason = proof.evidence_gate(_MISS, _BUDGET, frame=_frame())
        assert ok is False
        assert reason.startswith('sandwich_unavailable')
        assert 'delta' in reason

    def test_sealed_frame_field_causes(self) -> None:
        """帧字段任一 None ⇒ 不可评 + 字段名成因分键(归因可辨,
        禁伞形吞因)。"""
        _inject()
        for cause, over in (('e_p_next', {'e_p_next': None}),
                            ('o_plus', {'o_plus': None}),
                            ('c_hold', {'c_hold': None}),
                            ('d_death', {'d_death': None})):
            ok, reason = proof.evidence_gate(
                _MISS, _BUDGET, frame=_frame(**over))
            assert ok is False, cause
            assert reason.startswith('sandwich_unavailable'), cause
            assert cause in reason, (cause, reason)

    def test_delta_non_positive_out_of_lemma_domain(self) -> None:
        """丁.4 引理域 V_C>V_F:Δ≤0 系域外输入 ⇒ 不可评(fail-closed),
        禁用非正分母出阈值。"""
        _inject(delta=0.0)
        ok, reason = proof.evidence_gate(_MISS, _BUDGET, frame=_frame())
        assert ok is False
        assert reason.startswith('sandwich_unavailable')
        assert 'delta_non_positive' in reason

    def test_sufficiency_pass_lock_not_worse(self) -> None:
        """§4.4 充分侧:P ≥ θ̂_suff ⇒ 过门(锁不劣)。基线帧
        θ̂_suff=0.3+(1.5−2)/10=0.25,P=0.5。"""
        _inject()
        ok, reason = proof.evidence_gate(_MISS, _BUDGET, frame=_frame())
        assert ok is True
        assert reason.startswith('sandwich_suff')

    def test_necessity_fail(self) -> None:
        """§4.4 必要侧(右侧下界 O=F=B=0):P < θ̂_nec ⇒ 拒。
        θ̂_nec=0.3−(1+1)/10=0.1;P=0.05。"""
        _inject()
        ok, reason = proof.evidence_gate([(1, 0.05)], _BUDGET,
                                         frame=_frame())
        assert ok is False
        assert reason.startswith('sandwich_below_nec')

    def test_band_undetermined_fails_closed(self) -> None:
        """两截断之间 = 夹界未决 ⇒ 不过门(维持现状,旧 fail 方向)。"""
        _inject()
        ok, reason = proof.evidence_gate([(1, 0.2)], _BUDGET,
                                         frame=_frame())
        assert ok is False
        assert reason.startswith('sandwich_band')

    def test_domain_alpha_clamp_zero_unconditional_lock(self) -> None:
        """§4.4 闭式解 <0(域 α 深处)⇒ 截 0 = 无条件锁:P=0.05 也过门
        (戊.2 域 α「应最早锁」的结构涌现)。"""
        _inject()
        ok, reason = proof.evidence_gate([(1, 0.05)], _BUDGET,
                                         frame=_frame(o_plus=0.0, f_plus=0.0,
                                                      b_plus=0.0, c_hold=5.0,
                                                      d_death=5.0))
        assert ok is True
        assert reason.startswith('sandwich_suff')

    def test_e2_inflates_sufficiency_bound(self) -> None:
        """§4.4「ε₂ 并入夹界余量」:ε₂=0.3 抬升 θ̂_suff 至 0.55 > P=0.5
        ⇒ 充分侧不再放行,落带内(保守向)。"""
        _inject(e2=0.3)
        ok, reason = proof.evidence_gate(_MISS, _BUDGET, frame=_frame())
        assert ok is False
        assert reason.startswith('sandwich_band')

    def test_pathological_exit_a_ding2(self) -> None:
        """A-丁.2 病态域(suff 截断前原始值 >1,夹界空)⇒ 出口=不进单线
        锁判定(§4.4 处置),独立分键 sandwich_pathological。"""
        _inject()
        ok, reason = proof.evidence_gate(_MISS, _BUDGET,
                                         frame=_frame(o_plus=50.0))
        assert ok is False
        assert reason.startswith('sandwich_pathological')
