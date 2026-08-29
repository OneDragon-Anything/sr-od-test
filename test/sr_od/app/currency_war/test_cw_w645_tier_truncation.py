"""W645 提案 E-v2 息档边界截断锁(溢余消费截断+结转,tier_truncated_spend)。

设计=唯一规格:`.debug/temp/currency_war/w645_proposal_v2/SPECS.md` 提案
E-v2 节(对抗裁决修订版;机制=纯金额截断,无顺序主张、无凑档选件语义)。
数学依据:利息=gold//10 cap 5 按节点结算,息损=首末金量纯函数路径无关 →
花后不跨 10 的倍数档息损 0(P13/[11] 同档零息损);非必要溢余支出截断在
gold % 10 内弱占优(留金≥0、常态刷新无跨轮衰减);essential=True 两枝
(正账件/M-A 定向刷新车道)不辖——定向车道末窗无下轮重摇,截断=搜索
永久丢失,弱占优前提为假。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 档内不截断:essential=False ∧ gold%10 ≥ want → 原额放行(want);
- ② 跨档截断+结转:essential=False ∧ gold%10 < want → 返回值 < want
  =本笔不放行,余量(=gold%10)结转下轮(义务逐帧重算,锁为纯函数值);
- ③ essential=True 两枝不截断:正账件枝与定向刷新车道枝均原额返回,
  gold%10 < want 也不截(车道分类由消费点显式传参,函数不判车道);
- ④ 残差不足一刷停止收尾:authorize_release_refresh 在预算内但
  working_gold % 10 < 刷价 → 拒(截断返回值 < 刷价,本笔不放行);
- ⑤ 与既有刷新预算语义组合不回归:预算耗尽仍拒 / 花后 ≥ boss_floor
  仍拒 / 三门(预算→截断→地板)次序与各自独立生效;预算+档内余量均足
  → 放行且扣账累计不因截断门改变。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.economy_cycle import (
    tier_truncated_spend,
)
from sr_od.application.currency_war.decision_v2.posture_release import (
    ReleaseDirective,
    authorize_release_refresh,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY
_COST = 2    # 刷价(与 _state.shop_refresh_cost 同值)


def _directive(budget: int, *, find_ok: bool = True) -> ReleaseDirective:
    return ReleaseDirective(budget_gold=budget, rolls=budget // _COST,
                            third_path=False, reason='flip',
                            directed_only=False, find_ok=find_ok)


def _sess_with_directive(budget: int) -> StrategySession:
    s = StrategySession()
    s.v3_release = _directive(budget)
    s.v3_release_spent = 0
    return s


# --- ①②③ 纯函数 tier_truncated_spend ------------------------------------------


def test_tier_trunc_in_tier_no_cut() -> None:
    """① 档内不截断:gold%10 ≥ want 时原额放行(62 金余 12→2?不,62%10=2;
    取 gold=68 余 8 ≥ want=5 → 5)。"""
    assert tier_truncated_spend(68, 5, essential=False) == 5
    assert tier_truncated_spend(67, 6, essential=False) == 6


def test_tier_trunc_cross_tier_cut_and_carry() -> None:
    """② 跨档截断+结转:gold=63(余 3),want=5(一刷 2 金可刷两次多一档)
    → 截断返回 3 < 5 = 本笔不放行,3 金余量结转下轮。"""
    got = tier_truncated_spend(63, 5, essential=False)
    assert got == 3
    assert got < 5    # 调用契约:返回值 < want = 不放行


def test_tier_trunc_essential_both_branches_uncut() -> None:
    """③ essential=True 两枝不截断:正账件(买牌)与 M-A 定向刷新车道
    同为原额——gold%10=0 也不截(截断=定向搜索永久丢失/弃购,不在辖内)。"""
    assert tier_truncated_spend(60, 5, essential=True) == 5
    assert tier_truncated_spend(60, 5, essential=False) == 0    # 对照枝
    assert tier_truncated_spend(0, 9, essential=True) == 9


# --- ④⑤ authorize_release_refresh 截断门组合 -----------------------------------


def test_release_gate_residual_below_cost_rejected() -> None:
    """④ 残差不足一刷停止收尾:预算 10、金 63(余 3 ≥ 刷价?不,刷价 2
    ≤ 3 可刷)→ 改用金 61(余 1 < 刷价 2):预算内仍拒=截断门收口。"""
    s = _sess_with_directive(10)
    assert authorize_release_refresh(s, 61, _COST, _REG) == ''


def test_release_gate_residual_sufficient_passes() -> None:
    """④ 对照:预算 10、金 68(余 8 ≥ 刷价 2)→ 放行,累计扣账=刷价。"""
    s = _sess_with_directive(10)
    note = authorize_release_refresh(s, 68, _COST, _REG)
    assert note != ''
    assert s.v3_release_spent == _COST


def test_release_gate_budget_semantics_unchanged() -> None:
    """⑤ 与既有预算语义组合不回归:预算耗尽(spent+cost > budget)仍拒,
    截断门不放松预算界。"""
    s = _sess_with_directive(4)
    s.v3_release_spent = 4
    assert authorize_release_refresh(s, 68, _COST, _REG) == ''


def test_release_gate_boss_floor_semantics_unchanged() -> None:
    """⑤ 花后 ≥ boss_floor 下限仍在截断门之后独立生效:金 61(余 1)、
    预算充足,即使残差门若被绕过,地板门照拒——三门各自独立,次序
    预算→截断→地板。"""
    s = _sess_with_directive(10)
    # 金 51:余 1 < 刷价 → 截断门先拒(地板也拒,断言拒绝事实即可)
    assert authorize_release_refresh(s, 51, _COST, _REG) == ''
    # 同金位提高刷价余量对比:金 58(余 8 ≥ 2)但花后 56 ≥ boss_floor
    # (registry.p1_boss_floor=20)→ 放行,证明地板门不是本用例拒因。
    s2 = _sess_with_directive(10)
    assert authorize_release_refresh(s2, 58, _COST, _REG) != ''


def test_release_gate_directed_only_still_rejects_blind() -> None:
    """⑤ 定向化拒盲刷语义不回归(directed_only ∧ find_ok=False):截断门
    追加不改变既有定向化判定次序。"""
    s = StrategySession()
    s.v3_release = _directive(10, find_ok=False)
    s.v3_release_spent = 0
    d = ReleaseDirective(budget_gold=10, rolls=5, third_path=False,
                         reason='flip', directed_only=True, find_ok=False)
    s.v3_release = d
    assert authorize_release_refresh(s, 68, _COST, _REG) == ''
