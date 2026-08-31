"""cw_weight_search(24 号 CEM 权重搜索)v0 测试:J1 收敛 + J2 护栏自证。

出处:docs/develop/currency_war/decisions/INDEX.md;docs/develop/currency_war/strategy/05_observation.md(2026-08-31 测试瘦身批考证补记)。"""
import math
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.tools.cw_weight_search import (  # noqa: E402
    WeightDim,
    WeightSpace,
    cem_search,
    evaluate_weights,
)


def _synthetic_fitness(xs, seed, optimum=None, trap=None):
    """合成适应度:朝 optimum 的碗形 + 可选「陷阱维度」(sim 偏差虚高)。"""
    rng = random.Random(seed)
    opt = optimum or [3.0, 1.0]
    v = -sum((x - o) ** 2 for x, o in zip(xs, opt, strict=False))
    v += rng.gauss(0, 0.05)   # 观测噪声
    if trap is not None:
        # 陷阱:把权重大幅推离先验可获 sim 虚高(reward hacking 的合成形态)
        v += 0.8 * max(0.0, xs[0] - opt[0]) * 2
    return v


def test_j1_cem_converges_toward_optimum() -> None:
    """J1:已知更优点(远离先验中心)→ CEM 收敛方向正确(最优适应度显著高于先验点)。"""
    space = WeightSpace((WeightDim('w1', 1.0), WeightDim('w2', 0.5)))
    seeds = list(range(20))
    r = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, optimum=[3.0, 1.0]),
                   seed_bank=seeds, n_gen=10)
    prior_fit = evaluate_weights(space.prior_vector(),
                                 lambda xs, s: _synthetic_fitness(xs, s, optimum=[3.0, 1.0]),
                                 seeds, l2_coeff=0.05, center=space.prior_vector())
    assert r['best_fitness'] > prior_fit + 0.5, (
        f"收敛不足: best={r['best_fitness']} vs prior={prior_fit}")
    assert r['best'][0] > 2.0   # 朝 optimum=3 方向移动


def test_j2_regularization_bounds_reward_hacking() -> None:
    """J2 护栏自证:注入 sim 偏差陷阱 → 无正则冠军把 w1 推到上限拿虚高分;
    带正则冠军 w1 受界(离先验更近)——护栏真在防,不是装饰。"""
    space = WeightSpace((WeightDim('w1', 1.0, hi=10.0), WeightDim('w2', 0.5)))
    seeds = list(range(15))
    trap = object()
    no_reg = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                        seed_bank=seeds, n_gen=8, l2_coeff=0.0)
    with_reg = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                          seed_bank=seeds, n_gen=8, l2_coeff=0.3)
    assert no_reg['best'][0] > with_reg['best'][0], (
        f"正则未约束 hacking: no_reg={no_reg['best']} reg={with_reg['best']}")
    assert with_reg['best'][0] < no_reg['best'][0]


def test_prior_anchor_monotone() -> None:
    """中心保留锚:任何代的最优不劣于先验起点(搜索不倒退)。"""
    space = WeightSpace((WeightDim('w1', 1.0),))
    r = cem_search(space, lambda xs, s: _synthetic_fitness(xs, s),
                   seed_bank=list(range(8)), n_gen=5)
    assert r['best_fitness'] >= r['history'][0]['best_fit'] - 1e-9


def test_l2_penalty_semantics() -> None:
    """L2 语义:同适应度下离先验远者罚重。"""
    f = lambda xs, s: 1.0
    near = evaluate_weights([1.2], f, [1], l2_coeff=1.0, center=[1.0])
    far = evaluate_weights([3.0], f, [1], l2_coeff=1.0, center=[1.0])
    assert far < near
    assert math.isclose(near, 1.0 - 0.04, abs_tol=1e-9)
