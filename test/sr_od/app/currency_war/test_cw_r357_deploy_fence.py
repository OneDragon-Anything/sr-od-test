# -*- coding: utf-8 -*-
"""r357(局44 判读,r353 集成缺口):deploy 围栏随桥派生集。

局44 r2 实锤:四飞霄(狼狩,hunt3 桥件)全被旧四阵营围栏
(RECIPE_FACTIONS)按「非配方件+配方未满」摁 bench——板面
2/5 空槽打仗、金花在坐冷板凳。V4.0 过渡配方含 3狼狩系,
围栏必须 = RECIPE ∪ ENGINE(桥派生单一源)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_FACTIONS,
)
from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _DEPLOY_FENCE,
)


def test_deploy_fence_includes_bridge_factions() -> None:
    """r357 主锁:围栏集含桥派生阵营(狼狩/贝洛伯格)——
    r353 桥件买来必须能上场(hunt3/dot_belog 是 V4.0 过渡配方)。"""
    assert _DEPLOY_FENCE == frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS)
    assert '狼狩' in _DEPLOY_FENCE, 'hunt3 桥件(飞霄系)必须过围栏'
    assert '贝洛伯格' in _DEPLOY_FENCE, 'dot_belog 桥件必须过围栏'
    # 配方四老成员不丢
    for f in ('仙舟', '列车同行', '护盾', '持续伤害'):
        assert f in _DEPLOY_FENCE


def test_deploy_fence_still_blocks_pure_scatter() -> None:
    """纯散阵营(欢愉/公司/盛会之星)仍被围栏——r263b 纪律
    对非过渡配方阵营保持(防散件稀释)。"""
    for f in ('欢愉', '公司', '盛会之星', '夜之半神'):
        assert f not in _DEPLOY_FENCE, f'{f} 是散阵营,配方饥饿期必须留 bench'
