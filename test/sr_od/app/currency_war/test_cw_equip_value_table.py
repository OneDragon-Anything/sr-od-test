"""装备价值表补值锁(ADR-0555,批㉜ F4 清偿批)。

三面:
1. 补值键覆盖锁:策略层 key_equips 并集(去重)∩ 注册表 全量入表;
2. 对位锚值锁:F4 两名锚值直调数值复核(光速螺旋桨=5、
   动能激发剑=4,对位锚件在案由本锁 KeyError 面与死名守卫共辖);
3. 披露全量锁:检查项对全量缺值披露(移除任一单引用键也红)。
"""
from unittest.mock import patch

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENT_ROSTER,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_events import _EQUIP_VALUE
from sr_od.application.currency_war.sim.checks.ledger import (
    check_equip_value_strategy_key_coverage,
)


def _key_equips_union() -> set[str]:
    """策略层 key_equips 并集(全库去重)。"""
    names: set[str] = set()
    for c in COMP_LIBRARY:
        names.update(c.key_equips)
    return names


def test_equip_value_covers_all_strategy_key_equips() -> None:
    """覆盖锁:key_equips 并集 ∩ 注册表 ⊆ _EQUIP_VALUE(16 名全入)。

    缺值 = 未锁线局 decide_supply/planner 通用价值恒 0(定价失明),
    批㉜ F4 的真实缺口形态;ADR-0555 补值后清偿,回归即红防再漏。
    """
    missing = sorted(
        n for n in _key_equips_union()
        if n in EQUIPMENT_ROSTER and n not in _EQUIP_VALUE)
    assert not missing, f'key_equips 价值表缺值: {missing}'


def test_equip_value_keys_subset_of_roster() -> None:
    """死名守卫:表键必须 ⊆ 注册表单一源(ADR-0298 同款语义,本批
    新增 16 键后表面积翻倍,死名回归面随扩)。"""
    stale = sorted(n for n in _EQUIP_VALUE if n not in EQUIPMENT_ROSTER)
    assert not stale, f'价值表死名: {stale}'


def test_equip_value_f4_anchor_tiers() -> None:
    """锚值锁(补值批核心两值,直锁数值):光速螺旋桨=对位反重力
    皮靴 5 档(速度→强度换算乘区,5 comps 命脉);动能激发剑=对位
    冷笑话引擎 4 档(回合回战技点经济件)。改值 = 先改 ADR-0555。"""
    assert _EQUIP_VALUE['光速螺旋桨'] == _EQUIP_VALUE['反重力皮靴'] == 5
    assert _EQUIP_VALUE['动能激发剑'] == _EQUIP_VALUE['冷笑话引擎'] == 4


def test_variant_same_tier_as_base() -> None:
    """变体辖域锁(白昼/特权与基础件同值):变体 = 基础件效果数值
    强化,消费场景只强化不改定位,无实测依据禁差异化拍值。"""
    assert _EQUIP_VALUE['白昼·光速螺旋桨'] == _EQUIP_VALUE['光速螺旋桨']
    assert _EQUIP_VALUE['光速螺旋桨·特权'] == _EQUIP_VALUE['光速螺旋桨']
    assert _EQUIP_VALUE['火力风暴潮·特权'] == _EQUIP_VALUE['火力风暴潮']
    assert _EQUIP_VALUE['以牙还牙甲·特权'] == _EQUIP_VALUE['以牙还牙甲']


def test_coverage_check_discloses_any_single_reference_gap() -> None:
    """披露全量锁:阈值 ≥3 已除——移除**任一**单引用缺值键检查项
    即披露(回归即红防检查项退回阈值盲区形态)。"""
    single_ref = sorted(
        n for n in _key_equips_union()
        if n in EQUIPMENT_ROSTER and n in _EQUIP_VALUE
        and sum(n in c.key_equips for c in COMP_LIBRARY) == 1)
    assert single_ref, '无单引用样本可测,锁失去探针意义需重审'
    probe = single_ref[0]
    shrunk = {k: v for k, v in _EQUIP_VALUE.items() if k != probe}
    with patch(
            'sr_od.application.currency_war.kernel.cw_events._EQUIP_VALUE',
            shrunk):
        reported = check_equip_value_strategy_key_coverage([])
    assert any(probe in line for line in reported), \
        f'单引用键 {probe} 摘除未披露: {reported}'
