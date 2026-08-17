"""cw_experiment_mux(29 号实验多路复用)v0 测试:J1 债务审计 + J2 吞吐对拍 + 污染哨兵。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_experiment_mux import (  # noqa: E402
    DEBT_LEDGER,
    ExperimentSpec,
    compatible,
    debt_audit,
    pollution_check,
    schedule_package,
)


def test_j1_debt_audit_passes() -> None:
    """J1:15+ 项债务登记 → 全兼容类占比 ≥70%、行为域 ≤5(复用主张的前提)。"""
    rep = debt_audit()
    assert rep['j1_verdict'] == 'pass', rep
    assert rep['compatible_share'] >= 0.7
    assert rep['n_domains'] <= 5


def test_j2_throughput_simulation() -> None:
    """J2:同 100 局预算,分层重叠调度 vs 串行 FIFO,完成判据数 ≥3×。

    仿真:每局一个包(正交叠加),各实验按 n_runs 计满即 done;串行=每局只排队首。"""
    queue = list(DEBT_LEDGER)

    def _run(scheduler) -> int:
        remaining = {e.exp_id: e.n_runs for e in queue}
        specs = {e.exp_id: e for e in queue}
        done = 0
        for run_i in range(100):
            live = [e for e in queue if remaining[e.exp_id] > 0]
            if not live:
                break
            pkg_ids = scheduler(live, run_i)
            for eid in pkg_ids:
                remaining[eid] -= 1
                if remaining[eid] == 0:
                    done += 1
        return done

    mux_done = _run(lambda live, i: schedule_package(live, i))
    fifo_done = _run(lambda live, i: [live[0].exp_id])
    assert mux_done >= fifo_done
    # 吞吐倍数:完成判据数比 ≥3(全兼容类同局叠加)
    assert mux_done >= 3 * max(1, fifo_done), f"复用倍数不足: {mux_done} vs {fifo_done}"


def test_compatible_semantics() -> None:
    """正交判定:active 行为域相交 → 互斥;shadow 空集 → 与一切兼容;排斥对 → 不兼容。"""
    a1 = ExperimentSpec('a1', '', 'active', frozenset({'horizon_seam'}), (), 10)
    a2 = ExperimentSpec('a2', '', 'active', frozenset({'horizon_seam', 'x'}), (), 10)
    a3 = ExperimentSpec('a3', '', 'active', frozenset({'bundle_seam'}), (), 10)
    sh = ExperimentSpec('sh', '', 'shadow', frozenset(), (), 10)
    assert not compatible(a1, a2)
    assert compatible(a1, a3)
    assert compatible(sh, a1)
    assert not compatible(DEBT_LEDGER[-1], DEBT_LEDGER[-2])   # drift_inject × lambda_j0


def test_pollution_sentinel() -> None:
    """污染哨兵:共因变量对被显式记账(block 效应提示)。"""
    a = ExperimentSpec('a', '', 'shadow', frozenset(), ('win_rate', 'x'), 10)
    b = ExperimentSpec('b', '', 'passive', frozenset(), ('win_rate',), 10)
    flags = pollution_check([a, b])
    assert flags and flags[0]['shared_metrics'] == ['win_rate']


def test_small_queue_passthrough() -> None:
    """队列 <3:直通全排(不做无谓调度)。"""
    q = [ExperimentSpec('only', '', 'shadow', frozenset(), (), 5),
         ExperimentSpec('two', '', 'passive', frozenset(), (), 5)]
    assert schedule_package(q, 0) == ['only', 'two']
