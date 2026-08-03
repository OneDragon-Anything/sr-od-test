"""货币战争 装备领域模型(cw_equipment)测试 —— 纯逻辑,不依赖游戏。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_equipment import EQUIPMENTS, Equipment, get_equip
from test import SrTestBase


class TestCurrencyWarEquipment(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_key_equips_present(self):
        """策略相关 key 装备齐:反重力皮靴/以牙还牙甲/冷笑话引擎 等。"""
        for name in ("反重力皮靴", "以牙还牙甲", "冷笑话引擎", "火力风暴潮", "高周波电锯", "光速螺旋桨"):
            self.assertIn(name, EQUIPMENTS, f"key 装备 {name} 应在注册表")

    def test_stacking_flag(self):
        """stacking 标志:反重力皮靴/火力风暴潮/冷笑话引擎 可叠加;高周波电锯/以牙还牙甲 不可。"""
        self.assertTrue(get_equip("反重力皮靴").stacking, "反重力皮靴可叠加(鞋修×2)")
        self.assertTrue(get_equip("火力风暴潮").stacking)
        self.assertTrue(get_equip("冷笑话引擎").stacking)
        self.assertFalse(get_equip("高周波电锯").stacking)
        self.assertFalse(get_equip("以牙还牙甲").stacking)

    def test_get_equip_fields(self):
        """get_equip 取 Equipment 字段;未知名→None。"""
        e = get_equip("追击星徽")
        self.assertIsInstance(e, Equipment)
        self.assertEqual(e.category, "星徽")
        self.assertIsNone(get_equip("不存在装备"))
