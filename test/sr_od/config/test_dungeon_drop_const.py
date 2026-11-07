# -*- coding: utf-8 -*-
"""副本产出常量的结构锁:反查语义不变即应绿(不锁具体材料数值,版本更新不误红)。"""
from sr_od.config.dungeon_drop_const import find_dungeon_by_material


def test_find_known_material_returns_dungeon():
    """登记过的材料反查出非空副本列表,且列表元素都来自产出表键集。"""
    from sr_od.config.dungeon_drop_const import DUNGEON_MATERIAL_DROPS

    any_material = next(iter(DUNGEON_MATERIAL_DROPS))  # 表内任意键对应的首个材料
    some_material = next(iter(DUNGEON_MATERIAL_DROPS[any_material]))
    dungeons = find_dungeon_by_material(some_material)

    assert dungeons, '表内材料反查结果不应为空'
    assert all(d in DUNGEON_MATERIAL_DROPS for d in dungeons)


def test_find_unregistered_material_returns_empty():
    """表外材料返回空列表(调用方据此走非副本途径/实机读数兜底)。"""
    assert find_dungeon_by_material('不存在的材料') == []
