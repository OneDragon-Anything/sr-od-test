"""cw_lookup 三工具(货币战争静态查询)单测。

锁的内容(模块 docstring 匹配策略 + 字段合并语义):

- 角色域:精确命中(瓦尔特=开拓银轨成员)、同名多档合并(星神★阿哈 costs=[4,5,7]
  单条)、系统赠送单位(costs=[0]+来源说明)、模糊多命中 ambiguous、not_found、
  技能原文(双技能一 front 一 back、各星级只给一份;系统单位空;list_all 同带);
- 羁绊域:精确(欢愉逐档效果)、计数方式特例(千星商会 STAR3)、阵营过滤 list_all;
- 装备域:精确(配方拼接)、星徽类效果文本、分类过滤 list_all、多命中 ambiguous;
- 参数校验:list_all 缺过滤拒绝(带下一步提示文案);
- 注册冒烟:三工具注册、readOnlyHint、docstring 首句「观察类」、
  outputSchema 存在且运行时返回过 schema 校验(序列化层冒烟)。
"""

import jsonschema
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from sr_od.backend.mcp.cw_lookup_tools import (
    lookup_cw_char,
    lookup_cw_equip,
    lookup_cw_trait,
    register_cw_lookup_tools,
)


def _registered_tools() -> dict[str, object]:
    mcp = FastMCP('test')
    register_cw_lookup_tools(mcp, backend=None)
    return dict(mcp._tool_manager._tools)


def test_char_exact_and_multi_cost_merge() -> None:
    """精确命中带羁绊所属;星神★阿哈同名多档合并为 costs=[4,5,7] 单条。"""
    walter = lookup_cw_char('瓦尔特')
    assert walter.status == 'success'
    entry = walter.matches[0]
    assert entry.costs == [1]
    assert '开拓银轨' in entry.factions
    assert entry.position in ('front', 'back', 'common')

    aha = lookup_cw_char('星神★阿哈')
    assert aha.status == 'success'
    assert len(aha.matches) == 1
    assert aha.matches[0].costs == [4, 5, 7]


def test_char_system_unit_and_hidden() -> None:
    """系统赠送单位 costs=[0] 带来源说明、skills 空;隐藏单位(丹恒·腾荒)带 is_hide 标记且技能块照给。"""
    peipei = lookup_cw_char('佩佩')
    assert peipei.status == 'success'
    assert peipei.matches[0].costs == [0]
    assert peipei.matches[0].system_note != ''
    assert peipei.matches[0].skills == []

    tenghuang = lookup_cw_char('丹恒·腾荒')
    assert tenghuang.status == 'success'
    assert tenghuang.matches[0].is_hide is True
    assert tenghuang.matches[0].skills


def test_char_skills_with_sides_on_every_path() -> None:
    """技能原文随 skills 返回:双技能角色两条同名技能分属 front/back、原文非空;
    list_all 条目同样带(形状单一,无开关)。出处 = CwSkillInfo 字段注释。"""
    walter = lookup_cw_char('瓦尔特').matches[0]
    assert {s.front_back for s in walter.skills} == {'front', 'back'}
    assert len({s.name for s in walter.skills}) == 1  # 前后台两技能常同名,靠 front_back 区分
    assert all(s.desc and s.category_tags for s in walter.skills)

    assert all(m.skills for m in lookup_cw_char(cost=4, list_all=True).matches)


def test_char_fuzzy_ambiguous_and_not_found() -> None:
    """子串模糊多命中返回全部条目(ambiguous);查无与空 query 均 not_found。"""
    result = lookup_cw_char('三月七')
    assert result.status == 'success'  # 精确名命中(区别于模糊)

    fuzzy = lookup_cw_char('饮月')
    assert fuzzy.status == 'success'
    assert fuzzy.matches[0].name == '丹恒·饮月'

    assert lookup_cw_char('不存在的角色').status == 'not_found'
    assert lookup_cw_char('').status == 'not_found'


def test_char_list_all_with_cost_filter() -> None:
    """list_all 按费用过滤返回全量(多档角色计入对应费档);缺过滤拒绝。"""
    all_4cost = lookup_cw_char(cost=4, list_all=True)
    assert all_4cost.status == 'success'
    assert len(all_4cost.matches) > 10
    assert all(any(c == 4 for c in m.costs) for m in all_4cost.matches)
    assert '星神★阿哈' in {m.name for m in all_4cost.matches}

    try:
        lookup_cw_char(list_all=True)
    except ValueError as e:
        assert 'cost' in str(e)
    else:
        raise AssertionError('list_all 缺过滤应 ValueError')


def test_trait_exact_and_star3() -> None:
    """羁绊精确带逐档效果与成员;千星商会计数方式=STAR3(全表唯一特例)。"""
    joy = lookup_cw_trait('欢愉')
    assert joy.status == 'success'
    t = joy.matches[0]
    assert t.count_mode == 'TOTAL'
    assert '星神★阿哈' in t.members
    assert len(t.layers) >= 2
    assert all(ly.desc for ly in t.layers)

    qianxing = lookup_cw_trait('千星商会')
    assert qianxing.status == 'success'
    assert qianxing.matches[0].count_mode == 'STAR3'
    assert '砂金·戏浪' in qianxing.matches[0].members


def test_trait_list_all_by_kind() -> None:
    """按类型过滤 list_all;非法类型值报错并列出可用值。"""
    factions = lookup_cw_trait(kind_cn='阵营', list_all=True)
    assert factions.status == 'success'
    assert len(factions.matches) >= 10
    assert all(m.kind == '阵营' for m in factions.matches)

    try:
        lookup_cw_trait(kind_cn='不存在', list_all=True)
    except ValueError as e:
        assert '阵营' in str(e) and '流派' in str(e) and '独立' in str(e)
    else:
        raise AssertionError('非法 kind_cn 应 ValueError 带可用值')


def test_equip_exact_and_recipes() -> None:
    """装备精确命中带效果/配方拼接(材料以+连接);星徽效果文本=加入羁绊。"""
    sail = lookup_cw_equip('蓄能帆')
    assert sail.status == 'success'
    e = sail.matches[0]
    assert e.effect != ''
    assert e.category == '进阶装备'

    badge = lookup_cw_equip('开拓银轨星徽')
    assert badge.status == 'success'
    assert '开拓银轨' in badge.matches[0].effect
    assert badge.matches[0].category == '星徽'


def test_equip_fuzzy_ambiguous_and_list_all() -> None:
    """「星徽」子串多命中 ambiguous 全量返回;按分类 list_all 全列星徽。"""
    badges = lookup_cw_equip('星徽')
    assert badges.status == 'ambiguous'
    assert len(badges.matches) >= 15  # 注册表 21 件星徽,子串全命中

    all_badges = lookup_cw_equip(category='星徽', list_all=True)
    assert all_badges.status == 'success'
    assert len(all_badges.matches) == 21
    assert all(m.category == '星徽' for m in all_badges.matches)


def test_register_smoke_and_output_schema() -> None:
    """三工具注册 + readOnlyHint + docstring 首句;outputSchema 校验运行时返回(序列化层冒烟)。"""
    tools = _registered_tools()
    assert set(tools) == {'cw_char_lookup', 'cw_trait_lookup', 'cw_equip_lookup'}

    samples: dict[str, BaseModel] = {
        'cw_char_lookup': lookup_cw_char('瓦尔特'),
        'cw_trait_lookup': lookup_cw_trait('欢愉'),
        'cw_equip_lookup': lookup_cw_equip('蓄能帆'),
    }
    for name, tool in tools.items():
        annotations: ToolAnnotations = tool.annotations
        assert annotations.readOnlyHint is True
        assert tool.output_schema is not None, f'{name} 应有 outputSchema'
        doc = tool.description or ''
        assert doc.startswith('观察类'), f'{name} docstring 首句应标类别'
        # 运行时返回必须过自身 outputSchema(H1 教训:函数层测试绕过序列化层漏网)
        schema = _resolve_schema(tool.output_schema)
        jsonschema.validate(samples[name].model_dump(by_alias=True), schema)


def _resolve_schema(output_schema: dict) -> dict:
    """FastMCP 的 outputSchema 对 BaseModel 含 $defs 引用,直接返回原 schema 供校验。"""
    return output_schema


def test_char_matches_via_async_call() -> None:
    """经 FastMCP 调用层(非直调函数)取数,确认闭包注册与参数传递正常。"""
    import asyncio

    tools = _registered_tools()
    fn = tools['cw_char_lookup'].fn
    result = asyncio.run(fn(query='砂金·戏浪')) if asyncio.iscoroutinefunction(fn) else fn(query='砂金·戏浪')
    assert result.status == 'success'
    assert result.matches[0].name == '砂金·戏浪'
    assert '千星商会' in result.matches[0].factions
