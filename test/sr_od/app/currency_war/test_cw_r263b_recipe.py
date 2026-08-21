# -*- coding: utf-8 -*-
"""r263b 配方纪律测试(局15 鉴别诊断:散件稀释配方)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _RECIPE,
    _RECIPE_BASE,
)


def test_recipe_set_semantics() -> None:
    """配方集合语义(攻略[20]):基础(仙舟/DOT)+ 渐进(列车/护盾)。"""
    assert _RECIPE == frozenset(
        {'仙舟', '持续伤害', '列车同行', '护盾'})
    assert '减益' not in _RECIPE      # 局15 的散件元凶在配方外
    assert '星核猎手' not in _RECIPE
    assert '燃血' not in _RECIPE


def test_recipe_base_line() -> None:
    """基础线 = 3仙舟+2DOT = 5 档(攻略[20] 口径)。"""
    assert _RECIPE_BASE == 5
