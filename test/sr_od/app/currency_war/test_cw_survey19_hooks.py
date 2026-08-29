"""cw_survey19_hooks(P9/P1/P8 决策件)测试。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_survey19_hooks import (  # noqa: E402
    encounter_tier_score,
    supply_reroll_decision,
    wear_discipline_alert,
)


def test_p9_encounter_tier_context_dependent() -> None:
    """遭遇档评分场合依赖:同 −4,边际局高分/大胜局≈0;P1 放大。"""
    edge = encounter_tier_score(100, -4, gap=0, plane=2)
    blow = encounter_tier_score(100, -4, gap=-80, plane=2)
    p1 = encounter_tier_score(100, -4, gap=0, plane=1)
    assert edge > blow
    assert p1 > edge   # P1 尖峰 ×1.5


def test_p1_wear_discipline() -> None:
    """狼狩穿戴纪律:可穿而未穿 = 报警;无空槽的真积压才算;非狼狩无 XP 项。"""
    # 3 件闲 + 2 空槽 → overflow 1 → 报警(狼狩:每战 −1 XP)
    r = wear_discipline_alert(['a', 'b', 'c'], total_slots=10, worn_count=8,
                              faction_hunt_active=True)
    assert r['alert'] and r['unwearable_overflow'] == 1
    assert r['hunt_xp_loss_per_battle'] == 1
    # 全穿满 → 无报警(装备可循环,合成交换不算积压)
    ok = wear_discipline_alert([], total_slots=10, worn_count=10,
                               faction_hunt_active=True)
    assert not ok['alert'] and ok['hunt_xp_loss_per_battle'] == 0
    # 非狼狩:仅战力视角
    no_hunt = wear_discipline_alert(['a', 'b', 'c'], 10, 8, faction_hunt_active=False)
    assert no_hunt['alert'] and no_hunt['hunt_xp_loss_per_battle'] == 0


def test_p8_supply_reroll() -> None:
    """补给重刷:出钻直选/未出可刷→刷/刷过仍无→按价值选。"""
    assert supply_reroll_decision(True, False) == 'pick_diamond'
    assert supply_reroll_decision(True, True) == 'pick_diamond'
    assert supply_reroll_decision(False, False) == 'reroll'
    assert supply_reroll_decision(False, True) == 'pick_best'
