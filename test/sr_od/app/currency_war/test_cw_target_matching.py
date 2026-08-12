"""货币战争 target comp 牌归属匹配测试(流派/阵营全羁绊;ADR-0103)。

验证 ``_card_hits_target`` 用角色**全羁绊**(阵营 + 流派 + 独立)匹配 ``comp.factions`` —— 治本流派
断裂(旧 ``card.faction in target.factions`` 只阵营,流派主派 comp 的过渡/补充角色被误判 off-target)。

**起因**:实跑 DOT 队 P1 输 —— 艾丝妲/椒丘等持续伤害流派角色 ``card.faction``=银河学者/空(= ``Character.factions[0]``,只阵营)∉ DOT.factions([持续伤害(流派), 星核猎手(阵营)])→ commit 后被 prefilter 跳过 → 凑不出 2DOT 过渡。DOT 队为流派主派典型。
"""
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_decisions import (
    _card_hits_target,
    _char_synergies,
)


def test_char_synergies_includes_flows_and_independent() -> None:
    """_char_synergies 含流派 + 独立,不只阵营(factions[0])。"""
    assert _char_synergies("艾丝妲") == {"银河学者", "持续伤害"}
    assert _char_synergies("桑博") == {"贝洛伯格", "星间旅人", "持续伤害"}
    assert _char_synergies("椒丘") == {"持续伤害", "减益"}              # 阵营空,纯流派
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
