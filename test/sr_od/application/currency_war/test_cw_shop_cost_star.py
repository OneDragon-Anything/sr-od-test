"""商店费用徽章 → (费用, 星级) 解析锁:银狼LV.999 升费后基准费 ≠ 注册表
起始费形态(银狼升星记账批;设计 = docs/develop/sr_od/application/
currency_war/。
倍数体系 = 3^(星级−1):1★×1 / 2★×3 / 3★×9(cw_observation.
_SHOP_COST_MULT_TO_STAR)。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_observation import (
    COST_SOURCE_ROSTER_FALLBACK,
    resolve_cost_star,
)


def test_lv999_tier_badge_resolves():
    """升费形态:档=4 时 badge=4 → 1★/4费、badge=12 → 2★/12费。

    修复前除数 = 注册表起始费 3:badge=4/12 均非 3 的 1/3/9 倍 →
    roster_fallback 系统性误记 3费1★(设计 §1.2 症状 4)。"""
    assert resolve_cost_star(4, 4) == (4, 1, 'badge')
    assert resolve_cost_star(12, 4) == (12, 2, 'badge')


def test_plain_char_multiplier_regression():
    """普通角色回归:起始费 3 的 1/2★ 徽章 = 3/9(除数换语义后零行为差)。"""
    assert resolve_cost_star(3, 3) == (3, 1, 'badge')
    assert resolve_cost_star(9, 3) == (9, 2, 'badge')


def test_missing_and_nonintegral_fallback():
    """缺读/疑误读 → 基准费兜底记 1★(roster_fallback 留证语义不变)。"""
    assert resolve_cost_star(None, 4) == (4, 1, COST_SOURCE_ROSTER_FALLBACK)
    assert resolve_cost_star(8, 4) == (4, 1, COST_SOURCE_ROSTER_FALLBACK)
