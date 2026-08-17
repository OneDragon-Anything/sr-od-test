"""cw_release_layer(47 号发布层)v0 测试:J0 混杂恢复 + PVS/注册表语义。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import pytest  # noqa: E402

from sr_od.application.currency_war.cw_release_layer import (  # noqa: E402
    PolicyVersionStamp,
    ReleaseRegistry,
    RELEASE_STATES,
    generation_stratified_estimate,
)


def test_j0_confound_recovery() -> None:
    """J0 核心:合成语料注入世代效应(旧代驾驶差 −15pp 且与线指派相关:
    强线 A 多在旧代跑,弱线 C 多在新代跑)→ 不分层 top-3 排序翻转(A 被压到 C 下),
    分层+去偏恢复真排序 A>B>C。"""
    runs = []
    # 真强度:A=0.60 B=0.50 C=0.40;旧代整体 −0.15(驾驶差)
    # 指派相关:A 在旧代 60 局/新代 10 局;B 两代各半;C 旧 10/新 60
    import random
    rng = random.Random(3)
    def _emit(line, gen, n, p_true, gen_shift):
        pw = p_true + gen_shift
        w = sum(1 for _ in range(n) if rng.random() < pw)
        runs.append((line, gen, w, n))
    _emit('A', 'g1', 60, 0.60, -0.15)
    _emit('A', 'g2', 10, 0.60, 0.0)
    _emit('B', 'g1', 30, 0.50, -0.15)
    _emit('B', 'g2', 30, 0.50, 0.0)
    _emit('C', 'g1', 10, 0.40, -0.15)
    _emit('C', 'g2', 60, 0.40, 0.0)
    est = generation_stratified_estimate(runs)
    assert est['naive_ranking'] != ['A', 'B', 'C'], (
        f"混杂未翻转 naive 排序(注入失效或太弱): {est['naive_ranking']}")
    assert est['ranking'] == ['A', 'B', 'C'], (
        f"分层未恢复真排序: {est['ranking']}(strengths={est['line_strengths']})")


def test_gen_offsets_sign() -> None:
    """世代偏移符号:旧代负偏移、新代零锚(共享先验收缩)。"""
    runs = [('A', 'old', 3, 30), ('B', 'old', 2, 30), ('A', 'new', 18, 30), ('B', 'new', 15, 30)]
    est = generation_stratified_estimate(runs)
    assert est['gen_offsets']['old'] < 0 < est['gen_offsets']['new']


def test_pvs_stable_id() -> None:
    """PVS 稳定 id:同三元组同 id;seam 向量不同 → id 不同。"""
    a = PolicyVersionStamp('abc123def', (True, False) * 7 + (True,), 'w1', 'c1')
    b = PolicyVersionStamp('abc123def', (True, False) * 7 + (True,), 'w1', 'c1')
    c = PolicyVersionStamp('abc123def', (False,) * 15, 'w1', 'c1')
    assert a.stable_id() == b.stable_id()
    assert a.stable_id() != c.stable_id()


def test_release_registry_transitions() -> None:
    """发布态机:合法跃迁记录证据;非法态拒绝。"""
    reg = ReleaseRegistry()
    reg.transition('horizon', 'canary', evidence='ADR-0181 A/B')
    reg.transition('horizon', 'promoted', evidence='J1 判据过')
    assert reg.system_view() == {'horizon': 'promoted'}
    with pytest.raises(ValueError):
        reg.transition('horizon', 'half-baked')
    assert set(RELEASE_STATES) == {'shadow', 'canary', 'promoted', 'rolled_back', 'quarantined'}
