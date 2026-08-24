"""货币战争 target comp 牌归属匹配测试(流派/阵营全羁绊;ADR-0103)。

验证 ``_card_hits_target`` 用角色**全羁绊**(阵营 + 流派 + 独立)匹配 ``comp.factions`` —— 治本流派
断裂(旧 ``card.faction in target.factions`` 只阵营,流派主派 comp 的过渡/补充角色被误判 off-target)。

**起因**:实跑 DOT 队 P1 输 —— 艾丝妲/椒丘等持续伤害流派角色 ``card.faction``=银河学者/空(= ``Character.factions[0]``,只阵营)∉ DOT.factions([持续伤害(流派), 星核猎手(阵营)])→ commit 后被 prefilter 跳过 → 凑不出 2DOT 过渡。DOT 队为流派主派典型。
"""
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_evaluate import _card_hits_target
from sr_od.application.currency_war.cw_economy import _char_synergies


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
    from sr_od.application.currency_war.cw_plan import _card_supports_target
    from sr_od.application.currency_war.cw_state import GameState

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


# ===== ADR-0149 凑牌节奏(P1 骨架驱动买 + 无损窗口 + 兜底) =====
def test_skeleton_buy_ok_three_categories() -> None:
    """骨架合法买三类:枢纽池单买 / 骨架羁绊配对 / 通用填充件;散买骨架单张拒。"""
    from sr_od.application.currency_war.cw_plan import _skeleton_buy_ok
    from sr_od.application.currency_war.cw_state import GameState

    empty = GameState()
    # ① 枢纽池(TEMPO/EARLY)单买放行(藿藿 Early 265 次;千冶·刃存活 0.96)
    assert _skeleton_buy_ok("藿藿", "仙舟", empty) is True
    assert _skeleton_buy_ok("千冶·刃", "星核猎手", empty) is True
    # ② 骨架羁绊配对(评审Y1 收窄:凑**能激活档**的成对):佩拉(贝洛伯格 min_tier=2)板上
    # 已有 1 → 买第 2 张即激活 tier-1 → 放行;空板散买拒。镜流(狼狩 min_tier=3)board 1 张
    # 买第 2 张不激活任何效果 → 也拒(白占位)。
    # (丹恒·饮月在 TEMPO_POOL 恒放行,不作本例)
    assert _skeleton_buy_ok("佩拉", "贝洛伯格", GameState(board={"贝洛伯格": 1})) is True
    assert _skeleton_buy_ok("佩拉", "贝洛伯格", empty) is False
    assert _skeleton_buy_ok("镜流", "狼狩", GameState(board={"狼狩": 1})) is False
    # ③ 通用填充件(星期日):板未满放行
    assert _skeleton_buy_ok("星期日", "能量", empty) is True
    # 非骨架羁绊散买(追击 非骨架集):拒
    assert _skeleton_buy_ok("托帕&账账", "追击", GameState(board={"追击": 1})) is False


def test_plan_no_loss_window_skeleton_fallback_buy() -> None:
    """ADR-0149 兜底:无动作 + 金<20 + 商店有骨架件 → 规则直买(M22 r4 金21 空手病)。

    eval 对单张骨架件 delta 恒负(新阵营/掉金),门放行 eval 也不选 → 兜底规则优先。
    """
    import random as _random
    from types import SimpleNamespace

    from sr_od.application.currency_war.cw_plan import plan
    from sr_od.application.currency_war.cw_state import GameState, ShopCard

    cfg = SimpleNamespace(
        faction_priority=[], character_priority=[],
        character_build_around=["姬子·启行"],   # 锁列车同行 target(过滤只留列车)
        character_forbid=[], faction_forbid=[], faction_priority_extra=[],
    )
    state = GameState(
        gold=13, round_num=4, level=3, plane=1,
        shop=[ShopCard(x=1, faction="仙舟", name="藿藿", cost=1),
              ShopCard(x=2, faction="追击", name="托帕&账账", cost=5)],   # 无 target 卡
    )
    actions = plan(state, cfg, cfg.faction_priority, rng=_random.Random(0))
    buys = [a for a in actions if type(a).__name__ == 'BuyCard']
    assert buys, "金13(1息档)+ 商店有 TEMPO 枢纽(藿藿)→ 不该空手(ADR-0149 兜底)"
    assert buys[0].card.name == "藿藿"


# ===== ADR-0154 M7 装备角色级分配(equip_allocation) =====
def test_equip_allocation_carry_first() -> None:
    """carry 先拿 key_equips 按序(multiplicity);其余 core 次之;容量上限 3。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.cw_comps import EQUIP_CAPACITY, equip_allocation

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

    from sr_od.application.currency_war.cw_comps import equip_allocation

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
