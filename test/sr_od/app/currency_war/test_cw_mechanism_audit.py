"""机制常数核对器测试(redesign 23 号;ADR-0177):四审计的判定语义。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_mechanism_audit import (  # noqa: E402
    audit_base_income,
    audit_interest_threshold,
    audit_refresh_cost,
    audit_xp_per_buy,
)


def _row(run: str, rnd: int, gold: int, actions: list[dict] | None = None,
         xp=(0, 4), level=4, streak=None) -> dict:
    return {'run_id': run, 'state': {'round_num': rnd, 'gold': gold,
                                     'xp_progress': list(xp), 'level': level,
                                     'streak': streak},
            'actions': actions or []}


def test_refresh_cost_consistent() -> None:
    """同节点行对 + RefreshShop 前缀:gold 差−其他花费 = 单刷费 → est=2 一致。"""
    rows = []
    for i in range(6):
        rows.append(_row('r', 1, 50 - i * 2, [{'__type__': 'RefreshShop', 'cost': 2}]))
    a = audit_refresh_cost(rows)
    assert a.verdict == 'consistent' and a.estimate == 2.0


def test_refresh_cost_underpowered() -> None:
    """行对不足 → underpowered(不误判)。"""
    rows = [_row('r', 1, 50, [{'__type__': 'RefreshShop'}])]
    assert audit_refresh_cost(rows).verdict == 'underpowered'


def test_xp_per_buy_snapshot_confounded() -> None:
    """主峰 0(xp_progress=买后快照)+ 次峰 4 → confounded(口径差非 refute)。"""
    rows = []
    for _ in range(6):
        rows.append(_row('r', 1, 30, [{'__type__': 'BuyCard', 'card': {'cost': 1}}], xp=(4, 8)))
        rows.append(_row('r', 1, 29, xp=(4, 8)))   # Δxp=0(快照已含买牌 XP)
    rows.append(_row('r', 1, 28, [{'__type__': 'BuyCard', 'card': {'cost': 1}}], xp=(0, 4)))
    rows.append(_row('r', 1, 27, xp=(4, 8)))   # 次峰:Δ=4/1
    a = audit_xp_per_buy(rows)
    assert a.verdict == 'confounded'


def test_xp_per_buy_consistent_true_delta() -> None:
    """Δxp/买数 主峰=注册值 4 → consistent(真增量口径)。"""
    rows = []
    for i in range(6):
        rows.append(_row('r', 1, 30, [{'__type__': 'BuyCard', 'card': {'cost': 1}}], xp=(0, 16)))
        rows.append(_row('r', 1, 29, [], xp=(4, 16)))
    a = audit_xp_per_buy(rows)
    assert a.verdict == 'consistent' and a.estimate == 4.0


def test_base_income_confounded_on_upward_bias() -> None:
    """跨节点零花费行对整体上偏(est=Δ−interest>5)→ confounded(未观收入混入,非 base>5)。

    gb=20(interest=2):ga=29/30/31 → est=7/8/9(5+连胜 2/3/4)——streak=None 剔不掉。"""
    rows = []
    for ga in (29, 30, 31):
        for _ in range(3):
            rows.append(_row('r', 1, 20, []))
            rows.append(_row('r', 2, ga, []))
    a = audit_base_income(rows)
    assert a.verdict == 'confounded'


def test_base_income_consistent_clean_window() -> None:
    """零连胜(streak≤1)+ est=Δgold−interest=5 → consistent(gb=20:ga=27 → 27-20-2=5)。"""
    rows = []
    for i in range(6):
        rows.append(_row('r', 1 + i, 20, [], streak=0))
        rows.append(_row('r', 2 + i, 27, []))
    a = audit_base_income(rows)
    assert a.verdict == 'consistent' and a.estimate == 5.0


def test_interest_threshold_confounded_positive_bias() -> None:
    """gb≥50 段正偏差主导(est_int=Δ−5>0 多数)→ confounded 非 refuted。"""
    rows = []
    for i in range(8):
        rows.append(_row('r', 1 + i, 60, [], streak=0))
        rows.append(_row('r', 2 + i, 72, []))   # est_int=72-60-5=7>0(boss+2 混入)
    a = audit_interest_threshold(rows)
    assert a.verdict == 'confounded'
