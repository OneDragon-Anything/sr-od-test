# -*- coding: utf-8 -*-
"""ADR-0295 形态域结构批回归锁:混合域(deployed 主导+bench 折减)。

- 行为锁:bench-only 不成引擎(折减后计数 < 档位阈值)/deployed
  全额计数成引擎/bench 权重可调(1.0 时 bench-only 也成引擎)。
- 顶格不死锁:形态代理封顶折减后持有域囤件不再撑满 rung(x<引擎
  档),后续买入保留评分余量;目标件持有进度项天花板折减(n≥base
  时 targets = cap_frac × value,不再=满值)。
决策见 docs/develop/currency_war/decisions/0295-decision-v2-form-domain.md。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _held_form_weights,
    board_rung_x,
    score_state,
)


def _char_of_faction(faction: str) -> str:
    """取首个主阵营=faction 的真注册表角色名(引擎判定需真数据)。"""
    for n, c in CHARACTERS.items():
        if faction in (c.factions or ()):
            return n
    raise AssertionError(f'注册表无阵营 {faction} 角色')


def _bench(name: str, slot: int, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions or ['?'])[0], star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 100,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def test_bench_only_no_engine() -> None:
    """bench 折减:bench-only 仙舟×3 计数 1.05<3 → 不成引擎(x<1)。"""
    name = _char_of_faction('仙舟')
    st = _state(bench=[_bench(name, i) for i in (1, 2, 3)])
    assert board_rung_x(st, DEFAULT_REGISTRY) < 1.0, (
        'bench-only 囤件不得撑满引擎档(ADR-0295 deployed 主导)')


def test_deployed_full_weight_engine() -> None:
    """deployed 主导:上场仙舟×3 全额计数 → 引擎档(x≥1)。"""
    name = _char_of_faction('仙舟')
    st = _state(
        deployed=[_bench(name, i) for i in (1, 2, 3)],
        board={'仙舟': 3},
    )
    assert board_rung_x(st, DEFAULT_REGISTRY) >= 1.0


def test_bench_weight_adjustable() -> None:
    """权重可调:w=1.0 时 bench-only 也成引擎(等权=旧持有域行为)。"""
    name = _char_of_faction('仙舟')
    st = _state(bench=[_bench(name, i) for i in (1, 2, 3)])
    reg = replace(DEFAULT_REGISTRY, bench_form_weight=1.0)
    assert board_rung_x(st, reg) >= 1.0, (
        'w=1.0 应退化为旧持有域等权行为(bench-only 成引擎)')
    # 加权聚合同步锁:factions 计数 = 星级 × 权重
    fac, main, _dep = _held_form_weights(st, DEFAULT_REGISTRY)
    assert abs(fac['仙舟'] - 3 * DEFAULT_REGISTRY.bench_form_weight) < 1e-9
    assert abs(main['仙舟'] - 3 * DEFAULT_REGISTRY.bench_form_weight) < 1e-9


def test_target_hold_ceiling_discounted() -> None:
    """持有进度项天花板折减:n≥base 时 targets = cap_frac × value。"""
    from sr_od.application.currency_war.cw_bridge_pool import BRIDGE_POOL
    from sr_od.application.currency_war.cw_strategy import StrategySession
    # 目标件取桥池 fixed∪core(无方向种子语义=全集,必在 tset 内)
    names = sorted({n for combo in BRIDGE_POOL
                    for n in set(combo.fixed) | set(combo.core)
                    if n in CHARACTERS})
    name = names[0]
    n = DEFAULT_REGISTRY.target_hold_base + 1
    st = _state(bench=[_bench(name, i) for i in range(1, n + 1)])
    bd = score_state(st, DEFAULT_REGISTRY, StrategySession())
    expect = (DEFAULT_REGISTRY.target_hold_cap_frac
              * DEFAULT_REGISTRY.target_hold_value)
    assert abs(bd['targets'] - round(expect, 3)) < 0.01, (
        f"顶格 targets 应为 {expect}(实际 {bd['targets']})——"
        '顶格不再=满形态(ADR-0295)')


def test_form_domain_initial_values() -> None:
    """ADR-0295 结构批初值锁(20 局诊断定;改动须重诊断+更新本锁)。"""
    assert DEFAULT_REGISTRY.bench_form_weight == 0.35
    assert DEFAULT_REGISTRY.target_hold_cap_frac == 0.8
