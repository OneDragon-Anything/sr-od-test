"""装备价值共享机器锁(armory-box-value 迭代 landing 3.1;design 出处 =
changes/2026-09-12-armory-box-value/design.md §2.1-§2.3/§2.6)。

V 组 = 漂移锁(表平移快照/注册表形态快照/派生一致),S13 = wear 未锁态
stash 契合移除的行为变化锚点,末组 = pick_equipment 未锁退化路径。
纯逻辑帧,零副作用。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_equipment_data import (
    EQUIPMENTS,
    EQUIPMENT_ROSTER,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_equip_value import (
    EQUIP_GENERIC_VALUE,
    equip_material_generality,
    key_fit_names,
    key_recipe_pairs,
    pick_equipment,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.operations.cw_screen.cw_screen_equip_pick import (
    _resolve_locked_key_fit,
)

# V1 快照:EQUIP_GENERIC_VALUE 迁移源(cw_events._EQUIP_VALUE 退役前键集)。
# 分歧 = 平移漂移信号,先红后查(禁机械跟绿)。
_V1_SNAPSHOT_KEYS = frozenset({
    '反重力皮靴', '轮滑鞋', '永动机', '光能电池', '物质分解液', '绝对热量',
    '蓄能帆', '火力风暴潮', '高周波电锯', '冷笑话引擎', '光速螺旋桨',
    '动能激发剑', '虫洞掘进钻头', '电光履', '以牙还牙甲', '碎星斩舰刀',
    '热血沸腾拳', '自适应外骨骼', '斩首行动', '战场进化手册', '电磁弹射器',
    '反卫星狙击枪', '白昼·光速螺旋桨', '光速螺旋桨·特权', '火力风暴潮·特权',
    '以牙还牙甲·特权',
})

# V2 形态快照(单位 = 配方引用**条数**,自对配方双槽只计 1 条;
# 2026-09-12 实跑定值)。分歧 = 注册表变化信号,先红后改。
_V2_SNAPSHOT = {
    '生命之花': 10, '轮滑鞋': 10, '光能电池': 10, '以太钻头': 10,
    '折叠小刀': 10, '量产型装甲': 10, '和平手枪': 10, '幸运星': 10,
    '蓝钻': 11, '红钻': 11,
    '垃圾袋': 2,
    '火力风暴潮': 0, '反重力皮靴': 0,
}


def _direct_reference_counts() -> dict[str, int]:
    """V2 独立构造:直查 EQUIPMENTS 全量 recipes 的引用条数
    (每条配方内同材料只计 1;与机器实现分路,对拍防派生链 bug)。"""
    counts: dict[str, int] = {}
    for eq in EQUIPMENTS.values():
        for recipe in getattr(eq, 'recipes', ()) or ():
            for m in set(recipe):
                counts[m] = counts.get(m, 0) + 1
    return counts


def _direct_key_fit(key_equips) -> frozenset[str]:
    """V4 独立构造:直查 EQUIPMENTS.recipes 的成品 ∪ 材料全集。"""
    names: set[str] = set()
    for k in key_equips:
        if not k:
            continue
        names.add(k)
        eq = EQUIPMENTS.get(k)
        for recipe in getattr(eq, 'recipes', ()) or ():
            names.update(m for m in recipe if m)
    return frozenset(names)


def test_v1_generic_value_keys_snapshot_and_roster():
    """V1:EQUIP_GENERIC_VALUE 键集 = 迁移前 _EQUIP_VALUE 键集 ∧ ⊆ ROSTER
    (design landing 3.1;ADR-0298 注册表单一源判据)。"""
    assert set(EQUIP_GENERIC_VALUE) == _V1_SNAPSHOT_KEYS
    assert set(EQUIP_GENERIC_VALUE) <= EQUIPMENT_ROSTER


def test_v2_material_generality_independent_walk_and_shape_snapshot():
    """V2:机器引用条数 vs 独立直查构造逐名相等 + 注册表形态快照
    (简易域全体等值 10 条——虚构梯度退役的注册表证据,design §1.1 gap 4)。"""
    direct = _direct_reference_counts()
    for name in set(_V2_SNAPSHOT) | set(direct):
        assert equip_material_generality(name) == direct.get(name, 0), name
    for name, expected in _V2_SNAPSHOT.items():
        assert equip_material_generality(name) == expected, name


def test_v3_key_fit_names_subset_roster_and_superset_keys():
    """V3:全 comp 抽样——key_fit_names ⊆ EQUIPMENT_ROSTER ∧
    去重 keys ⊆ key_fit_names(design landing 3.1 V3)。"""
    for c in COMP_LIBRARY:
        fit = key_fit_names(c.key_equips)
        assert fit <= EQUIPMENT_ROSTER
        assert {k for k in c.key_equips if k} <= fit


def test_v4_key_fit_names_independent_construction():
    """V4:key_fit_names(机器派生) vs 直查 EQUIPMENTS.recipes 独立构造,
    全 comp 逐套相等(landing 3.1;两构造独立实现防派生链 bug)。"""
    for c in COMP_LIBRARY:
        assert key_fit_names(c.key_equips) == _direct_key_fit(c.key_equips)


def test_pick_equipment_unlocked_degenerate_paths():
    """未锁退化路径(landing 3.1):空 names → 0;空 key_equips = 纯 base
    排序(design §2.2 未锁态);全零 base 并列取先。"""
    assert pick_equipment([]) == 0
    assert pick_equipment(['幸运星', '火力风暴潮']) == 1   # base 0 vs 6
    assert pick_equipment(['垃圾袋', '火力风暴潮']) == 1   # mv 表外帧,base 生效
    assert pick_equipment(['垃圾袋', '幸运星']) == 0       # base 全 0,取先


def _stub_ctx(v3_intention) -> SimpleNamespace:
    """_resolve_locked_key_fit 桩:黑盒策略状态(getattr 通道)。"""
    session = SimpleNamespace(
        strategy_state=SimpleNamespace(v3_intention=v3_intention))
    return SimpleNamespace(cw_match=SimpleNamespace(session=session))


def test_s13_locked_state_resolves_key_fit():
    """S13 认领(landing 3.1):锁定态锚 = locked_comp → key_fit_names
    (反甲白厄实名;重复 key 需求由原序列承载)。"""
    ist = IntentionState(locked_comp='反甲白厄')
    fit = _resolve_locked_key_fit(_stub_ctx(ist))
    assert fit == _direct_key_fit(
        ['以牙还牙甲', '以牙还牙甲', '高周波电锯', '以牙还牙甲·特权',
         '热血沸腾拳'])
    assert '幸运星' in fit and '量产型装甲' in fit


def test_s13_unlocked_state_no_binding_despite_target_stash():
    """S13 行为变化锚点:未锁态即使 target/stash 带方向 key 也不再消费
    ——装备选择不绑囤牌方向(严格版裁定 5;design landing 3.1)。"""
    ist = IntentionState()   # locked_comp 恒空(伪 comp 帧形态)
    state = SimpleNamespace(
        v3_intention=ist,
        target_comp=SimpleNamespace(key_equips=('以牙还牙甲',)),
        stash_comp=SimpleNamespace(key_equips=('电光履',)),
    )
    ctx = SimpleNamespace(cw_match=SimpleNamespace(
        session=SimpleNamespace(strategy_state=state)))
    assert _resolve_locked_key_fit(ctx) == frozenset()
