"""货币战争 COMP_LIBRARY v2 十字段建库 + 插件注册表测试(W25,C4/C5 契约;纯逻辑)。

覆盖三块:
1. **key_equips 派生恒等**(C5 保活地基,裁决 2 顺序:先派生后数据):
   ``derive_key_equips(comp)`` 与旧手编 ``comp.key_equips`` 多重集恒等,20 套全过;
   equip_assign 为空的长尾套走旧值回退(旧读者不炸);
2. **v2 字段结构校验**(form_tiers_max/sub_tiers/equip_assign 键域/special_systems
   枚举/substitute_plan 必备键/branch_of 互指/family 域);
3. **插件注册表完整性**(22 单卡 + 15 小羁绊,建库基准=三B/三C;禁用矩阵引用有效
   + 盾系×万敌对称性:盾系插件[含三月七,W55 补行]对万敌燃血全禁)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from collections import Counter

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    V2_FAMILIES,
    Comp,
    EquipChoice,
    derive_key_equips,
    get_comp,
)
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel.cw_plugins import (
    PLUGIN_DISABLE_MATRIX,
    PLUGIN_LIBRARY,
    plugin_disabled,
)

# ===== 1. key_equips 派生恒等(C5;裁决 2:先于数据变更落地)=====


def test_derive_key_equips_identity_all_comps() -> None:
    """恒等不变量:derive_key_equips(comp) 与旧手编 key_equips 多重集相等,20 套全过。

    口径=多重集(Counter):equip_fit/合成材料判定等消费均为多重集语义;顺序差异仅影响
    equip_allocation 的 carry 按序取件微差(装备到人重排的预期副作用,非语义变更)。

    ⚠️ 本测试锁的是「两套表示不漂移」的 C5 兼容不变量,**不是**「到人正确」的 C4 语义
    (R2 §6 点名:恒等绿无法暴露到人错配——历史上 以牙还牙甲→三月七 类错误在本测试下恒绿)。
    到人语义由 test_equip_assign_doctrine_v2(W55 新增)承接;A/B 拆分批放开恒等时,
    本测试需改写为「到人对拍 v2 教义」方向(届时欠账才可见)。
    """
    assert len(COMP_LIBRARY) == 20
    for comp in COMP_LIBRARY:
        assert Counter(derive_key_equips(comp)) == Counter(comp.key_equips), (
            f"{comp.name}: derive 与旧手编 key_equips 不恒等(C5 兼容断裂)"
        )


def test_equip_assign_doctrine_v2() -> None:
    """到人教义锚(W55,R2 §1 四处旧值重排修正的语义锁——恒等测试锁不到这层)。

    依据 comp_definitions_v2.md 各套「装备」节(数据源=三B/三C 定稿文档):
    - 姬子列车 A 流铁三角:三月七=自适应外骨骼(吸仇恨刚需);以牙还牙甲属姬子(×2-3),
      **不得**再错给三月七(旧值重排残留,R2 §1 点名);
    - 狼尊:银狼=风暴潮+速度件(升费链要行动)→ 皮靴在身,电锯(非速度件)不在;
    - 圣杯A:Archer=战技点件(动能激发剑,战技点燃料层主C 本命件);
    - 圣杯线 闪闪=反重力皮靴(锁轴速度载体,41%)。
    """
    lt = get_comp("列车同行").equip_assign
    assert lt["三月七"] == ["自适应外骨骼"], "三月七=A 流铁三角吸仇恨件(外骨骼),非以牙还牙甲"
    assert "以牙还牙甲" not in derive_key_equips(get_comp("列车同行")), "甲属姬子A流(拆分批落位),当前条不得携带"
    wolf = get_comp("狼尊欢愉").equip_assign
    assert wolf["银狼LV.999"] == ["火力风暴潮", "反重力皮靴"], "银狼=风暴潮+速度件(皮靴)"
    honga = get_comp("命运圣杯红A").equip_assign
    assert "动能激发剑" in honga["Archer"], "Archer=战技点件(动能激发剑)"
    assert "高周波电锯" not in honga["Archer"], "电锯是旧平铺残件,v2 专属装备落地后须让位"
    assert get_comp("双王圣杯").equip_assign["吉尔伽美什"] == ["反重力皮靴"], "闪闪=反重力皮靴"


def test_derive_key_equips_fallback_when_no_assign() -> None:
    """equip_assign 为空(长尾/未迁移套)→ 派生返回旧手编值的拷贝(旧读者不炸)。"""
    c = Comp(name="t", factions=["追击"], core_chars=["飞霄"], form_tiers={"追击": 3},
             strength="B", form_difficulty="medium", key_equips=["a", "a", "b"])
    out = derive_key_equips(c)
    assert out == ["a", "a", "b"]
    out.append("x")   # 拷贝语义:改派生结果不回写手编值
    assert c.key_equips == ["a", "a", "b"]


def test_derive_key_equips_pool_expands_all_candidates() -> None:
    """pool 条目贡献全部候选(候选池内每件都是关键件,黄泉第四件类);fixed 原样。"""
    c = Comp(name="t", factions=[], core_chars=["黄泉"], form_tiers={}, strength="A",
             form_difficulty="medium",
             equip_assign={"黄泉": ["电锯", EquipChoice("pool", ("永动机", "螺旋桨"))]})
    assert Counter(derive_key_equips(c)) == Counter(["电锯", "永动机", "螺旋桨"])


# ===== 2. v2 字段结构校验(C4 schema 锁)=====

V2_COMP_NAMES = {c.name for c in COMP_LIBRARY if c.family != "legacy"}
_SUB_PLAN_KEYS = {"替班者", "顶位", "身份", "分岔点"}
_SPECIAL_SYSTEM_KEYS = {"navigator", "grail_quest", "aha_slots", "cost_escalation"}


def test_v2_family_annotation() -> None:
    """family 域:9 家族 + 'legacy';12 套 v2 家族 comp 落 9 家族;8 套长尾保活。"""
    for comp in COMP_LIBRARY:
        assert comp.family in V2_FAMILIES or comp.family == "legacy", comp.name
    n_v2 = sum(1 for c in COMP_LIBRARY if c.family != "legacy")
    n_legacy = sum(1 for c in COMP_LIBRARY if c.family == "legacy")
    assert n_v2 == 12 and n_legacy == 8
    assert {c.family for c in COMP_LIBRARY if c.family != "legacy"} <= set(V2_FAMILIES)


def test_form_tiers_max_schema() -> None:
    """form_tiers_max 键 ⊆ form_tiers 键;值 ≥ 下限(裁决 5:form_tiers 保 int=下限)。"""
    for comp in COMP_LIBRARY:
        for k, hi in comp.form_tiers_max.items():
            assert k in comp.form_tiers, f"{comp.name}.form_tiers_max[{k}] 不在 form_tiers 键内"
            assert hi >= comp.form_tiers[k], f"{comp.name}.form_tiers_max[{k}]={hi} < 下限 {comp.form_tiers[k]}"
    # 区间教义抽查:万敌 燃血4-6 / 狼尊 欢愉5-7 / 黄泉 减益4-6(comp_definitions_v2)
    assert get_comp("万敌单C").form_tiers_max["燃血"] == 6
    assert get_comp("狼尊欢愉").form_tiers_max["欢愉"] == 7
    assert get_comp("黄泉减益").form_tiers_max["减益"] == 6


def test_sub_tiers_schema() -> None:
    """sub_tiers:键是羁绊规范名(FACTIONS 注册表)、不与主档 form_tiers 重复;值为正 int/区间。"""
    for comp in COMP_LIBRARY:
        for k, v in comp.sub_tiers.items():
            assert k in FACTIONS, f"{comp.name}.sub_tiers[{k}] 非规范羁绊名"
            assert k not in comp.form_tiers, f"{comp.name}.sub_tiers[{k}] 与主档重复"
            lo, hi = v if isinstance(v, tuple) else (v, v)
            assert 0 < lo <= hi, f"{comp.name}.sub_tiers[{k}]={v} 非法档深"
    # 教义抽查:万敌 战技点2(90% 第三引擎)
    assert get_comp("万敌单C").sub_tiers == {"战技点": 2}


def test_equip_assign_key_domain() -> None:
    """equip_assign 键 ⊆ core ∪ shared ∪ substitute_plan 替班者(到人口径);值元素合法。"""
    for comp in COMP_LIBRARY:
        allowed = (set(comp.core_chars) | set(comp.shared_chars)
                   | {s["替班者"] for s in comp.substitute_plan})
        for person, items in comp.equip_assign.items():
            assert person in allowed, f"{comp.name}.equip_assign 键 '{person}' 不在到人域内"
            assert items, f"{comp.name}.equip_assign['{person}'] 空序列"
            for it in items:
                if isinstance(it, EquipChoice):
                    assert it.kind in ("fixed", "pool") and it.choices, f"{comp.name}:{person} 非法 EquipChoice"
                else:
                    assert isinstance(it, str) and it, f"{comp.name}:{person} 非法条目 {it!r}"
    # 12 套 v2 家族 comp 均已到人化(长尾留空走回退)
    assert sum(1 for c in COMP_LIBRARY if c.equip_assign) == 12


def test_equip_taboos_wandi_doctrine() -> None:
    """万敌禁一切护盾件(官方:燃血无法获盾,受盾转微回血=负资产)——教义逐条对原文。"""
    taboos = set(get_comp("万敌单C").equip_taboos)
    assert "护盾件(类)" in taboos
    assert "以牙还牙甲" in taboos and "掩体生成枪" in taboos   # 连带盾类装备全禁


def test_equip_synergy_jizi_iron_triangle() -> None:
    """姬子线铁三角:外骨骼吸仇恨→以牙还牙甲反伤→皮靴加速,少一件链断(教义手编)。"""
    syn = get_comp("列车同行").equip_synergy
    assert syn and "铁三角" in syn and "少一件链断" in syn["铁三角"]


def test_substitute_plan_schema_and_no_transition_residue() -> None:
    """替班结构四必备键;替班者不得留在 transition_chars(C4 验收 4:无「替班者后期卖」残留)。"""
    for comp in COMP_LIBRARY:
        for s in comp.substitute_plan:
            assert set(s) == _SUB_PLAN_KEYS, f"{comp.name}.substitute_plan 键集 {set(s)}"
            assert s["替班者"] not in comp.transition_chars, (
                f"{comp.name}: 替班者 '{s['替班者']}' 仍在 transition_chars(卖出语义残留)"
            )
    # 教义抽查:狼尊 绯英替班(不卖,降副C沉淀)/红A Saber 接力
    wolf = {s["替班者"] for s in get_comp("狼尊欢愉").substitute_plan}
    assert "绯英" in wolf
    honga = {s["替班者"] for s in get_comp("命运圣杯红A").substitute_plan}
    assert "Saber" in honga
    # core 不再挂 transition(迁移完成抽检)
    for name, core in [("DOT队", "卡芙卡"), ("反甲白厄", "三月七"), ("大黑塔银河学者", "黑塔")]:
        assert core not in get_comp(name).transition_chars, f"{name}: core '{core}' 残留 transition"


def test_special_systems_enum_and_doctrine() -> None:
    """special_systems 键 ⊆ 已知四枚举(开放);圣杯任务链/领航员/阿哈/升费链教义在场。"""
    for comp in COMP_LIBRARY:
        for k in comp.special_systems:
            assert k in _SPECIAL_SYSTEM_KEYS, f"{comp.name}.special_systems 未知键 '{k}'"
    assert "navigator" in get_comp("列车同行").special_systems
    assert "grail_quest" in get_comp("命运圣杯红A").special_systems
    wolf = get_comp("狼尊欢愉").special_systems
    assert "aha_slots" in wolf and "cost_escalation" in wolf
    assert wolf["cost_escalation"]["目标费"] == 5   # 银狼养至 5 费


def test_branch_of_mutual_pointer() -> None:
    """branch_of 互指(兄弟套指针)且同 family(欢愉族/圣杯双C 两对)。"""
    by_name = {c.name: c for c in COMP_LIBRARY}
    for comp in COMP_LIBRARY:
        if comp.branch_of:
            sib = by_name.get(comp.branch_of)
            assert sib is not None, f"{comp.name}.branch_of 指向不存在套 '{comp.branch_of}'"
            assert sib.family == comp.family, f"{comp.name}/{sib.name} family 不一致"
            assert sib.branch_of == comp.name, f"{comp.name}/{sib.name} branch_of 未互指"
    assert len([c for c in COMP_LIBRARY if c.branch_of]) == 4   # 两对互指


def test_free_slots_schema() -> None:
    """自由槽结构:row/tags/说明 三键;带标签即坐不点名。"""
    for comp in COMP_LIBRARY:
        for fs in comp.free_slots:
            assert set(fs) == {"row", "tags", "说明"}, f"{comp.name}.free_slots 键集 {set(fs)}"
            assert fs["row"] in ("front", "back") and fs["tags"]
    assert any("量子" in "、".join(fs["tags"]) or "量子同频" in fs["tags"]
               for fs in get_comp("希儿量子").free_slots)   # 量子槽教义


# ===== 3. 插件注册表完整性(建库基准=comp_elements 三B/三C 最晚定稿节)=====


def test_plugin_library_counts_and_schema() -> None:
    """22 单卡(三B:T1=6/T2=7/T3=9)+ 15 小羁绊(三C:T1=3/T2=3/T3=9 含角色特定 2)。

    W55(R2 §2 🔴 断言改造):小羁绊锁 **15** 而非 14——三C 定稿 T3 名单明列 7 个队员口径件
    (星核2/贝洛伯格2/夜半2/学者2/公司2/**圣杯2**/击破2)+ 角色特定 2;建库时 圣杯2 被静默
    丢弃(无出池记录)且被旧断言 smalls==14 固化——错误值被测试保护的典型(R2 §2/§6)。
    """
    units = [p for p in PLUGIN_LIBRARY.values() if p.kind == "unit"]
    smalls = [p for p in PLUGIN_LIBRARY.values() if p.kind == "small_faction"]
    assert len(units) == 22 and len(smalls) == 15
    ids = [p.plugin_id for p in (*units, *smalls)]
    assert len(set(ids)) == 37   # id 无重复
    unit_tier = Counter(p.tier for p in units)
    assert unit_tier == {"T1": 6, "T2": 7, "T3": 9}
    small_tier = Counter(p.tier for p in smalls)
    assert small_tier == {"T1": 3, "T2": 3, "T3": 9}
    for p in PLUGIN_LIBRARY.values():
        assert p.kind in ("unit", "small_faction")
        assert p.tier in ("T1", "T2", "T3")
        assert p.effect_scope in ("team", "member", "char")
        assert p.source, f"{p.plugin_id} 缺证据指针"
        assert set(p.majority_lines) <= set(V2_FAMILIES), f"{p.plugin_id} majority_lines 域外家族"
    # 三B 定稿要点:椒丘被剔除(v3)不入池;巡海游侠1 出池(三C)
    assert "椒丘" not in PLUGIN_LIBRARY
    assert "巡海游侠1" not in PLUGIN_LIBRARY
    # 三C 定稿 15 件全落(W55 🔴):圣杯2 在库
    assert "圣杯2" in PLUGIN_LIBRARY
    # 规范名(R2 §2):单卡 plugin_id 必须是 CHARACTERS 注册表键(买门按名匹配)
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    for p in units:
        assert p.plugin_id in CHARACTERS, f"单卡 plugin_id '{p.plugin_id}' 非注册表规范名(买门永不命中)"


def test_plugin_disable_matrix_symmetry_shield_vs_wandi() -> None:
    """禁用矩阵对称性:盾系插件(护盾2/砂金/腾荒/杰帕德/**三月七**)对万敌燃血**全禁**;
    杰帕德对两个吸仇恨流(姬子列车/白厄反甲)全禁。

    W55(R2 §2 断言扩面):三月七入盾系断言集——注册表 flows=("护盾",) 且效果含「行动护盾」,
    按判定法她是盾系单卡,旧矩阵漏行(三B 原文「砂金/腾荒/杰帕德**等**」的「等」即留此口)。
    """
    shield_plugins = {"护盾2", "砂金", "丹恒·腾荒", "杰帕德", "三月七"}
    for pid in shield_plugins:
        assert plugin_disabled(pid, "万敌燃血"), f"盾系 '{pid}' 未对万敌燃血禁用(矩阵漏行)"
        assert ("护盾" in PLUGIN_DISABLE_MATRIX[(pid, "万敌燃血")]
                or "盾" in PLUGIN_DISABLE_MATRIX[(pid, "万敌燃血")]), f"{pid} 禁用原因非盾系机制"
    assert plugin_disabled("杰帕德", "姬子列车") is not None
    assert plugin_disabled("杰帕德", "白厄反甲") is not None
    # 非盾件不禁用(负例)
    assert plugin_disabled("知更鸟", "万敌燃血") is None
    assert plugin_disabled("治疗2", "万敌燃血") is None   # 弱不适配不进硬矩阵


def test_plugin_disable_matrix_references_valid() -> None:
    """矩阵引用完整:plugin_id ∈ PLUGIN_LIBRARY;line ∈ 家族键 ∪ comp 名。"""
    lines = set(V2_FAMILIES) | {c.name for c in COMP_LIBRARY}
    for (pid, line), reason in PLUGIN_DISABLE_MATRIX.items():
        assert pid in PLUGIN_LIBRARY, f"矩阵引用未知插件 '{pid}'"
        assert line in lines, f"矩阵引用未知线 '{line}'"
        assert reason, f"({pid},{line}) 缺机制原因"


def test_plugin_majority_lines_doctrine() -> None:
    """线内身份标注抽查(过半=已是骨架,插件身份不在该线成立):
    战技点2×万敌(90%)/护盾2×姬子列车(50%)/三月七双身份(姬子88/白厄87)。"""
    assert "万敌燃血" in PLUGIN_LIBRARY["战技点2"].majority_lines
    assert "姬子列车" in PLUGIN_LIBRARY["护盾2"].majority_lines
    assert PLUGIN_LIBRARY["三月七"].majority_lines == frozenset({"姬子列车", "白厄反甲"})
    # majority_lines 与 Comp.sub_tiers 互为对拍锚(升格单一写入口的两端同时在库)
    wandi = get_comp("万敌单C")
    assert "战技点" in wandi.sub_tiers   # 过半副档已同步落 sub_tiers
