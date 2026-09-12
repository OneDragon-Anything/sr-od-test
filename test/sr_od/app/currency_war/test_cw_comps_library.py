"""test_cw_comps_library 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- comp_v2: test_cw_comp_v2.py
- system_cards: test_cw_system_cards.py
- r405_component_reserve: test_cw_r405_component_reserve.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


# ==================== comp_v2 ====================

from collections import Counter

from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    V2_FAMILIES,
    Comp,
    EquipChoice,
    derive_key_equips,
    get_comp,
)
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
    """禁用矩阵对称性:盾系插件(护盾2/砂金/腾荒/杰帕德/**三月七**)对万敌燃血**全禁**。

    W55(R2 §2 断言扩面):三月七入盾系断言集——注册表 flows=("护盾",) 且效果含「行动护盾」,
    按判定法她是盾系单卡,旧矩阵漏行(三B 原文「砂金/腾荒/杰帕德**等**」的「等」即留此口)。
    行准入口径:官方机制事实留,单帖攻略行删(heuristic_ab B3)——旧断言中的
    杰帕德×吸仇恨互斥行(攻略 #48 单帖)已删,不再锁。
    """
    shield_plugins = {"护盾2", "砂金", "丹恒·腾荒", "杰帕德", "三月七"}
    for pid in shield_plugins:
        assert plugin_disabled(pid, "万敌燃血"), f"盾系 '{pid}' 未对万敌燃血禁用(矩阵漏行)"
        assert ("护盾" in PLUGIN_DISABLE_MATRIX[(pid, "万敌燃血")]
                or "盾" in PLUGIN_DISABLE_MATRIX[(pid, "万敌燃血")]), f"{pid} 禁用原因非盾系机制"
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


# ==================== system_cards ====================

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
    _recount_board,
)
from sr_od.application.currency_war.kernel.cw_system_cards import (
    _WEIGHT_PIECE,
    _WEIGHT_READINESS,
    SYSTEM_CARDS,
    blank_window_policy,
    card_active,
    card_engine_complete,
    card_pieces,
    engine_missing,
    pick_card_combination,
)


def _char(name: str, faction: str | None = None, row: str | None = None,
          star: int = 1, slot: int = 0) -> BenchChar:
    """注册表真值构造 BenchChar(faction/站位单一源;faction 可覆写流派口径,
    row=None 走注册表 position_pref)——system_cards/evolution/r405 三段共用
    (机械拼接期的双构造器与 _evolution_* 别名增殖已收敛)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=faction or (c.factions or ['?'])[0],
                     position_pref=row or c.position_pref())


def _state_with_deployed(names: list[str]) -> GameState:
    """构造 deployed + 同步 board 的单帧(char 身份=注册表真值)。

    ADR-0312(W50):_recount_board 已是**全集口径**(factions+flows+
    independent)——旧「首阵营聚合后手工补多阵营」的补丁循环随之删除
    (保留会双计)。"""
    st = GameState()
    st.deployed = [_char(n, slot=i) for i, n in enumerate(names)]
    st.board = _recount_board(st.deployed)
    return st


def _shop(names_factions: list[tuple[str, str]]) -> list[ShopCard]:
    return [ShopCard(x=i * 100, faction=f, name=n, cost=1)
            for i, (n, f) in enumerate(names_factions)]


# ---------- 1. 判据穷举锁(四卡正/反例) ----------

def test_xianzhou3_active_and_inactive():
    card = SYSTEM_CARDS['xianzhou3']
    # 正例:仙舟 ≥3(铁三角三人组)
    st = _state_with_deployed(['爻光', '藿藿', '丹恒·饮月'])
    assert card_active(card, _bridge(st)) is True
    # 反例:仙舟 2 人(档位未到)
    st2 = _state_with_deployed(['爻光', '藿藿'])
    assert card_active(card, _bridge(st2)) is False


def test_dot2_active_and_inactive():
    card = SYSTEM_CARDS['dot2']
    st = _state_with_deployed(['卡芙卡', '桑博'])
    assert card_active(card, _bridge(st)) is True
    st2 = _state_with_deployed(['卡芙卡'])
    assert card_active(card, _bridge(st2)) is False


def test_train2_active_and_inactive():
    card = SYSTEM_CARDS['train2']
    st = _state_with_deployed(['三月七', '姬子·启行'])
    assert card_active(card, _bridge(st)) is True
    st2 = _state_with_deployed(['三月七'])
    assert card_active(card, _bridge(st2)) is False


def test_seele_or_branch_and_amplifier_not_independent():
    card = SYSTEM_CARDS['seele']
    # 正例A(量子分支):希儿在场 + 量子 ≥2(希儿自身=量子1,符玄=量子2)
    st = _state_with_deployed(['希儿', '符玄'])
    assert card_active(card, _bridge(st)) is True
    # 正例B(贝洛伯格分支):希儿在场 + 贝洛伯格 ≥2(希儿自身=贝1,桑博=贝2)
    st2 = _state_with_deployed(['希儿', '桑博'])
    assert card_active(card, _bridge(st2)) is True
    # 反例:放大器不能独立(无希儿时量子 2 不当过渡;p1_definition 卡4)
    st3 = _state_with_deployed(['符玄', '花火'])
    assert card_active(card, _bridge(st3)) is False
    # 反例:希儿单卡无放大器(量子 1/贝 1 均不足;停云=仙舟,两分支都不沾)
    st5 = _state_with_deployed(['希儿', '停云'])
    assert card_active(card, _bridge(st5)) is False


# ---------- 2. 引擎完备度(铁三角不可拆/缺一=空壳) ----------

def test_engine_complete_xianzhou_trio_undividable():
    card = SYSTEM_CARDS['xianzhou3']
    trio = {'爻光', '藿藿', '丹恒·饮月'}
    assert card_engine_complete(card, trio) is True
    # 缺藿藿 = 空壳(功能链:饮月输出/爻光叠段/藿藿保血,各占一环不可拆)
    missing_one = trio - {'藿藿'}
    assert card_engine_complete(card, missing_one) is False
    assert engine_missing(card, missing_one) == ['藿藿']


def test_engine_complete_no_engine_cards_always_ok():
    for cid in ('dot2', 'train2'):
        assert SYSTEM_CARDS[cid].engine_required == []
        assert card_engine_complete(SYSTEM_CARDS[cid], set()) is True


def test_engine_required_and_star_goal_registry():
    """注册表教义锁:铁三角名单/星级目标(铁三角 2★、希儿 3★、其余不追)。"""
    xz = SYSTEM_CARDS['xianzhou3']
    assert set(xz.engine_required) == {'爻光', '藿藿', '丹恒·饮月'}
    assert xz.star_goal == {'爻光': 2, '藿藿': 2, '丹恒·饮月': 2}
    assert SYSTEM_CARDS['dot2'].star_goal == {}
    assert SYSTEM_CARDS['train2'].star_goal == {}
    assert SYSTEM_CARDS['seele'].star_goal == {'希儿': 3}
    assert SYSTEM_CARDS['seele'].engine_required == ['希儿']


# ---------- 3. 组合选择(来牌主判据/readiness 统一维度/意向/词条/等价性四项) ----------

def test_pick_dot2_wins_by_score_when_only_dot_pieces():
    """等价性②:仅 2 张 DOT 件在手 → DOT2 胜(原来靠首站加成,现在靠分;
    readiness=2/2 满格,其余系 0)。"""
    st = GameState()
    st.bench = [_char('卡芙卡'), _char('桑博')]
    st.board = {}
    dec = pick_card_combination(_bridge(st))
    assert dec.blank_window is False
    assert dec.chosen[0] == 'dot2'
    assert dec.scores['dot2'] == (2 * _WEIGHT_PIECE + 1.0 * _WEIGHT_READINESS)
    assert not any('首站' in r for r in dec.ruling)   # 特权措辞已删


def test_equiv_trio_full_hand_beats_dot():
    """等价性①:铁三角全在手+DOT2 可达 → 仙舟3 仍胜
    (原来靠例外条款直取,现在靠分:pieces 3>2 且 readiness 双满格)。"""
    st = GameState()
    st.bench = [_char('卡芙卡'), _char('桑博')]   # DOT 也可达,制造竞争
    st.deployed = [_char('爻光', slot=0, row='back'),
                   _char('藿藿', slot=1, row='back'),
                   _char('丹恒·饮月', slot=2, row='back')]
    st.board = _recount_board(st.deployed)
    dec = pick_card_combination(_bridge(st))
    assert dec.chosen[0] == 'xianzhou3'
    assert dec.scores['xianzhou3'] > dec.scores['dot2']
    assert not any('例外' in r or '一轮成型' in r for r in dec.ruling)   # 例外条款已删


def test_readiness_unified_across_cards():
    """readiness 统一维度:全卡按 pieces/激活件数折算(仙舟3=3、DOT2/列车2=2、
    希儿系≈3),门槛低=分高,无任何卡专属 if。"""
    # 2 仙舟件(readiness 2/3)vs 1 列车件(readiness 1/2):
    # pieces 2>1 主判据胜;readiness 0.667>0.5 同向
    st = GameState()
    st.bench = [_char('爻光'), _char('藿藿'), _char('三月七')]
    dec = pick_card_combination(_bridge(st))
    assert dec.chosen[0] == 'xianzhou3'
    assert dec.scores['xianzhou3'] == (2 * _WEIGHT_PIECE + 2 / 3 * _WEIGHT_READINESS)


def test_pick_arrival_is_primary_signal():
    """来牌主判据:无词条无意向时,件数多的体系胜出。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('姬子·启行'), _char('卡芙卡')]
    dec = pick_card_combination(_bridge(st))
    assert dec.chosen[0] == 'train2'   # 列车 2 件 > DOT 1 件


def test_pick_tie_break_ruling_nonempty_and_intent_breaks_tie():
    """同分构造:裁决记录非空;意向同向 tie-break 定向(非一票否决)。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('桑博')]   # 列车 1 件 vs DOT 1 件 = 同分
    dec = pick_card_combination(_bridge(st))
    assert dec.scores['train2'] == dec.scores['dot2']
    assert dec.ruling, '同分构造下裁决记录必须非空(C2 冻结要求)'
    assert any('tie-break' in r for r in dec.ruling)
    # 意向同向(希儿量子家族→seele 的映射没有;用 DOT 家族验证):
    dec2 = pick_card_combination(_bridge(st), intent='DOT卡芙卡')
    assert dec2.chosen[0] == 'dot2'
    # 意向非同向 = 不否决(列车仍可因来牌胜出/或 DOT 因意向翻越——只锁非崩溃+有记录)
    dec3 = pick_card_combination(_bridge(st), intent='希儿量子')
    assert any('非同向' in r for r in dec3.ruling)


def test_pick_affix_input_adjusts_dot():
    """词条前置输入:敌方频动旺(忍无可忍)→ DOT 权重升;净化身心 → DOT 权重降。"""
    st = GameState()
    st.bench = [_char('三月七'), _char('桑博')]   # 平分底
    dec_like = pick_card_combination(_bridge(st), affixes=['忍无可忍'])
    assert dec_like.chosen[0] == 'dot2'
    dec_fear = pick_card_combination(_bridge(st), affixes=['净化身心'])
    assert dec_fear.chosen[0] == 'train2'
    assert any('词条输入' in r for r in dec_fear.ruling)


def test_pick_seele_affix_fear_counter():
    """希儿系怕量子熄火(counter 警惕):3 件的领先被 fear(-3.0) 抵成落后。"""
    st = GameState()
    st.bench = [_char('希儿'), _char('符玄')]   # seele 件数 2(希儿引擎+符玄放大器,去重)
    dec = pick_card_combination(_bridge(st), affixes=['量子熄火'])
    assert SYSTEM_CARDS['seele'].affix_fears == ['量子熄火']
    assert card_pieces(SYSTEM_CARDS['seele'], _bridge(st)) == 2
    assert dec.scores['seele'] == (2 * _WEIGHT_PIECE + 2 / 3 * _WEIGHT_READINESS - 3.0)
    #   # 2 件(readiness 2/3)+ fear -3.0 = -0.33(counter 压制)


def test_pick_blank_when_nothing_arrived():
    """等价性④:空窗行为不变——四系 0 件(readiness 恒 0)→ blank_window=True,chosen=[]。"""
    st = GameState()
    # 灵砂=狼狩+治疗,不沾四系任一判据阵营(瓦尔特含列车同行,不可用)
    st.bench = [_char('灵砂')]
    dec = pick_card_combination(_bridge(st))
    assert dec.blank_window is True
    assert dec.chosen == []
    assert any('空窗' in r for r in dec.ruling)


# ---------- 4. 空窗期规则(目标件/费用带/不 D 牌) ----------

def test_blank_window_buy_target_only():
    """无体系+店有目标件 → 只买目标件;off-target 不进 buy_idx([31] 不为凑数 D)。"""
    st = GameState()
    st.bench = [_char('桑博')]   # 来牌方向=持续伤害(1 件)
    st.shop = _shop([('藿藿', '仙舟'),      # 引擎件(铁三角)→ 买
                     ('卡芙卡', '持续伤害'),  # 来牌方向件 → 买
                     ('停云', '仙舟'),        # 仙舟无来牌方向但停云=仙舟阵营……
                     ('瓦尔特', '星核猎手')])
    dec = blank_window_policy(_bridge(st))
    assert dec.is_blank is True
    assert dec.target_factions == ['持续伤害']
    assert '藿藿' in dec.target_char_ids and '希儿' in dec.target_char_ids
    assert 0 in dec.buy_idx and 1 in dec.buy_idx
    assert 3 not in dec.buy_idx          # off-target(星核猎手)绝不 D
    # 槽2 停云:阵营=仙舟 ∉ target_factions → 不买(仙舟无来牌迹象)
    assert 2 not in dec.buy_idx


def test_blank_window_cost_band_and_no_direction():
    """无来牌方向:仅引擎件见即买;费用带=引擎件费用众数(铁三角 1,1,2 + 希儿 3 → 1)。"""
    st = GameState()
    st.shop = _shop([('瓦尔特', '星核猎手')])
    dec = blank_window_policy(_bridge(st))
    assert dec.is_blank is True
    assert dec.target_factions == []
    assert dec.buy_idx == []            # 无目标件 → 不买(off-target 不 D)
    assert dec.cost_band == 1
    assert any('不为凑数' in r for r in dec.ruling)


def test_blank_window_not_blank_when_any_system_active():
    st = _state_with_deployed(['卡芙卡', '桑博'])   # DOT2 已激活
    dec = blank_window_policy(_bridge(st))
    assert dec.is_blank is False
    assert dec.buy_idx == []

# (evolution 节已随 kernel/cw_evolution 整模块退役删除——W8 本体切割批
#  (T-7)「模块删则锁随面退役」:该节锁演进工作帧行为,载体消亡即锁消亡;
#  comp 库数据锁(上文)不受影响。)
