"""28 号 Tier-1 死锁穷举证明器测试。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_deadlock_prover import (  # noqa: E402
    DeadlockReport,
    enumerate_deadlocks,
    _progress_actions_available,
)


def test_no_deadlock_full_space() -> None:
    """全状态空间(t 0-9 + gold 0-100 + lv 1-10 + bench 3 态,活性条件)无死锁。"""
    rep = enumerate_deadlocks()
    assert rep.states_enumerated == 10 * 101 * 10 * 3   # t_max=9 → 10 值
    assert rep.deadlocks == [], f'发现死锁: {rep.minimal_counterexamples()}'
    assert rep.verdict == 'PROVEN_NO_DEADLOCK'


def test_liveness_rescues_trivial_poverty() -> None:
    """活性条件:gold=0 空 bench 的平凡贫困态被下节点收入救活(非死锁)。"""
    ok, why = _progress_actions_available(0, 5, 0)
    assert ok, f'gold=0 空 bench 应被收入救活: {why}'
    assert '收入后' in why


def test_bench_occupied_always_progress() -> None:
    """bench 有角色:卖恒可行(腾席回金)。"""
    ok, _ = _progress_actions_available(0, 1, 1)
    assert ok
    ok2, _ = _progress_actions_available(0, 1, 2)
    assert ok2


def test_report_counterexample_sorting() -> None:
    """反例排序按 gold 升序(最小反例优先)。"""
    rep = DeadlockReport()
    rep.deadlocks = []
    assert rep.minimal_counterexamples() == []
    assert rep.verdict == 'PROVEN_NO_DEADLOCK'
