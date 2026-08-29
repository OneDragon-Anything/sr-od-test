"""货币战争 target comp 牌归属匹配测试(流派/阵营全羁绊;ADR-0103)。

验证 ``_card_hits_target`` 用角色**全羁绊**(阵营 + 流派 + 独立)匹配 ``comp.factions`` —— 治本流派
断裂(旧 ``card.faction in target.factions`` 只阵营,流派主派 comp 的过渡/补充角色被误判 off-target)。

**起因**:实跑 DOT 队 P1 输 —— 艾丝妲/椒丘等持续伤害流派角色 ``card.faction``=银河学者/空(= ``Character.factions[0]``,只阵营)∉ DOT.factions([持续伤害(流派), 星核猎手(阵营)])→ commit 后被 prefilter 跳过 → 凑不出 2DOT 过渡。DOT 队为流派主派典型。
"""
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_deploy_seat import _card_hits_target
from sr_od.application.currency_war.kernel.cw_economy import _char_synergies


def test_char_synergies_includes_flows_and_independent() -> None:
    """_char_synergies 含流派 + 独立,不只阵营(factions[0])。"""
    assert _char_synergies("艾丝妲") == {"银河学者", "持续伤害"}
    assert _char_synergies("桑博") == {"贝洛伯格", "星间旅人", "持续伤害"}
    assert _char_synergies("椒丘") == {"狼狩", "持续伤害", "减益"}      # trait 对齐 plaza:+狼狩(2026-08-15)
    assert _char_synergies("姬子·启行") == {"列车同行", "领航员"}       # 含独立羁绊
    assert _char_synergies("未识别角色") == set()                       # 不在注册表 → 空


def test_card_hits_target_flow_main_comp() -> None:
    """DOT 队(持续伤害流派 + 星核猎手阵营):流派角色识别为 target(治本:不再误判 off-target)。"""
    dot = get_comp("DOT队")
    assert dot is not None
    # 持续伤害流派角色(非 core)→ 全羁绊 ∩ DOT.factions 命中(旧 bug 处:被当 off-target 跳过)
    assert _card_hits_target("艾丝妲", "银河学者", dot) is True
    assert _card_hits_target("椒丘", "?", dot) is True                  # 阵营空,流派持续伤害命中
    # 星核猎手阵营角色 → 命中
    assert _card_hits_target("流萤", "星核猎手", dot) is True
    # core_chars → 命中(无论阵营)
    assert _card_hits_target("桑博", "贝洛伯格", dot) is True
    assert _card_hits_target("黑天鹅", "盛会之星", dot) is True


def test_card_hits_target_true_offtarget() -> None:
    """真 off-target(既非持续伤害也非星核猎手)→ False。"""
    dot = get_comp("DOT队")
    assert dot is not None
    assert _card_hits_target("佩拉", "贝洛伯格", dot) is False          # 贝洛伯格,无 dot 羁绊
    assert _card_hits_target("三月七", "列车同行", dot) is False
    assert _card_hits_target("藿藿", "仙舟", dot) is False


def test_card_hits_target_unidentified_faction_fallback() -> None:
    """name 未识别(空)→ 用 OCR faction 兜底:name 空时查注册表得空,仅 faction 一个阵营判。"""
    dot = get_comp("DOT队")
    assert dot is not None
    assert _card_hits_target("", "星核猎手", dot) is True               # faction 兜底命中星核猎手
    assert _card_hits_target("", "贝洛伯格", dot) is False              # faction 兜底不命中
    assert _card_hits_target("", "?", dot) is False                     # 全未知 → off-target


# ===== ADR-0152 M25 修正:flex 买牌配对纪律(_card_supports_target) =====
def test_card_supports_target_pair_discipline() -> None:
    """flex 单张散买 = off-target(M25 实证 8 阵营各 1 spread);成对深化 + 枢纽单买放行。"""
    from sr_od.application.currency_war.kernel.cw_deploy_seat import _card_supports_target
    from sr_od.application.currency_war.kernel.cw_state import GameState

    lt = get_comp("列车同行")
    # 大丽花(盛会之星=flex):板上无盛会之星 → 散买拒
    empty = GameState()
    assert _card_supports_target("大丽花", "盛会之星", empty, lt) is False
    # 板已有 盛会之星 1 → 成对深化放行
    paired = GameState(board={"盛会之星": 1})
    assert _card_supports_target("大丽花", "盛会之星", paired, lt) is True
    # 枢纽早期核心(千冶·刃):空板也放行(M3 单买=开局)
    assert _card_supports_target("千冶·刃", "星核猎手", empty, lt) is True
    # 核心(三月七):恒放行
    assert _card_supports_target("三月七", "列车同行", empty, lt) is True
    # 真 off-target(佩拉,贝洛伯格∉列车任何档):恒拒
    assert _card_supports_target("佩拉", "贝洛伯格", paired, lt) is False


# ===== ADR-0154 M7 装备角色级分配(equip_allocation) =====
def test_equip_allocation_carry_first() -> None:
    """carry 先拿 key_equips 按序(multiplicity);其余 core 次之;容量上限 3。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_comps import EQUIP_CAPACITY, equip_allocation

    lt = get_comp("列车同行")   # key_equips: 风暴潮×1/电锯/自适应外骨骼/冷笑话(W55);carry=姬子·启行
    dep = [SimpleNamespace(char_id='三月七', position_pref='back', slot=1),
           SimpleNamespace(char_id='姬子·启行', position_pref='front', slot=2)]
    # W55(R2 §1):池内 以牙还牙甲→自适应外骨骼(三月七=A 流吸仇恨件,甲属姬子拆分批)
    alloc = equip_allocation(lt, dep, ['火力风暴潮', '高周波电锯', '自适应外骨骼', '蓄能帆'])
    # 姬子(carry)按序拿 key(API 口径:风暴/电锯/外骨骼;ADR-0209 换血)
    jz = [e for c, e in alloc if c == '姬子·启行']
    assert jz == ['火力风暴潮', '高周波电锯', '自适应外骨骼'], f"carry 按序拿 key,得 {jz}"
    # 三月七(core)拿第四件(自适应外骨骼不在池 → 通用兜底:蓄能帆)
    sy = [e for c, e in alloc if c == '三月七']
    assert sy == ['蓄能帆'], f"core 兜底拿剩余,得 {sy}"


def test_equip_allocation_capacity_and_fallback() -> None:
    """容量扣减(已穿 3 = 满)与 comp=None 通用兜底(r232 轮转)。

    r232 行为变更(用户实锤「无脑给前台1」修复):comp=None
    从「deployed 顺序灌满第一人」改为**轮转分配**(每人 1 件
    一圈再回头)——前排先序保留,但不再独占。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation

    dep = [SimpleNamespace(char_id='瓦尔特', position_pref='front', slot=1),
           SimpleNamespace(char_id='符玄', position_pref='back', slot=2)]
    # comp=None → 轮转:瓦尔特先拿第一件,符玄拿第二件
    # (r232 前:瓦尔特全拿)
    alloc = equip_allocation(None, dep, ['永动机', '蓄能帆'])
    assert alloc == [('瓦尔特', '永动机'), ('符玄', '蓄能帆')]
    # 容量:瓦尔特已穿满 3 → 让位给符玄
    occ = {('front', 1): ['a', 'b', 'c']}
    alloc2 = equip_allocation(None, dep, ['永动机'], occ)
    assert alloc2 == [('符玄', '永动机')]
