"""test_cw_weight_search 主题锁(离线权重搜索器;T-197 回补家)。

前身 = test_cw_weight_search.py 随测试重组批 f799914 整体退役(sim_suite
机械拼接的 weight_search 节);本机制此前无主题文件,按纪律单独立家。

出处:tools/cw_weight_search(redesign 24 号/ADR-0194,CEM 闭环 +
防退化三件套 = 先验 L2 正则 + 种子族域随机化代理 + 13 合约硬约束挂
消费端)。本锁辖 J2 护栏自证面:注入 sim 偏差陷阱 → 无正则冠军把权重
推到上限拿虚高分,带正则冠军受界(离先验更近)——护栏真在防,不是装饰。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.tools.cw_weight_search import (
    WeightDim,
    WeightSpace,
    cem_search,
)


def _synthetic_fitness(xs: list[float], seed: int, optimum: list[float] | None = None,
                       trap: object | None = None) -> float:
    """合成适应度:朝 optimum 的碗形 + 可选「陷阱维度」(sim 偏差虚高)。"""
    rng = random.Random(seed)
    opt = optimum or [3.0, 1.0]
    v = -sum((x - o) ** 2 for x, o in zip(xs, opt, strict=False))
    v += rng.gauss(0, 0.05)   # 观测噪声
    if trap is not None:
        # 陷阱:把权重大幅推离先验可获 sim 虚高(reward hacking 的合成形态)
        v += 0.8 * max(0.0, xs[0] - opt[0]) * 2
    return v


def test_j2_regularization_bounds_reward_hacking() -> None:
    """J2 护栏自证:注入 sim 偏差陷阱 → 无正则冠军把 w1 推到上限拿虚高
    分;带正则冠军 w1 受界(离先验更近)——护栏真在防,不是装饰。

    确定性:cem_search 内部 rng 固定种子 + CRN 配对种子库 → 同入参同结论。
    """
    space = WeightSpace((WeightDim('w1', 1.0, hi=10.0), WeightDim('w2', 0.5)))
    seeds = list(range(15))
    trap = object()
    no_reg = cem_search(space,
                        lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                        seed_bank=seeds, n_gen=8, l2_coeff=0.0)
    with_reg = cem_search(space,
                          lambda xs, s: _synthetic_fitness(xs, s, trap=trap),
                          seed_bank=seeds, n_gen=8, l2_coeff=0.3)
    assert no_reg['best'][0] > with_reg['best'][0], (
        f'正则未约束 hacking: no_reg={no_reg["best"]} reg={with_reg["best"]}')
