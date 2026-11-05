"""character_lookup 角色静态信息查询工具单测。

锁的内容（character_tools 模块 docstring 匹配策略）：

- 数字 id 命中（1217 → 藿藿，带 traces/eidolons 详情）；
- 中文名精确（黄泉 → acheron）；模糊单命中；多命中 ambiguous；
- 过滤组合与 list_all 全量（count 对齐）；list_all 缺过滤拒绝；
- 与账号状态的边界：本工具不读 mys（零网络），查的是静态定义；
- 注册冒烟：FastMCP 含 character_lookup 只读工具、首句「观察类」、
  query 参数带 Field 描述。
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from sr_od.backend.mcp.character_tools import lookup_character, register_character_tools


def test_lookup_by_avatar_id_and_name() -> None:
    """数字 id 命中带详情（1217 藿藿：丰饶 + traces/eidolons）；中文名精确。"""
    by_id = lookup_character('1217')
    assert by_id['status'] == 'success'
    assert by_id['data']['cn'] == '藿藿'
    assert by_id['data']['path_cn'] == '丰饶'
    assert len(by_id['data']['traces']) > 0
    assert len(by_id['data']['eidolons']) == 6
    assert by_id['data']['match'] == 'avatar_id'

    by_name = lookup_character('黄泉')
    assert by_name['status'] == 'success'
    assert by_name['data']['avatar_id'] == 1308
    assert by_name['data']['id'] == 'acheron'
    assert by_name['data']['eidolons'][0]['name'] == '高天寥落真言始'


def test_lookup_fuzzy_and_ambiguous() -> None:
    """模糊命中与多命中候选；not_found 形态（空串/未知数字/无关词）。"""
    single = lookup_character('开拓者·毁灭·男')
    assert single['status'] == 'success'

    ambiguous = lookup_character('三月七')
    assert ambiguous['status'] == 'success'  # 中文名精确命中存护三月七（非模糊）

    exact = lookup_character('黑塔')
    assert exact['status'] == 'success'  # 「黑塔」是合法精确中文名（区别于「大黑塔」）

    ambiguous = lookup_character('开拓者')
    assert ambiguous['status'] == 'ambiguous'  # 开拓者双性别×五命途拆分多条
    assert len(ambiguous['data']['candidates']) > 1

    assert lookup_character('')['status'] == 'not_found'
    assert lookup_character('不存在的角色')['status'] == 'not_found'
    assert lookup_character('99999')['status'] == 'not_found'


def test_lookup_filter_and_list_all() -> None:
    """list_all 全量：5 星记忆命途（6 角色）；缺过滤条件拒绝。"""
    listed = lookup_character('', rarity=5, path_cn='记忆', list_all=True)
    assert listed['status'] == 'success'
    assert listed['data']['count'] == 6
    assert all(item['rarity'] == 5 and item['path_cn'] == '记忆'
               for item in listed['data']['list'])
    assert 'traces' not in listed['data']['list'][0]  # 列表口径不带详情

    assert lookup_character('', list_all=True)['status'] == 'not_found'


def test_register_character_tools_smoke() -> None:
    """注册冒烟：FastMCP 含 character_lookup 只读工具；首句「观察类」；
    query 参数带 Field 描述（mcp-implementation §1/§2 规范）。"""
    mcp = FastMCP('test')
    register_character_tools(mcp, backend=None)
    tool_list = asyncio.run(mcp.list_tools())
    assert 'character_lookup' in {t.name for t in tool_list}
    char_tool = next(t for t in tool_list if t.name == 'character_lookup')
    assert char_tool.annotations.readOnlyHint is True
    assert char_tool.description.startswith('观察类')
    query_schema = char_tool.inputSchema['properties']['query']
    assert '查询词' in query_schema['description']
