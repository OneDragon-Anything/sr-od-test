"""货币战争 角色领域模型(cw_chars)测试 —— 纯逻辑,不依赖游戏。

验证 Character model + CHARACTERS 注册表(V4.4 单一真相源):
- 注册表完整(全费用 1-5;规范名非粉丝缩写)。
- 查询:chars_by_cost / chars_by_faction / get_char。
- Character.position_pref:前台→front、后台→back、前后台→back。
- CHARACTER_ROSTER 从 CHARACTERS 派生。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import (
    CHARACTER_ROSTER,
    CHARACTERS,
    Character,
    chars_by_cost,
    chars_by_faction,
    get_char,
)
from sr_od.application.currency_war.cw_factions import FACTIONS
from test import SrTestBase


class TestCurrencyWarChars(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_registry_complete_all_costs(self):
        """注册表覆盖全费用 1-5;每条费用非空。"""
        for cost in range(1, 6):
            self.assertGreater(len(chars_by_cost(cost)), 0, f"{cost}费应有角色")
        # 总数合理(V4.4 ~70+,开拓者按命途合并性别)
        self.assertGreater(len(CHARACTERS), 60)

    def test_roster_derived_from_registry(self):
        """CHARACTER_ROSTER 是从 CHARACTERS 派生的规范名集合(单一真相源)。"""
        self.assertEqual(CHARACTER_ROSTER, frozenset(CHARACTERS.keys()))

    def test_canonical_names_no_nicknames(self):
        """规范名集合禁粉丝缩写:Archer 在,红A 不在。"""
        self.assertIn("Archer", CHARACTER_ROSTER)
        self.assertNotIn("红A", CHARACTER_ROSTER)
        self.assertIn("瓦尔特", CHARACTER_ROSTER)
        self.assertNotIn("杨叔", CHARACTER_ROSTER)

    def test_get_char_fields(self):
        """get_char 取 Character 字段:Archer 5费/前台/命运圣杯/战技点/独立魔术师。"""
        archer = get_char("Archer")
        self.assertIsNotNone(archer)
        self.assertEqual(archer.cost, 5)
        self.assertEqual(archer.position, "front")
        self.assertIn("命运圣杯", archer.factions)
        self.assertIn("战技点", archer.flows)
        self.assertEqual(archer.independent, "魔术师")
        self.assertIsNone(get_char("不存在角色"), "未知名 → None")

    def test_position_pref(self):
        """Character.position_pref:前台→front、后台→back、前后台(flex)→back。"""
        self.assertEqual(get_char("流萤").position_pref(), "front")      # 前台
        self.assertEqual(get_char("三月七").position_pref(), "back")     # 后台
        self.assertEqual(get_char("远坂凛").position_pref(), "back")     # 前后台→back 默认

    def test_chars_by_faction(self):
        """chars_by_faction:仙舟含青雀;含流派(燃血含刃)。"""
        仙舟 = [c.name for c in chars_by_faction("仙舟")]
        self.assertIn("青雀", 仙舟)
        燃血 = [c.name for c in chars_by_faction("燃血")]
        self.assertIn("刃", 燃血)
        self.assertIn("万敌", 燃血)

    def test_chars_by_cost_count(self):
        """3费=13(与 D牌期望表 77124902 实测点 v=13 吻合)。"""
        self.assertEqual(len(chars_by_cost(3)), 13)

    def test_faction_members_cross_module(self):
        """FactionInfo.members() 跨模块从 CHARACTERS 反查(派生关系,非硬编码)。"""
        仙舟_info = FACTIONS["仙舟"]
        members = 仙舟_info.members()
        self.assertIn("青雀", members)
        self.assertGreater(len(members), 0)
        # 成员关系派生:改 CHARACTERS 自动传导(FactionInfo 不存 members 字段)
        self.assertFalse(hasattr(仙舟_info, "__dict__") and "members" in 仙舟_info.__dict__,
                         "members 是方法非存储字段(派生,单一真相源)")

    def test_character_is_frozen(self):
        """Character 是 frozen dataclass(注册表条目不可变,防误改)。"""
        import dataclasses
        c = get_char("青雀")
        self.assertIsInstance(c, Character)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            c.cost = 9   # frozen → FrozenInstanceError
