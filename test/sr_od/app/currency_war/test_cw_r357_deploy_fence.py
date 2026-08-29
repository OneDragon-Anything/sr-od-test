# -*- coding: utf-8 -*-
"""r357(局44 判读,r353 集成缺口):deploy 围栏随桥派生集。

局44 r2 实锤:四飞霄(狼狩,hunt3 桥件)全被旧四阵营围栏
(RECIPE_FACTIONS)按「非配方件+配方未满」摁 bench——板面
2/5 空槽打仗、金花在坐冷板凳。V4.0 过渡配方含 3狼狩系,
围栏必须 = RECIPE ∪ ENGINE(桥派生单一源)。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_line_defs import (
    ENGINE_FACTIONS,
    RECIPE_FACTIONS,
)
from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _DEPLOY_FENCE,
)


def test_deploy_fence_includes_bridge_factions() -> None:
    """r357 主锁(围栏=RECIPE ∪ ENGINE 桥派生单一源)。
    W126/ADR-0350:狼狩/贝洛伯格已随四体系封闭裁定退出围栏
    (hunt3/dot_belog 桥删除)——已封存体系件不再有框架豁免通道;
    桥派生(存活三桥=仙舟/dot/列车)与配方四老成员保持。"""
    assert _DEPLOY_FENCE == frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS)
    assert '狼狩' not in _DEPLOY_FENCE, 'W126:已封存体系退出围栏'
    assert '贝洛伯格' not in _DEPLOY_FENCE, 'W126:已封存体系退出围栏'
    # 配方四老成员不丢
    for f in ('仙舟', '列车同行', '护盾', '持续伤害'):
        assert f in _DEPLOY_FENCE


def test_deploy_fence_still_blocks_pure_scatter() -> None:
    """纯散阵营(欢愉/公司/盛会之星)仍被围栏——r263b 纪律
    对非过渡配方阵营保持(防散件稀释)。"""
    for f in ('欢愉', '公司', '盛会之星', '夜之半神'):
        assert f not in _DEPLOY_FENCE, f'{f} 是散阵营,配方饥饿期必须留 bench'
