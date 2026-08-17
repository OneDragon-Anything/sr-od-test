"""cw_time_ledger(45 号时间经济 J0)测试:wall-clock 重建 + 台账语义。"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_time_ledger import (  # noqa: E402
    RunWallClock,
    run_wallclock,
    throughput_ledger,
)


def _rows(spec: list[tuple[str, str, int]]) -> list[dict]:
    """(run_id, ts_iso, hp_after) → outcomes 行。"""
    return [{'run_id': rid, 'ts': ts, 'hp_after': hp} for rid, ts, hp in spec]


def test_run_wallclock_rebuild() -> None:
    """ts 序列 → 单局记录:时长/节点数/间隔;乱序行按 ts 排序。"""
    t0 = datetime(2026, 8, 17, 12, 0, 0)
    spec = [
        ('r1', (t0 + timedelta(seconds=120)).isoformat(), 90),          # 乱序放前
        ('r1', t0.isoformat(), 100),
        ('r1', (t0 + timedelta(seconds=300)).isoformat(), 0),
    ]
    runs = run_wallclock(_rows(spec))
    assert len(runs) == 1
    r = runs[0]
    assert r.n_nodes == 3 and r.duration_min == 5.0
    assert r.node_intervals == [120.0, 180.0]
    assert r.dead_run


def test_ledger_dead_share_semantics() -> None:
    """台账:死局打完份额(wall-clock 口径)+ J1 判读。"""
    t0 = datetime(2026, 8, 17, 12, 0, 0)
    spec = []
    # 死局长局 30min + 活局短局 10min×3 → 死局 wall-clock 份额 50%
    spec += [('dead', t0.isoformat(), 100),
             ('dead', (t0 + timedelta(minutes=30)).isoformat(), 0)]
    for k in range(3):
        rid = f'live{k}'
        spec += [(rid, (t0 + timedelta(minutes=k * 11)).isoformat(), 100),
                 (rid, (t0 + timedelta(minutes=k * 11 + 10)).isoformat(), 50)]
    runs = run_wallclock(_rows(spec))
    led = throughput_ledger(runs)
    assert led['n_runs'] == 4
    assert abs(led['dead_run_share']['share_of_wallclock'] - 0.5) < 0.01
    assert led['j1_prediction'] == '主杠杆成立'


def test_ledger_degrade_when_no_dead_runs() -> None:
    """全活局:死局份额 0 → J1 判读降级(自我证伪条款的机器判定)。"""
    t0 = datetime(2026, 8, 17, 12, 0, 0)
    spec = []
    for k in range(4):
        rid = f'w{k}'
        spec += [(rid, (t0 + timedelta(minutes=k * 12)).isoformat(), 100),
                 (rid, (t0 + timedelta(minutes=k * 12 + 10)).isoformat(), 30)]
    led = throughput_ledger(run_wallclock(_rows(spec)))
    assert led['dead_run_share']['share_of_wallclock'] == 0.0
    assert led['j1_prediction'] == '主杠杆失效→层降级报表'
