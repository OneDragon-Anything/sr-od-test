"""relic_lookup 遗器查询工具单测。

锁的内容（relic_tools 模块 docstring 匹配策略 + mys-relic-sets 常量锚点）：

- tid 数字命中：61013 → 云无留迹的过客（含 kind_cn/set_id/effects/pieces
  与图标路径公式）；未知 tid → not_found 不抛异常；
- 件名精确：翁瓦克的诞生之岛 → 生命的翁瓦克（matched_piece 回带）；
- 套装名精确：官方全名命中，match=set_exact；
- 模糊单命中：子串「翁瓦克」→ 生命的翁瓦克（match=fuzzy）；
- 模糊多命中：status=ambiguous + candidates 候选列表（不猜）；
- not_found：空串 / 无关词；
- 注册冒烟：register_relic_tools 后 FastMCP 含 relic_lookup 只读工具。
"""

from mcp.server.fastmcp import FastMCP

from sr_od.backend.mcp.relic_tools import lookup_relic, register_relic_tools


def test_lookup_by_tid() -> None:
    """tid 数字命中：信使锚点件 id → 骇域漫游的信使；data 含结构化全量。"""
    result = lookup_relic('61141')
    assert result['status'] == 'success'
    data = result['data']
    assert data['set_name'] == '骇域漫游的信使'
    assert data['set_id'] == 114
    assert data['kind_cn'] == '隧洞遗器'
    assert data['effects']['2'] == '速度提高6%。'
    assert [p['name'] for p in data['pieces']] == [
        '信使的全息目镜', '信使的百变义手', '信使的密信挎包', '信使的酷跑板鞋',
    ]
    assert data['pieces'][0]['icon'] == 'assets/game_data/relic_icons/iconrelic_114_1.webp'
    assert data['match'] == 'tid'


def test_lookup_by_piece_and_set_name() -> None:
    """件名精确（matched_piece 回带）与套装名精确两种命中形态。"""
    by_piece = lookup_relic('翁瓦克的诞生之岛')
    assert by_piece['status'] == 'success'
    assert by_piece['data']['set_name'] == '生命的翁瓦克'
    assert by_piece['data']['matched_piece'] == '翁瓦克的诞生之岛'
    assert by_piece['data']['pieces'][0]['pos_cn'] == '位面球'

    by_set = lookup_relic('生命的翁瓦克')
    assert by_set['status'] == 'success'
    assert by_set['data']['set_id'] == 308
    assert by_set['data']['match'] == 'set_exact'


def test_lookup_fuzzy_single_and_ambiguous() -> None:
    """模糊单命中：子串「翁瓦克」唯一命中；模糊多命中：返回 ambiguous +
    candidates 候选列表（多于一个候选），不静默猜测。"""
    single = lookup_relic('翁瓦克')
    assert single['status'] == 'success'
    assert single['data']['set_name'] == '生命的翁瓦克'
    assert single['data']['match'] == 'fuzzy'

    ambiguous = lookup_relic('星')
    assert ambiguous['status'] == 'ambiguous'
    assert len(ambiguous['data']['candidates']) > 1


def test_lookup_not_found() -> None:
    """not_found 三形态：空串、无关词、未知 tid——均为 not_found 不抛异常。"""
    assert lookup_relic('')['status'] == 'not_found'
    assert lookup_relic('不存在的遗器名')['status'] == 'not_found'
    assert lookup_relic('99999')['status'] == 'not_found'


def test_register_relic_tools_smoke() -> None:
    """注册冒烟：装配后 FastMCP 工具列表含 relic_lookup 且标记只读；
    docstring 首句带「观察类」标注、query 参数带 Field 描述（mcp-implementation
    §1 双标原则 + §2 参数描述规范）。"""
    import asyncio

    mcp = FastMCP('test')
    register_relic_tools(mcp, backend=None)
    tool_list = asyncio.run(mcp.list_tools())
    assert 'relic_lookup' in {t.name for t in tool_list}
    relic_tool = next(t for t in tool_list if t.name == 'relic_lookup')
    assert relic_tool.annotations.readOnlyHint is True
    assert '遗器' in relic_tool.description
    assert relic_tool.description.startswith('观察类')
    query_schema = relic_tool.inputSchema['properties']['query']
    assert '查询词' in query_schema['description']
    assert 'query' in relic_tool.inputSchema.get('required', [])
