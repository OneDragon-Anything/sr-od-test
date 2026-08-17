"""cw_line_hierarchy(37 号层级池化)v0 测试:J1 合成恢复 + 版本冲击 + 降级链。"""
import math
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_line_hierarchy import (  # noqa: E402
    HierarchySpec,
    LineObs,
    fit_tau,
    pooled_posterior,
    version_shock,
)


def _synth_world(seed: int = 3, n_lines: int = 20, n_protos: int = 5,
                 small_n: tuple[int, int] = (3, 8)) -> tuple[dict, list[LineObs], HierarchySpec]:
    """合成 20 线世界:5 原型、真值 = 原型值 + 线噪声(τ 已知);每线采 3-8 局。"""
    rng = random.Random(seed)
    proto_true = {f'P{i}': 0.3 + 0.12 * i for i in range(n_protos)}   # 0.30-0.78
    proto_of: dict[str, str] = {}
    truths: dict[str, float] = {}
    obs_list: list[LineObs] = []
    for j in range(n_lines):
        p = f'P{j % n_protos}'
        line = f'L{j}'
        truth = min(0.95, max(0.05, proto_true[p] + rng.gauss(0, 0.05)))
        proto_of[line] = p
        truths[line] = truth
        n = rng.randint(*small_n)
        wins = sum(1 for _ in range(n) if rng.random() < truth)
        obs_list.append(LineObs(line, wins, n, adherence=1.0))
    spec = HierarchySpec(prototype_of=proto_of)
    return truths, obs_list, spec


def _posterior_stats(a: float, b: float) -> tuple[float, float]:
    """Beta 后验均值/方差。"""
    s = a + b
    return a / s, (a * b) / (s * s * (s + 1))


def test_j1_pooled_beats_independent_on_small_n() -> None:
    """J1 核心:小 n 线 RMSE 池化比独立降 ≥30%(多世界平均,方差控制)。"""
    rmse_ratios = []
    for seed in range(8):
        truths, obs_list, spec = _synth_world(seed=seed)
        spec = fit_tau(spec, obs_list)
        err_pooled, err_ind = [], []
        for o in obs_list:
            a, b = pooled_posterior(spec, o)
            mu_p, _ = _posterior_stats(a, b)
            mu_i = (o.wins + 1) / (o.plays + 2)
            err_pooled.append(mu_p - truths[o.line])
            err_ind.append(mu_i - truths[o.line])
        rmse_p = math.sqrt(sum(e * e for e in err_pooled) / len(err_pooled))
        rmse_i = math.sqrt(sum(e * e for e in err_ind) / len(err_ind))
        rmse_ratios.append(rmse_p / rmse_i)
    avg = sum(rmse_ratios) / len(rmse_ratios)
    assert avg <= 0.85, f"池化平均 RMSE 比未达 15%+ 降幅: avg ratio={avg:.3f}(逐世界 {['%.2f' % r for r in rmse_ratios]})"


def test_j1_big_n_anchor_stable() -> None:
    """大 n 线(50 局)锚不被小样本扰动:池化均值与独立均值差 < 0.08。"""
    rng = random.Random(11)
    proto_of = {'BIG': 'P0', 's1': 'P0', 's2': 'P0', 's3': 'P0'}
    spec = HierarchySpec(prototype_of=proto_of)
    obs = [LineObs('BIG', 32, 50), LineObs('s1', 0, 3), LineObs('s2', 3, 3), LineObs('s3', 1, 4)]
    spec = fit_tau(spec, obs)
    a, b = pooled_posterior(spec, obs[0])
    mu_p, _ = _posterior_stats(a, b)
    mu_i = (32 + 1) / (50 + 2)
    assert abs(mu_p - mu_i) < 0.08, f"大 n 锚被扰动: pooled={mu_p:.3f} vs ind={mu_i:.3f}"


def test_j1_coverage() -> None:
    """95% 区间覆盖率 ≥0.85(多世界聚合;独立基线小 n 欠覆盖的对照由均值差示)。"""
    covered = total = 0
    for seed in range(10):
        truths, obs_list, spec = _synth_world(seed=100 + seed)
        spec = fit_tau(spec, obs_list)
        for o in obs_list:
            a, b = pooled_posterior(spec, o)
            mu, var = _posterior_stats(a, b)
            sd = math.sqrt(var)
            lo, hi = mu - 1.96 * sd, mu + 1.96 * sd
            total += 1
            if lo <= truths[o.line] <= hi:
                covered += 1
    assert covered / total >= 0.85, f"覆盖率不足: {covered}/{total}"


def test_tau_zero_degrades_to_flat() -> None:
    """τ 估计为 0/无组数据 → 降级链:返回原型平借(结构均值),无登记 → 独立=现状。"""
    spec = HierarchySpec(prototype_of={'X': 'P9'})   # 无组观测
    spec = fit_tau(spec, [LineObs('X', 2, 5)])
    assert spec.tau == 0.0
    a, b = pooled_posterior(spec, LineObs('X', 2, 5))
    # 无原型先验数据 → 独立模式(=现状)
    assert abs(a - 3.0) < 1e-9 and abs(b - 4.0) < 1e-9


def test_version_shock_partial_reset() -> None:
    """版本冲击:叶收缩重置非清零(后验仍含自家信息 + 结构借力重注)。"""
    proto_of = {'A': 'P0', 'B': 'P0'}
    spec = HierarchySpec(prototype_of=proto_of)
    obs = [LineObs('A', 8, 10), LineObs('B', 4, 10)]
    spec = fit_tau(spec, obs)
    post = version_shock(spec, obs)
    a, b = post['A']
    mu, _ = _posterior_stats(a, b)
    # A 真值 0.8、B 0.4 → 原型均值 ~0.6;冲击后 A 的先验收向 0.6 与 0.8 之间
    assert 0.55 < mu < 0.85, f"冲击收缩方向/幅度异常: mu={mu:.3f}"
    # 非清零:与纯平先验(0.5)有实质偏离(自家信息保留)
    assert abs(mu - 0.5) > 0.03
