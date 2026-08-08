"""货币战争 装备合成图谱(cw_synthesis)测试 —— 纯逻辑,不依赖游戏。"""
from __future__ import annotations

from collections import Counter

from sr_od.application.currency_war import cw_synthesis as synth
from sr_od.application.currency_war.cw_equipment import EQUIPMENT_ROSTER


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


def test_self_recipes_one_per_base() -> None:
    """自配配方 7 个(每件基础件 1 个进阶版);反重力皮靴=2×轮滑鞋 攻略确证。"""
    assert len(synth.SELF_RECIPES) == 7
    bases_used = set(synth.SELF_RECIPES.values())
    assert bases_used == set(synth.SYNTHESIS_BASES), "每件基础件应有 1 个自配进阶"
    assert synth.SELF_RECIPES["反重力皮靴"] == "轮滑鞋"


def test_all_recipe_names_in_roster() -> None:
    """所有合成结果名(交叉+自配+光能)都在装备注册表(OCR↔米游社双源对拍)。"""
    names = set(synth.CROSS_RECIPES) | set(synth.SELF_RECIPES) | set(synth.GUANGNENG_ONLY)
    miss = [n for n in names if n not in EQUIPMENT_ROSTER]
    assert miss == [], f"注册表缺: {miss}"


def test_recipe_groups_disjoint() -> None:
    """交叉/自配/光能 三组结果互不重叠(无歧义归属)。"""
    assert not (set(synth.CROSS_RECIPES) & set(synth.SELF_RECIPES))
    assert not (set(synth.CROSS_RECIPES) & set(synth.GUANGNENG_ONLY))
    assert not (set(synth.SELF_RECIPES) & set(synth.GUANGNENG_ONLY))


def test_reachability_helpers() -> None:
    """可达性查询:synthesize_target 顺序无关且不含自配;self_advance/self_base 双向。"""
    assert synth.synthesize_target("以太钻头", "轮滑鞋") == "光速螺旋桨"
    assert synth.synthesize_target("轮滑鞋", "以太钻头") == "光速螺旋桨"  # 顺序无关
    assert synth.synthesize_target("以太钻头", "以太钻头") is None  # 自配不走交叉
    assert synth.synthesize_target("以太钻头", "生命之花") == "物质分解液"

    assert synth.cross_components("流星飞翼") == ("轮滑鞋", "量产型装甲")
    assert synth.cross_components("反重力皮靴") is None  # 自配,非交叉

    assert synth.self_advance("轮滑鞋") == "反重力皮靴"
    assert synth.self_base("反重力皮靴") == "轮滑鞋"
    assert synth.self_advance("光能电池") is None  # 光能电池非标准基础件


def test_guangneng_isolated() -> None:
    """光能电池 7 进阶与标准 K7 零交叉(孤立节点,机理待游戏内核实)。"""
    assert len(synth.GUANGNENG_ONLY) == 7
    assert "光能电池" not in synth.SYNTHESIS_BASES  # 光能电池不作为标准基础件
    for adv in synth.GUANGNENG_ONLY:
        assert adv not in synth.CROSS_RECIPES
        assert adv not in synth.SELF_RECIPES
