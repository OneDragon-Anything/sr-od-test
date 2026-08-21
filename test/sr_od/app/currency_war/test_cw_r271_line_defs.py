# -*- coding: utf-8 -*-
"""r271 配方/引擎阵营单一源测试(统一审查批次一)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_BASE,
    RECIPE_FACTIONS,
    recipe_kinds_1cost,
    recipe_tier,
)


def test_recipe_set_semantics() -> None:
    """配方集合(攻略[20]):基础(仙舟/DOT)+渐进(列车/护盾)。"""
    assert RECIPE_FACTIONS == frozenset(
        {'仙舟', '持续伤害', '列车同行', '护盾'})
    # r263b 局15 锁(合并自 test_cw_r263b_recipe.py,原文件已删):
    # 散件元凶阵营不得进配方
    assert '减益' not in RECIPE_FACTIONS
    assert '星核猎手' not in RECIPE_FACTIONS
    assert '燃血' not in RECIPE_FACTIONS


def test_recipe_base_line() -> None:
    """基础线 = 3仙舟+2DOT = 5 档。"""
    assert RECIPE_BASE == 5


def test_engine_derived_from_bridges() -> None:
    """引擎阵营从桥池派生(单一源,不再手抄)。
    r353(V4.0 口径):能打伤害的前期羁绊五家=仙舟/狼狩/DOT/
    列车/贝洛伯格(transitions.md §1);dot_belog 与 hunt3 桥
    入池后贝洛伯格/狼狩随 engine_bonds 派生进引擎门。"""
    assert ENGINE_FACTIONS == frozenset(
        {'仙舟', '列车同行', '持续伤害', '狼狩', '贝洛伯格'})


def test_recipe_tier_helper() -> None:
    assert recipe_tier({'仙舟': 3, '列车同行': 2, '公司': 1}) == 5
    assert recipe_tier({}) == 0
    assert recipe_tier({'公司': 9}) == 0


def test_consumers_share_single_source() -> None:
    """消费方共享单源:deploy_bench 与 line_strategy 的名字一致。"""
    from sr_od.application.currency_war.operations.prep import (
        deploy_bench,
    )
    assert deploy_bench._RECIPE is RECIPE_FACTIONS
    assert deploy_bench._RECIPE_BASE == RECIPE_BASE


def test_1cost_kinds_positive() -> None:
    """1 费配方件种数 >0(找件刷概率的分子)。"""
    assert recipe_kinds_1cost() >= 4
