"""cw_reentry(31 号重入层)v0 测试:J1 热重入精确恢复 + 三级判定 + 加宽语义 + rng 重放。"""
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_reentry import (  # noqa: E402
    JournalEvent,
    project,
    reentry_level,
    replay_rng,
    widen_beliefs_on_gap,
)


def _ev(family, kind, rnd, **payload) -> JournalEvent:
    return JournalEvent(family, kind, 'r', rnd, payload)


def test_j1_hot_reentry_exact_recovery() -> None:
    """J1:合成 journal 前缀 → 投影逐字段恢复(obs 最后值 + action 重放)。"""
    events = [
        _ev('observation', 'obs:state', 1, gold=30, hp=80, level=4, plane=1),
        _ev('action', 'action:BuyCard', 1, char='A'),
        _ev('action', 'action:BuyCard', 2, char='B'),
        _ev('action', 'action:DeployMove', 2, bench_idx=0, faction='仙舟'),
        _ev('observation', 'obs:state', 3, gold=22, hp=70, level=5, plane=1),
        _ev('rng', 'rng:draw', 3),
    ]
    w = project(events)
    assert w['gold'] == 22 and w['hp'] == 70 and w['level'] == 5
    assert w['bench'] == ['B'] and w['deployed'] == ['A']
    assert w['board'] == {'仙舟': 1}
    assert w['rng_consumed'] == 1 and w['last_round'] == 3


def test_reentry_levels() -> None:
    """三级判定:冷(空)/热(覆盖当前)/温(缺口)。"""
    assert reentry_level({}, 5) == 'cold'
    evs = {1: [_ev('observation', 'obs:x', 1)], 2: [_ev('observation', 'obs:x', 2)]}
    assert reentry_level(evs, 2) == 'hot'
    assert reentry_level(evs, 5) == 'warm'


def test_widen_beliefs_semantics() -> None:
    """加宽语义:缺口轮数 → 方差乘子(信念变宽非变准)。"""
    w = widen_beliefs_on_gap(3)
    assert w['pool_variance_multiplier'] == 1.45
    assert '加宽' in w['note']


def test_rng_replay_deterministic() -> None:
    """随机数消费重放:同种子同消费数 → 恢复同断点(后续抽样一致)。"""
    r1 = replay_rng(42, 5)
    r2 = replay_rng(42, 5)
    assert [r1.random() for _ in range(3)] == [r2.random() for _ in range(3)]
    # 消费数不同 → 断点不同(流推进)
    r3 = replay_rng(42, 6)
    assert r3.random() != r1.random()


def test_projection_version_pinned() -> None:
    """版本 pinning:事件携带 projection_version(重放历史用当时版本的前提)。"""
    e = _ev('observation', 'obs:x', 1)
    assert e.projection_version == 1
