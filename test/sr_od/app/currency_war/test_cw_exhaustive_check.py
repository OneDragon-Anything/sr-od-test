"""cw_exhaustive_check(28 号 Tier-1 穷举检查)测试:J2 absence 证明 + 判定器灵敏度。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_exhaustive_check import (  # noqa: E402
    check_absence,
    deadlock_states,
    progress_feasible,
)


def test_j2_absence_proof_current_gates() -> None:
    """J2②:现行门族 + 精确机制(含收入下界)下,金零进展死锁全空间不可达。"""
    rep = check_absence()
    assert rep.absence_proven, f"死锁可达: {rep.deadlock_samples}"
    assert rep.n_states > 9000, "扫描空间完整(gold×level×hp×bench)"


def test_detector_sensitivity_synthetic_deadlock() -> None:
    """判定器灵敏度(防恒真):构造假门(买被挡+钱不够升与刷)→ 死锁被检出。"""
    # gold=0:买(≥1)不可、刷(≥2)不可、升不可 → 死锁(收入下界收入 5+息 → g=5 时仍可买)
    assert not progress_feasible(0, 5, 50)
    # 收入下界救活:gold=0 + income 5 → g_eff=5 → 可买
    assert progress_feasible(5, 5, 50)


def test_bench_full_still_has_refresh_edge() -> None:
    """bench 满不构成死锁:刷/升出边仍在。"""
    assert progress_feasible(30, 5, 50, bench_full=True)


def test_income_floor_rescues_zero_gold() -> None:
    """纯零金态被收入下界拯救(金零进展实锤 = 收入也断的门,现行机制收入恒在)。"""
    rep = deadlock_states(include_income=False)
    # 不含收入时 gold<1 的态全是死锁(判定器能看见);含收入后被救 —— 两态对比证判定器在咬
    assert rep.n_deadlock > 0
    rep2 = deadlock_states(include_income=True)
    assert rep2.n_deadlock < rep.n_deadlock
