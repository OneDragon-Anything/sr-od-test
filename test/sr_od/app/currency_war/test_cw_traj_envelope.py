"""cw_traj_envelope(32 号形态包络)v0 测试:包络构建(真数据)+ 离群/路由语义(合成)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_traj_envelope import (  # noqa: E402
    Outlier,
    _percentile,
    build_envelope,
    outlier_vector,
    route,
)

_PLAZA = _REPO / '.debug' / 'temp' / 'currency_war' / 'plaza' / 'lineups_HotHard.jsonl'


def test_envelope_builds_from_real_data() -> None:
    """真数据构建:三阶段 × 六维度有分布且**有序**(百分位查表前提);赢家 Early 规模
    落人类带。"""
    if not _PLAZA.exists():
        return  # 数据不在盘的环境跳过(语料在 .debug 不入 git)
    env = build_envelope(_PLAZA)
    for stage in ('Early', 'Middle', 'Final'):
        assert 'board_size' in env[stage] and len(env[stage]['board_size']) > 100
        vals = env[stage]['board_size']
        assert vals == sorted(vals), '包络值表须有序(百分位二分前提)'
        assert 2 <= vals[len(vals) // 2] <= 8


def test_percentile_semantics() -> None:
    """百分位:有序表二分;端点语义。"""
    assert _percentile([1, 2, 3, 4], 0) == 0.0
    assert _percentile([1, 2, 3, 4], 2.5) == 0.5
    assert _percentile([1, 2, 3, 4], 5) == 1.0
    assert _percentile([], 3) == 0.5


def test_outlier_vector_m25_spread() -> None:
    """M25 场景:spread 形态(8 阵营各 1)在人类包络外 → 高侧离群检出。"""
    env = {'Early': {'board_size': sorted([5, 5, 6, 6, 7, 7, 7, 8] * 20),
                     'trait_count': sorted([2, 2, 3, 3, 3, 4] * 20)}}
    current = {'Early': {'board_size': 8, 'trait_count': 8}}   # 8 羁绊激活 = 远超包络
    outs = outlier_vector(env, current)
    assert any(o.dim == 'trait_count' and o.side == 'high' for o in outs)


def test_route_whitelist_and_investigate() -> None:
    """认识论路由:白名单豁免(解释义务已履行)/ 其余进调查队列。"""
    outs = [Outlier('board_size', 'Early', 'high', 0.99),
            Outlier('bench_hoard', 'Middle', 'high', 0.99)]
    r = route(outs, whitelist=('bench_hoard',))
    assert [o.dim for o in r['explained']] == ['bench_hoard']
    assert [o.dim for o in r['investigate']] == ['board_size']
    assert route([])['clean']
