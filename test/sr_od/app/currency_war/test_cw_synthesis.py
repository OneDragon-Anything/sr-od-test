"""货币战争 装备合成图谱(cw_synthesis)测试 —— 纯逻辑,不依赖游戏。

2026-08-26 光能电池系配方补齐(官方 API compose_list):光能电池=第 8 件基础件,
8 基础件 × K8 闭合 = C(8,2)=28 交叉 + 8 自配 = 36 件进阶全量。
旧「孤立节点」语义锁已反转(GUANGNENG_ONLY 废弃 → GUANGNENG_CROSS/SELF_RECIPES)。


出处:.dsh/skills/sr-od-currency-war-dev/references/data-collection.md;docs/develop/currency_war/decisions/0265-equip-component-reserve-p1.md(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from collections import Counter

from sr_od.application.currency_war.data import cw_synthesis as synth
from sr_od.application.currency_war.obs.cw_equipment import EQUIPMENT_ROSTER


def test_cross_recipe_graph_is_complete_k7() -> None:
    """7 件标准基础件构成完整 K7 两两合成图:C(7,2)=21 交叉,每件度数 6,无重复对。"""
    assert len(synth.CROSS_RECIPES) == 21
    assert len(synth.SYNTHESIS_BASES) == 7

    pairs = []
    for adv, (a, b) in synth.CROSS_RECIPES.items():
        assert a in synth.SYNTHESIS_BASES, f"{adv} 组件 {a} 非基础件"
        assert b in synth.SYNTHESIS_BASES, f"{adv} 组件 {b} 非基础件"
        assert a != b, f"{adv} 交叉配方两件相同(应入自配)"
        pairs.append(frozenset({a, b}))
    assert len(set(pairs)) == 21, "交叉配方有重复对"

    # 每件基础件在交叉图里度数恰为 6(与其余 6 件各配一次)
    deg: Counter[str] = Counter()
    for p in pairs:
        for x in p:
            deg[x] += 1
    assert set(deg) == set(synth.SYNTHESIS_BASES)
    assert all(v == 6 for v in deg.values()), f"K7 度数应全 6: {dict(deg)}"


def test_guangneng_cross_k7_view() -> None:
    """光能电池系交叉 7 件:光能电池×7 标准件各一件(度数 1 星型图)。"""
    assert len(synth.GUANGNENG_CROSS_RECIPES) == 7
    partners = []
    for adv, (a, b) in synth.GUANGNENG_CROSS_RECIPES.items():
        assert a == '光能电池' or b == '光能电池', f"{adv} 组件不含光能电池"
        other = b if a == '光能电池' else a
        assert other in synth.SYNTHESIS_BASES, f"{adv} 组件 {other} 非标准基础件"
        partners.append(other)
    assert sorted(partners) == sorted(synth.SYNTHESIS_BASES), "光能电池应与 7 件标准件各交叉一次"
    # 官方 API 锚点(绝对热量=光能电池+生命之花,run 26 实锤互证)
    assert synth.GUANGNENG_CROSS_RECIPES['绝对热量'] == ('光能电池', '生命之花')


def test_self_recipes_one_per_base() -> None:
    """自配配方 7 个(每件标准基础件 1 个进阶版)+ 光能电池自配(永动机)。"""
    assert len(synth.SELF_RECIPES) == 7
    bases_used = set(synth.SELF_RECIPES.values())
    assert bases_used == set(synth.SYNTHESIS_BASES), "每件基础件应有 1 个自配进阶"
    assert synth.SELF_RECIPES["反重力皮靴"] == "轮滑鞋"
    assert synth.GUANGNENG_SELF_RECIPES == {"永动机": "光能电池"}


def test_all_recipe_names_in_roster() -> None:
    """所有合成结果名(交叉+自配+光能系)都在装备注册表(OCR↔官方 API 双源对拍)。"""
    names = (set(synth.CROSS_RECIPES) | set(synth.SELF_RECIPES)
             | set(synth.GUANGNENG_CROSS_RECIPES) | set(synth.GUANGNENG_SELF_RECIPES))
    miss = [n for n in names if n not in EQUIPMENT_ROSTER]
    assert miss == [], f"注册表缺: {miss}"


def test_all_advanced_have_recipe() -> None:
    """36 件进阶全量有配方(K8 闭合;2026-08-26 官方 API 补齐后成立)。"""
    from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
    adv = [n for n, e in EQUIPMENTS.items() if e.category == '进阶']
    assert len(adv) == 36
    missing = [n for n in adv
               if not (synth.cross_components(n) or synth.self_base(n))]
    assert missing == [], f"进阶无配方: {missing}"


def test_recipe_groups_disjoint() -> None:
    """四组配方结果互不重叠(无歧义归属)。"""
    groups = [set(synth.CROSS_RECIPES), set(synth.SELF_RECIPES),
              set(synth.GUANGNENG_CROSS_RECIPES), set(synth.GUANGNENG_SELF_RECIPES)]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            assert not (groups[i] & groups[j]), f"组 {i}/{j} 重叠: {groups[i] & groups[j]}"


def test_reachability_helpers() -> None:
    """可达性查询:synthesize_target 顺序无关且不含自配;self_advance/self_base 双向(含光能电池系)。"""
    assert synth.synthesize_target("以太钻头", "轮滑鞋") == "光速螺旋桨"
    assert synth.synthesize_target("轮滑鞋", "以太钻头") == "光速螺旋桨"  # 顺序无关
    assert synth.synthesize_target("以太钻头", "以太钻头") is None  # 自配不走交叉
    assert synth.synthesize_target("以太钻头", "生命之花") == "物质分解液"
    # 光能电池系(官方 API,2026-08-26)
    assert synth.synthesize_target("光能电池", "以太钻头") == "行星钻地弹"
    assert synth.synthesize_target("光能电池", "光能电池") is None  # 自配不走交叉
    assert synth.cross_components("绝对热量") == ("光能电池", "生命之花")
    assert synth.cross_components("反重力皮靴") is None  # 自配,非交叉
    assert synth.self_advance("光能电池") == "永动机"
    assert synth.self_base("永动机") == "光能电池"
    assert synth.self_advance("轮滑鞋") == "反重力皮靴"
    assert synth.self_base("反重力皮靴") == "轮滑鞋"


def test_guangneng_not_isolated() -> None:
    """光能电池系已由官方 API 补齐配方(旧「孤立节点」语义反转,2026-08-26)。"""
    assert not hasattr(synth, 'GUANGNENG_ONLY'), "旧 GUANGNENG_ONLY 常量已废弃"
    assert "光能电池" not in synth.SYNTHESIS_BASES  # 仍不作标准基础件(8 基础件分两组管理)
    for adv in synth.GUANGNENG_CROSS_RECIPES:
        assert adv not in synth.CROSS_RECIPES
        assert adv not in synth.SELF_RECIPES
