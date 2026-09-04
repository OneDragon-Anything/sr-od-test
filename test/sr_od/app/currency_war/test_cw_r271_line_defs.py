# -*- coding: utf-8 -*-
"""test_cw_r271_line_defs 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



from sr_od.application.currency_war.kernel.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_BASE,
    RECIPE_FACTIONS,
    recipe_kinds_1cost,
    recipe_tier,
)


def test_recipe_set_semantics() -> None:
    """配方集合(攻略[20]):基础(仙舟/DOT)+渐进(列车/护盾)。"""
    assert frozenset(
        {'仙舟', '持续伤害', '列车同行', '护盾'}) == RECIPE_FACTIONS
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
    W126/ADR-0350:dot_belog/hunt3 两桥已随四体系封闭裁定删除——
    狼狩/贝洛伯格退出引擎门(贝只在希儿系判据内保留计数);存活三桥
    (xianzhou_dot/xianzhou_train/train_dot)派生出四体系三羁绊。"""
    assert frozenset(
        {'仙舟', '列车同行', '持续伤害'}) == ENGINE_FACTIONS


def test_recipe_tier_helper() -> None:
    assert recipe_tier({'仙舟': 3, '列车同行': 2, '公司': 1}) == 5
    assert recipe_tier({}) == 0
    assert recipe_tier({'公司': 9}) == 0


def test_consumers_share_single_source() -> None:
    """消费方共享单源:deploy_bench 与 cw_line_defs 的名字一致
    (旧 line_strategy 局部 set 随 ADR-0336 删)。

    dd-037 更新:op 的配方基础线判据(RECIPE_BASE)随选人段收敛进
    kernel.cw_deploy_logic.select_deployments(kernel 自己 import 单一源),
    op 模块的 _RECIPE_BASE 死别名已删——单源性改锁在 kernel 消费上,
    op 侧围栏别名(_RECIPE)锁保持。
    """
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as deploy_bench
    import sr_od.application.currency_war.kernel.cw_deploy_logic as deploy_logic
    assert deploy_bench._RECIPE is RECIPE_FACTIONS
    assert deploy_logic.RECIPE_BASE == RECIPE_BASE
    assert deploy_logic.select_deployments is not None


def test_1cost_kinds_positive() -> None:
    """1 费配方件种数 >0(找件刷概率的分子)。"""
    assert recipe_kinds_1cost() >= 4
