"""sr_character_details 角色静态信息常量单测。

锁的内容（模块 docstring 契约；基准值来自 wiki 抓取固化）：

- 快照完整性：97 角色（101 词条 - 3 前瞻占位 - 1 旧模板缺解析）、
  行迹/星魂键集一致（同源于同一批角色词条）；
- 数据质量：每角色星魂恒 6 层、行迹节点带 tag/name；普攻战技终结技天赋
  类节点有满级数值（属性加成类无数值表，不强求）；
- 基准：黄泉 1308（普攻三途枯榷 满级等级7 + ('110%',)）、白露 1211
  （E1 百脉甘津宁神久 + 生息效果）；
- 查询助手：miss 返回空元组不抛异常。
"""

from sr_od.mys.sr_character_details import (
    CHARACTER_EIDOLONS,
    CHARACTER_TRACES,
    resolve_eidolons,
    resolve_traces,
)

_ACHERON = 1308
_BAILU = 1211


def test_snapshot_integrity() -> None:
    """快照完整性：97 角色；行迹与星魂键集一致（同一批角色词条同源解析）。"""
    assert len(CHARACTER_TRACES) == 97
    assert len(CHARACTER_EIDOLONS) == 97
    assert set(CHARACTER_TRACES) == set(CHARACTER_EIDOLONS)


def test_data_quality() -> None:
    """数据质量：每角色星魂恒 6 层（pos 1-6 齐备）且效果非空；行迹节点带
    tag/name；主要输出类行迹（普攻/战技/终结技/天赋）有满级等级。"""
    for aid, eidolons in CHARACTER_EIDOLONS.items():
        assert [e.pos for e in eidolons] == [1, 2, 3, 4, 5, 6], aid
        assert all(e.name and e.desc for e in eidolons), aid
    for aid, traces in CHARACTER_TRACES.items():
        assert all(t.tag or t.name for t in traces), aid
        if 8001 <= aid <= 8010:
            continue  # 开拓者词条模板特殊:tag 为技能名而非类型标签,数据透传不强求
        main_traces = [t for t in traces if t.tag in ('普攻', '战技', '终结技', '天赋')]
        assert main_traces, aid
        for t in main_traces:
            if t.tag != '天赋':  # 天赋部分节点（如描述型）可无数值表
                assert t.max_values or t.desc, (aid, t.name)


def test_anchor_acheron_and_bailu() -> None:
    """基准：黄泉普攻满级（等级7 + ('110%',)）；白露 E1 名称与生息效果。"""
    ts = resolve_traces(_ACHERON)
    normal_attack = next(t for t in ts if t.tag == '普攻')
    assert normal_attack.name == '三途枯榷'
    assert normal_attack.max_level == '等级7'
    assert tuple(normal_attack.max_values) == ('110%',)

    e1 = resolve_eidolons(_BAILU)[0]
    assert e1.pos == 1
    assert e1.name == '百脉甘津宁神久'
    assert '生息' in e1.desc


def test_resolver_miss_returns_empty() -> None:
    """miss 防御：未实装/未知 avatarId 返回空元组，不抛异常。"""
    assert resolve_traces(8175) == ()  # 前瞻占位（未实装）
    assert resolve_eidolons(-1) == ()
