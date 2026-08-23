# -*- coding: utf-8 -*-
"""r409 Δ池防饥饿守卫 + 池标定检查锁(ADR-0268;压测批③ F1)。

批③ F1:battle 桶6 n=1 恒 -11 → 深 6 悬崖,跨桶边界策略臂被
系统性伪惩罚(B/B1/C 臂 snapshot hp 降幅大半为伪影)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_sim_checks import (
    check_ab_depth_boundary_confound,
    check_delta_pool_bucket_min_n,
    check_depth_cliff_monotonicity,
)


def test_guard_hungry_bucket_not_deterministic_cliff() -> None:
    """守卫触发:n<5 桶不裸采样——饥饿桶唯一样本不再恒定命中。

    合并候选 = 本桶∪深邻桶(20 样本),饥饿样本 -11 以 1/20
    权重参与(合并非剔除);旧语义下 depth∈[6,8] 的战斗轮
    **恒 -11**(确定性悬崖)是伪惩罚本体。
    """
    # battle 桶6 n=1 恒 -11(批③ F1 原始形态);桶9 n=6 健康
    pool = {'battle': {6: [-11],
                       9: [-4, -5, -6, -7, -8, -9]}}
    rng = random.Random(0)
    drawn = [cw_sim.live_delta_for('battle', 7, rng, pool_map=pool)
             for _ in range(200)]
    assert drawn.count(-11) <= 30   # ≈1/20 权重,远非常数(旧=200)
    assert -4 in drawn and -9 in drawn   # 邻桶样本可达(非恒悬崖)


def test_guard_picks_lower_variance_candidate() -> None:
    """降级选择:邻桶合并候选中取方差最小者(浅邻方差小 → 收敛浅邻)。"""
    pool = {'battle': {
        3: [-3, -4, -5, -6, -7, -8],           # 浅邻:方差小
        6: [-11],                               # 饥饿桶
        9: [-30, -1, -30, -1, -30, -1],         # 深邻:方差大
    }}
    rng = random.Random(1)
    for _ in range(200):
        v = cw_sim.live_delta_for('battle', 6, rng, pool_map=pool)
        assert v in (-3, -4, -5, -6, -7, -8, -11) or v == -11
        assert v != -30 and v != -1   # 深邻候选(方差大)不入选


def test_guard_tiny_pool_falls_back_to_bare_sample() -> None:
    """极端小池(无邻桶可合并):退回裸样本,语义不破(r340 兼容)。"""
    pool = {'battle': {6: [-3, -5]}}   # n=2,无邻桶,全池=本桶
    v = cw_sim.live_delta_for('battle', 7, random.Random(1),
                              pool_map=pool)
    assert v in (-3, -5)


def test_guard_preserves_missing_bucket_none() -> None:
    """守卫不改变缺桶两态语义:缺桶且无更浅桶 → None。"""
    pool = {'battle': {6: [-11], 9: [-4] * 6}}
    assert cw_sim.live_delta_for('battle', 0, random.Random(1),
                                 pool_map=pool) is None
    assert cw_sim.live_delta_for('boss', 6, random.Random(1),
                                 pool_map=pool) is None


def test_guard_healthy_bucket_unchanged() -> None:
    """n≥5 健康桶照旧裸采样(守卫零影响面)。"""
    pool = {'battle': {6: [-4, -5, -6, -7, -8]}}
    rng = random.Random(2)
    for _ in range(50):
        v = cw_sim.live_delta_for('battle', 7, rng, pool_map=pool)
        assert v in (-4, -5, -6, -7, -8)


def test_check_delta_pool_bucket_min_n() -> None:
    """检查项 1:饥饿桶审计(批③ 形态:battle 桶6 n=1)。"""
    pool = {'battle': {6: [-11], 9: [-4] * 6},
            'encounter': {9: [-13, 2]}}
    rep = check_delta_pool_bucket_min_n(pool)
    assert rep['violations'] == 2
    assert 'battle:桶6(n=1)' in rep['buckets']
    assert 'encounter:桶9(n=2)' in rep['buckets']
    # 全健康池 / 空池(fallback)零违规
    assert check_delta_pool_bucket_min_n(
        {'battle': {6: [-1] * 5}})['violations'] == 0
    assert check_delta_pool_bucket_min_n({})['violations'] == 0


def test_check_depth_cliff_monotonicity() -> None:
    """检查项 2:可信桶均值随深度单调不减血。"""
    # 违反:更深桶更痛(桶6 -5 → 桶9 -11)
    bad = {'battle': {6: [-5] * 6, 9: [-11] * 6}}
    rep = check_depth_cliff_monotonicity(bad)
    assert rep['violations'] == 1
    assert 'battle' in rep['pairs'][0]
    # 合规:更深不减血(趋 0 方向单调)
    good = {'battle': {6: [-11] * 6, 9: [-6] * 6, 12: [-2] * 6}}
    assert check_depth_cliff_monotonicity(good)['violations'] == 0
    # 饥饿桶(n<5)不参评——由检查项 1 辖
    skip = {'battle': {6: [-11], 9: [-5] * 6}}
    assert check_depth_cliff_monotonicity(skip)['violations'] == 0


def _battle_row(depth: int) -> dict:
    return {'plane': 1, 'round_num': 3,
            'sim': {'node': 'battle', 'depth': depth, 'delta': -5}}


def test_check_ab_depth_boundary_confound() -> None:
    """检查项 3:两臂深度桶占用不对称 → 池混杂标。"""
    a = [[_battle_row(4), _battle_row(7)]]     # A 跨桶 0/6
    b = [[_battle_row(4), _battle_row(4)]]     # B 只在桶 0
    hits = check_ab_depth_boundary_confound(a, b)
    assert len(hits) == 1
    assert '桶6' in hits[0] and 'A 臂' in hits[0]
    # 对称分布不报
    assert check_ab_depth_boundary_confound(
        [[_battle_row(7)]], [[_battle_row(8)]]) == []
    # 非战斗轮(reward)不入直方图
    reward_row = [{'plane': 1, 'round_num': 1,
                   'sim': {'node': 'reward', 'depth': 7, 'delta': 2}}]
    assert check_ab_depth_boundary_confound(
        [reward_row], []) == []


def test_batch_report_embeds_pool_checks() -> None:
    """simulate_p1_batch 内嵌池级检查(fallback 空池零违规)。"""
    rep = cw_sim.simulate_p1_batch(3, pool='fallback', ledger=False)
    cv = rep['checks_violations']
    assert cv['delta_pool_bucket_min_n']['violations'] == 0
    assert cv['depth_cliff_monotonicity']['violations'] == 0


def test_sampler_version_bumped_and_snapshot_guarded() -> None:
    """采样器 v2(守卫语义入指纹)+ 提交快照自洽。"""
    assert cw_sim._SAMPLER_VERSION == 2
    assert cw_sim._BUCKET_MIN_N == 5
    m, fp, src = cw_sim.resolve_pool('snapshot')
    assert src == 'snapshot'
    from sr_od.application.currency_war import cw_delta_pool_data
    assert fp == cw_delta_pool_data.META['fingerprint']
