"""drawable_names / grant_bucket_names 景元费用档桶归属测试(镜像 src =
kernel/cw_pool.py 该两出口;宿主目录按被测函数拆目录规范落位,先例 =
同目录 test_grant_char_pool.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-410-feiguang-
yingyue.md §4 锁 5(默认案 A 全场同名同档,含商店在架卡):
- 飞光·映月拿卡档 1(tier=1)→ 景元归入 1 费桶(商店发牌桶/随机授予桶
  自动跟随,经 effective_cost 档感知过滤零额外接入调用);
- 未拿卡(None)→ 景元在注册表起始 5 费桶。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    Field,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_pool import (
    drawable_names,
    grant_bucket_names,
)


def _gs(tier: int | None) -> GameState:
    """直构容器种子(空席 held 全零;tier None = 未拿卡形态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if tier is not None:
        gs = replace(gs, yingyue_cost_tier=Field(value=tier, source='logic'))
    return gs


def test_drawable_names_yingyue_tier_bucket() -> None:
    """商店发牌桶:tier=1 → 景元 ∈ 1 费桶且 ∉ 5 费桶;None → 反之。
    (桶归属即费用档过滤的直接后果,在架卡同名同档。)"""
    held_gs = _gs(1)
    assert '景元' in drawable_names(held_gs, 1), '档 1 → 景元 ∈ 1 费桶'
    assert '景元' not in drawable_names(held_gs, 5), '档 1 → 景元 ∉ 5 费桶'
    fresh_gs = _gs(None)
    assert '景元' in drawable_names(fresh_gs, 5), '未拿卡 → 景元 ∈ 5 费桶'
    assert '景元' not in drawable_names(fresh_gs, 1), \
        '未拿卡 → 景元 ∉ 1 费桶'


def test_grant_bucket_names_yingyue_tier_bucket() -> None:
    """随机授予桶(与商店出口同一档感知过滤,差异仅 ≥9 清空条件):
    tier=1 → 景元 ∈ 1 费桶;None → 5 费桶。"""
    held_gs = _gs(1)
    assert '景元' in grant_bucket_names(held_gs, 1), '档 1 → 1 费授予桶'
    assert '景元' not in grant_bucket_names(held_gs, 5), '档 1 → ∉ 5 费授予桶'
    fresh_gs = _gs(None)
    assert '景元' in grant_bucket_names(fresh_gs, 5), \
        '未拿卡 → 5 费授予桶'
    assert '景元' not in grant_bucket_names(fresh_gs, 1), \
        '未拿卡 → ∉ 1 费授予桶'
