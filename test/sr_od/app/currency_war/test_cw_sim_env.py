"""cw_sim_env(02 号 salvage 校准环境 v0)测试:确定性/收支守恒/A/B 分辨力(ADR-0168)。"""
import pytest

from sr_od.application.currency_war.cw_sim_env import (
    SimEnv,
    baseline_policy,
    run_batch,
)


def test_determinism_same_seed():
    r1 = SimEnv(seed=7).run(baseline_policy)
    r2 = SimEnv(seed=7).run(baseline_policy)
    assert r1.hp_trace == r2.hp_trace
    assert r1.gold_end == r2.gold_end and r1.level_end == r2.level_end


def test_bounds_respected():
    """hp ∈ [0,100];gold ≤ 110;等级 ≤ 10。"""
    for seed in range(10):
        r = SimEnv(seed=seed).run(baseline_policy)
        assert 0 <= r.hp_end <= 100
        assert r.gold_end <= 110
        assert 1 <= r.level_end <= 10


def test_batch_produces_metrics():
    rep = run_batch(baseline_policy, n=40, seed0=0)
    assert rep['n'] == 40
    assert 0.0 <= rep['survival_rate'] <= 1.0
    assert 1.0 <= rep['mean_plane'] <= 3.0
    assert rep['mean_level_end'] >= 1


def test_ab_discriminates_policies():
    """A/B 分辨力:激进策略(永不存息,见牌就买)vs 基线 —— 指标可分离(环境有效性)。"""

    def aggressive(st, env):
        acts = []
        for c in st.shop:
            if c.name and st.gold >= c.cost + 2:
                acts.append(__import__('sr_od.application.currency_war.cw_state', fromlist=['BuyCard']).BuyCard(card=c))
                break
        return acts

    base = run_batch(baseline_policy, n=60, seed0=0)
    aggr = run_batch(aggressive, n=60, seed0=0)
    # 两策略至少在某指标上分化(说明环境对策略敏感,不是常数输出)
    diffs = [abs(base['survival_rate'] - aggr['survival_rate']),
             abs(base['mean_level_end'] - aggr['mean_level_end']),
             abs(base['mean_gold_end'] - aggr['mean_gold_end'])]
    assert max(diffs) > 0.01
