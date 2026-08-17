"""cw_loss_budget(34 号损失预算)测试:符号检验语义 + 报告结构(小 n 快跑)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_loss_budget import (  # noqa: E402
    BudgetReport,
    _sign_test,
    loss_budget,
)


def test_sign_test_semantics() -> None:
    """配对符号检验:C 全胜分歧 → p 极小;无分歧 → p=1。"""
    a = [False] * 8 + [True] * 2
    c = [True] * 8 + [True] * 2      # 8 分歧全利于 C
    assert _sign_test(a, c) < 0.05
    assert _sign_test(a, a) == 1.0


def test_loss_budget_small_n_structure() -> None:
    """小 n(30)快跑:报告结构完整、量纲自洽(decision_gap = win_c − win_a;
    actionable = decision(sim 内 D=C);floor = 1 − win_c)。"""
    rep = loss_budget(n=30, seed0=5000)
    assert isinstance(rep, BudgetReport) and rep.n == 30
    assert abs(rep.decision_gap - (rep.win_c - rep.win_a)) < 1e-4   # round(4) 粒度
    assert abs(rep.actionable_upper - rep.decision_gap) < 1e-4
    assert abs(rep.floor_upper - (1.0 - rep.win_c)) < 1e-4
    assert 0.0 <= rep.sign_test_p <= 1.0
