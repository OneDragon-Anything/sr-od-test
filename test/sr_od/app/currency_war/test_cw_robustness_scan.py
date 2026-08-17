"""28 号 Tier-2 常数区间稳健性扫描测试。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_robustness_scan import (  # noqa: E402
    scan_income,
    scan_refresh_cost,
)


def test_refresh_cost_robust() -> None:
    """无死锁结论在刷新费 1-4 全区间稳健。"""
    rep = scan_refresh_cost()
    assert rep.verdict == 'ROBUST', f'翻转点: {[(f.constant, f.value) for f in rep.flips]}'


def test_income_robust() -> None:
    """无死锁结论在 base income 3-7 全区间稳健(低收入环境也不出死锁)。"""
    rep = scan_income()
    assert rep.verdict == 'ROBUST', f'翻转点: {[(f.constant, f.value) for f in rep.flips]}'
