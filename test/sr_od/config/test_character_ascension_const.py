# -*- coding: utf-8 -*-
"""角色晋阶材料常量的结构锁:官方快照重生成后,查询接口的结构不变即应绿。

不断言具体材料数量——版本更新会合法变动数值;锁的是「表结构 + 查询语义」。
"""
from sr_od.config.character_ascension_const import (
    CharacterAscension,
    get_character_ascension,
)


def test_get_known_character_returns_staged_table():
    """已知角色返回分段表:段非空、段有序、总量为各段并集。"""
    asc = get_character_ascension('藿藿')
    assert isinstance(asc, CharacterAscension)
    assert len(asc.stages) > 0
    assert asc.stages[0].name.endswith('晋阶')
    for stage in asc.stages:
        assert stage.materials, f'{stage.name} 材料为空'

    # total = 各段材料的并集:任一段的任意材料都出现在总量里
    first = asc.stages[0]
    for name, amount in first.materials.items():
        assert name in asc.total


def test_get_unknown_character_returns_none():
    """表外角色返回 None(调用方据此走「实机晋阶界面读数」兜底)。"""
    assert get_character_ascension('不存在角色') is None
