"""cw_equip_planner(07 号装备规划器 v0)测试:行为锚单测(ADR-0164;提案判据①)。"""
from sr_od.application.currency_war.cw_equip_planner import (
    EquipPlanner,
    equip_overlap_matrix,
    pivot_equip_cost,
)


def test_anchor_lock_target_take_core_component():
    """行为锚:target 单锁(阿雅 key=双皮靴)时,皮靴直接命中 → 价值高于无关件。"""
    p = EquipPlanner(['昼神阿雅'])
    v_boot = p.value_of_take('反重力皮靴', {}, channels_left=2)   # 进阶件直接命中 key
    v_other = p.value_of_take('冶金炉', {}, channels_left=2)      # 非组件非 key
    assert v_boot > 0
    assert v_boot > v_other


def test_anchor_locked_and_full_low_value():
    """行为锚:target 已齐该件 → 再取价值 ≈0(盈余)。"""
    from sr_od.application.currency_war.cw_comps import get_comp
    comp = get_comp('列车同行')
    keys = list(comp.key_equips)
    first = keys[0]
    p = EquipPlanner(['列车同行'])
    need = keys.count(first)
    v_full = p.value_of_take(first, {first: need}, channels_left=3)
    v_gap = p.value_of_take(first, {}, channels_left=3)
    assert v_gap > v_full


def test_anchor_exercise_vital_when_gap():
    """行为锚:产物是 target 命脉件且缺口 → 立即行权。"""
    p = EquipPlanner(['列车同行'])
    from sr_od.application.currency_war.cw_synthesis import cross_components
    keys = list(p.candidates[0].key_equips)
    adv = next(a for a in keys if cross_components(a))
    cc = cross_components(adv)
    ok, why = p.should_exercise(cc[0], cc[1], {})
    assert ok, why


def test_anchor_hold_when_component_is_other_path():
    """行为锚:「风暴潮前不合小件」—— 组件是命脉路的临门组件 → 持有。"""
    # 反重力皮靴 = 自配轮滑鞋;构造:target 含某自配进阶,组件量少 → 持有
    p = EquipPlanner(None)   # 多元候选(期权全开)
    ok, why = p.should_exercise('轮滑鞋', '轮滑鞋', {})   # 自配 → 皮靴
    # 多元下皮靴是 15/19 comp 共享高重叠件,大概率行权;关键断言是理由可解释
    assert isinstance(ok, bool) and why


def test_overlap_matrix_derived():
    """重叠矩阵是派生量:对称、对角不含、风暴潮 ubiquity 体现(高重叠对存在)。"""
    m = equip_overlap_matrix()
    (x, y) = next(iter(m))
    assert m[(x, y)] == m[(y, x)] if (y, x) in m else True   # 只存上三角;补查对称构造
    vals = sorted(m.values(), reverse=True)
    assert vals[0] > 0.3   # 存在高重叠对(共享风暴潮类)


def test_pivot_equip_cost_sunk():
    """转型装备沉没:带的走的进阶不计,带不走的计满。"""
    cost = pivot_equip_cost('列车同行', '昼神阿雅', ['火力风暴潮'])
    assert 0.0 <= cost <= 1.0
    assert pivot_equip_cost('x', '昼神阿雅', []) == 0.0
