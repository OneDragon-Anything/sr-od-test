"""货币战争 角色领域模型(cw_chars)测试 —— 纯逻辑,不依赖游戏。

验证 Character model + CHARACTERS 注册表(V4.4 单一真相源):
- 注册表完整(全费用 1-5;规范名非粉丝缩写)。
- 查询:chars_by_cost / chars_by_faction / get_char。
- Character.position_pref:前台→front、后台→back、前后台→back。
- CHARACTER_ROSTER 从 CHARACTERS 派生。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.data.cw_chars import (
    CHARACTER_ROSTER,
    CHARACTERS,
    Character,
    chars_by_cost,
    chars_by_faction,
    get_char,
)
from sr_od.application.currency_war.data.cw_factions import FACTIONS


def test_registry_complete_all_costs() -> None:
    """注册表覆盖全费用 1-5;每条费用非空。"""
    for cost in range(1, 6):
        assert len(chars_by_cost(cost)) > 0, f"{cost}费应有角色"
    # 总数合理(V4.4 ~70+,开拓者按命途合并性别)
    assert len(CHARACTERS) > 60


def test_roster_derived_from_registry() -> None:
    """CHARACTER_ROSTER 是从 CHARACTERS 派生的规范名集合(单一真相源)。"""
    assert frozenset(CHARACTERS.keys()) == CHARACTER_ROSTER


def test_canonical_names_no_nicknames() -> None:
    """规范名集合禁粉丝缩写:Archer 在,红A 不在。"""
    assert "Archer" in CHARACTER_ROSTER
    assert "红A" not in CHARACTER_ROSTER
    assert "瓦尔特" in CHARACTER_ROSTER
    assert "杨叔" not in CHARACTER_ROSTER


def test_get_char_fields() -> None:
    """get_char 取 Character 字段:Archer 5费/前台/命运圣杯/战技点/独立魔术师。"""
    archer = get_char("Archer")
    assert archer is not None
    assert archer.cost == 5
    assert archer.position == "front"
    assert "命运圣杯" in archer.factions
    assert "战技点" in archer.flows
    assert archer.independent == "魔术师"
    assert get_char("不存在角色") is None, "未知名 → None"


def test_position_pref() -> None:
    """Character.position_pref:前台→front、后台→back、前后台(flex)→back。"""
    assert get_char("流萤").position_pref() == "front"      # 前台
    assert get_char("三月七").position_pref() == "back"     # 后台
    assert get_char("远坂凛").position_pref() == "back"     # 前后台→back 默认


def test_chars_by_faction() -> None:
    """chars_by_faction:仙舟含青雀;含流派(燃血含刃)。"""
    仙舟 = [c.name for c in chars_by_faction("仙舟")]
    assert "青雀" in 仙舟
    燃血 = [c.name for c in chars_by_faction("燃血")]
    assert "刃" in 燃血
    assert "万敌" in 燃血


def test_chars_by_cost_count() -> None:
    """费用分布(2026-08-15 勘误后):娜塔莎 1→3、爻光 2→1、罗刹 5→4(广场 config rarity+bwiki 双源)。

    旧断言 3费=13 来自 D牌期望表 77124902 实测点 v=13 —— 该实测点统计口径含娜塔莎错录 1 费,
    勘误后 3费=14。D牌期望表若重校,按新分布回归。
    """
    assert len(chars_by_cost(3)) == 14
    assert len(chars_by_cost(1)) == 20   # 19 + 停云(plaza 补录,专家顾问)
    assert len(chars_by_cost(5)) == 9    # 10 - 罗刹(5→4)
    # 勘误个体(广场 config rarity 权威值)
    assert CHARACTERS["娜塔莎"].cost == 3
    assert CHARACTERS["爻光"].cost == 1
    assert CHARACTERS["罗刹"].cost == 4
    # 停云补录(plaza id=1202,1费后台,仙舟+能量)
    assert CHARACTERS["停云"].cost == 1
    assert CHARACTERS["停云"].position == "back"
    assert "仙舟" in CHARACTERS["停云"].factions


def test_faction_members_cross_module() -> None:
    """FactionInfo.members() 跨模块从 CHARACTERS 反查(派生关系,非硬编码)。"""
    仙舟_info = FACTIONS["仙舟"]
    members = 仙舟_info.members()
    assert "青雀" in members
    assert len(members) > 0
    # 成员关系派生:改 CHARACTERS 自动传导(FactionInfo 不存 members 字段)
    assert not (hasattr(仙舟_info, "__dict__") and "members" in 仙舟_info.__dict__), (
        "members 是方法非存储字段(派生,单一真相源)"
    )


def test_character_is_frozen() -> None:
    """Character 是 frozen dataclass(注册表条目不可变,防误改)。"""
    c = get_char("青雀")
    assert isinstance(c, Character)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.cost = 9   # frozen → FrozenInstanceError


# ---- plaza 官方接口对拍守卫 ----
# plaza 数据层 cw_chars_data.py 已删(2026-09 治理审计:零消费,生成器改对拍器);
# 本守卫把「注册表 vs 官方接口」的对拍从纯口头升级为接线测试:抽查条目冻结自 plaza
# config API V4.4(与 tools/cw/gen_plaza_chars.py 数据源同源),随机抽 5 条比
# cost/position/traits。全量对拍跑 `uv run python tools/cw/gen_plaza_chars.py`。
_PLAZA_SAMPLE_POOL = (  # (plaza_id, 规范名, cost, 站位, traits);站位/费用=官方字段值
    ("1001", "三月七", 1, "Back", ("列车同行", "护盾")),
    ("1014", "Saber", 3, "Common", ("命运圣杯", "能量")),
    ("1202", "停云", 1, "Back", ("仙舟", "能量")),
    ("1304", "砂金", 2, "Front", ("公司", "追击", "护盾")),
    ("1408", "白厄", 3, "Front", ("救世主",)),
    ("1501", "火花", 4, "Front", ("星间旅人", "战技点", "欢愉")),
    ("15061", "银狼LV.999", 3, "Front", ("星核猎手", "欢愉", "头号玩家")),
    ("8009", "开拓者·欢愉", 4, "Back", ("列车同行", "能量", "欢愉")),
)
_PLAZA_POSITION = {"Front": "front", "Back": "back", "Common": "flex"}


def test_plaza_official_snapshot_guard() -> None:
    """随机抽 5 条 plaza 冻结条目,断言 cost/position/traits 与 CHARACTERS 一致。"""
    import random
    rng = random.Random(20260815)  # 固定种子:抽查集可复现(条目池见 _PLAZA_SAMPLE_POOL 注)
    for pid, name, cost, pos, traits in rng.sample(_PLAZA_SAMPLE_POOL, 5):
        ch = CHARACTERS[name]
        assert ch.cost == cost, f"{pid} {name}: cost {ch.cost} != plaza {cost}"
        assert ch.position == _PLAZA_POSITION[pos], f"{pid} {name}: position {ch.position} != plaza {pos}"
        reg_traits = set(ch.factions) | set(ch.flows) | ({ch.independent} if ch.independent else set())
        assert reg_traits == set(traits), f"{pid} {name}: traits {sorted(reg_traits)} != plaza {sorted(traits)}"
