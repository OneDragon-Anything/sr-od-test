"""cone_lookup 光锥查询工具单测。

锁的内容（cone_tools 模块 docstring 匹配策略）：

- tid 数字命中（23000 → 银河铁道之夜）；未知 tid → not_found；
- 名称精确命中（match=name_exact）；
- 模糊单命中（子串 → fuzzy）与多命中（ambiguous + candidates）；
- 过滤组合：rarity/path_id 缩域、list_all 全量列表、list_all 缺过滤拒绝；
- 注册冒烟：FastMCP 含 cone_lookup 只读工具、docstring 首句「观察类」、
  query 参数带 Field 描述（mcp-implementation §1/§2 规范）。
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from sr_od.backend.mcp.cone_tools import lookup_light_cone, register_cone_tools


def test_lookup_by_tid_and_name() -> None:
    """tid 命中（23000 → 银河铁道之夜，data 含结构化字段）；名称精确命中。"""
    by_tid = lookup_light_cone('23000')
    assert by_tid['status'] == 'success'
    assert by_tid['data']['name'] == '银河铁道之夜'
    assert by_tid['data']['rarity'] == 5
    assert by_tid['data']['path_cn'] == '智识'
    assert by_tid['data']['icon'] == 'assets/game_data/light_cone_icons/lightcone_23000.webp'
    assert by_tid['data']['match'] == 'tid'

    by_name = lookup_light_cone('银河铁道之夜')
    assert by_name['status'] == 'success'
    assert by_name['data']['match'] == 'name_exact'


def test_lookup_fuzzy_and_ambiguous() -> None:
    """模糊单命中（「于夜色」→ 于夜色中）；多命中返回 ambiguous 候选列表
    （不猜）；not_found 三形态（空串/无关词/未知 tid）。"""
    single = lookup_light_cone('于夜色')
    assert single['status'] == 'success'
    assert single['data']['name'] == '于夜色中'
    assert single['data']['match'] == 'fuzzy'

    ambiguous = lookup_light_cone('的')
    assert ambiguous['status'] == 'ambiguous'
    assert len(ambiguous['data']['candidates']) > 1

    assert lookup_light_cone('')['status'] == 'not_found'
    assert lookup_light_cone('不存在的光锥')['status'] == 'not_found'
    assert lookup_light_cone('999999')['status'] == 'not_found'


def test_lookup_filter_and_list_all() -> None:
    """过滤组合：rarity/path_id 缩域命中；list_all 全量列表（count 对齐过滤
    结果）；list_all 缺过滤条件拒绝。"""
    filtered = lookup_light_cone('银河铁道之夜', rarity=4)
    assert filtered['status'] == 'not_found'  # 名称命中但被星级过滤排除

    listed = lookup_light_cone('', rarity=3, list_all=True)
    assert listed['status'] == 'success'
    assert listed['data']['count'] == 25
    assert all(item['rarity'] == 3 for item in listed['data']['list'])

    by_path = lookup_light_cone('', path_id='remembrance', list_all=True)
    assert by_path['status'] == 'success'
    assert all(item['path_cn'] == '记忆' for item in by_path['data']['list'])

    assert lookup_light_cone('', list_all=True)['status'] == 'not_found'


def test_register_cone_tools_smoke() -> None:
    """注册冒烟：FastMCP 含 cone_lookup 只读工具；docstring 首句「观察类」、
    query 参数带 Field 描述（mcp-implementation §1/§2 规范）。"""
    mcp = FastMCP('test')
    register_cone_tools(mcp, backend=None)
    tool_list = asyncio.run(mcp.list_tools())
    assert 'cone_lookup' in {t.name for t in tool_list}
    cone_tool = next(t for t in tool_list if t.name == 'cone_lookup')
    assert cone_tool.annotations.readOnlyHint is True
    assert cone_tool.description.startswith('观察类')
    query_schema = cone_tool.inputSchema['properties']['query']
    assert '查询词' in query_schema['description']
