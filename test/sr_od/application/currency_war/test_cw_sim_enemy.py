"""sim 敌人难度派生(M19)/boss 名单(M20)/特殊角色规则(M21)回归锁。

锁面 = U25 难度定谳成分与基础 None 披露(品质彩 6/遭遇档 20/伟大征服
连胜项;难度修改器节点型限定)/U02 boss 池采样与覆盖优先/U26 银狼策划
触发判据与开拓者形态。模块归宿 = sim/cw_sim_enemy + cw_sim_special
(驱动反转迭代平移保留)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.sim.cw_sim_enemy import (
    BOSS_DEDUP_PENDING,
    DIFFICULTY_BASE_PENDING_U25,
    HOLY_GRAIL_BONUS,
    difficulty_of,
    resolve_plane_bosses,
)
from sr_od.application.currency_war.sim.cw_sim_special import (
    SILVER_WOLF_ID,
    planner_overlay_due,
    trailblazer_form_of,
)

# ============================================================ M19 难度

def test_difficulty_known_components_and_base_none_u25() -> None:
    """U25:定谳成分(品质彩6/遭遇档20/伟大征服连胜项)逐项可算;
    基础曲线未采 → base=None 且 total=None(禁插值不出合计)。"""
    d = difficulty_of(['伟大征服'], node_kind='encounter', streak=2,
                      encounter_tier=3, base=None)
    assert d.base is None and d.total is None
    assert d.quality_bonus == 6, '伟大征服 = 棱彩档 +6(注册表 rarity)'
    assert d.encounter_tier_bonus == 20, '第三档 = 20'
    assert d.special_bonus == 2, 'difficulty_per_streak=1 × streak=2'
    assert d.strategy_delta == 0
    assert DIFFICULTY_BASE_PENDING_U25


def test_difficulty_total_with_base_and_node_scoped_delta() -> None:
    """base 可传(局级输入档):total = base + 定谳成分;难度修改器
    (−4,遭遇+首领限定)只在遭遇/首领节点计入。"""
    d_battle = difficulty_of(['难度修改器'], node_kind='battle',
                             streak=0, base=100)
    assert d_battle.strategy_delta == 0, '战斗节点不计节点型限定 Δ'
    assert d_battle.total == 100
    d_enc = difficulty_of(['难度修改器'], node_kind='encounter',
                          streak=0, base=100)
    assert d_enc.strategy_delta == -4 and d_enc.total == 96
    d_simple = difficulty_of(['简单模式'], node_kind='battle',
                             streak=0, base=100)
    assert d_simple.strategy_delta == -3, '无限定 Δ 恒计入'


def test_difficulty_holy_grail_constant_pending() -> None:
    """圣杯 +30 定谳真值在册;激活态占位(首版恒未激活)。"""
    d_off = difficulty_of([], node_kind='battle', streak=0, base=50)
    assert d_off.special_bonus == 0
    d_on = difficulty_of([], node_kind='battle', streak=0, base=50,
                         holy_grail_active=True)
    assert d_on.special_bonus == HOLY_GRAIL_BONUS == 30


# ============================================================ M20 boss

def test_plane_boss_override_priority_and_pool_membership() -> None:
    """U02:RunConfig 覆盖位优先;None 位 → 内置池采样(池 = boss 机制
    注册表键集)。"""
    from sr_od.application.currency_war.data.cw_enemy_data import (
        BOSS_MECHANICS,
    )
    picked = resolve_plane_bosses(
        ('造梦兄弟影业', None, '灰手生命科技'), random.Random(1))
    assert picked[0] == '造梦兄弟影业' and picked[2] == '灰手生命科技'
    assert picked[1] in BOSS_MECHANICS
    full_sampled = resolve_plane_bosses(None, random.Random(2))
    assert all(b in BOSS_MECHANICS for b in full_sampled)
    assert BOSS_DEDUP_PENDING  # 去重语义占位披露键在册


# ============================================================ M21 特殊角色

def test_planner_overlay_due_on_first_two_star() -> None:
    """「我来当策划」触发判据:银狼升达 2 星的合成事件(1→2);
    非 2 星跨越/非银狼不触发。"""
    assert planner_overlay_due(SILVER_WOLF_ID, 1, 2)
    assert not planner_overlay_due(SILVER_WOLF_ID, 2, 3)
    assert not planner_overlay_due('淘金客', 1, 2)


def test_trailblazer_form_routing() -> None:
    """开拓者双形态按排路由(front=记忆/back=欢愉);非开拓者原样。"""
    assert trailblazer_form_of('开拓者', 'front') == '开拓者·记忆'
    assert trailblazer_form_of('开拓者', 'back') == '开拓者·欢愉'
    assert trailblazer_form_of('淘金客', 'front') == '淘金客'
