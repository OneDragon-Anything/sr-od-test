"""TlApocalypticShadowChallengeOp 节点图守卫测试(不跑流程,锁流转约定)。

锁设计约定(见 src/sr_od/operations/tl_as_challenge.py 节点图):
- 主 op 为组合 op:编队选人(TlAsTeamFillOp)/ 终焉公理装配(TlAsAxiomEquipOp) /
  战斗推进(TlAsBattleOp)为可独立 run_operation 的子 op,主 op 节点组合它们;
- 入口多态:进入编队屏的三种返回(成功/BANNER_UP/BATTLE_ONGOING)各有一条
  唯一出边,分别流向 编队选人 / 战斗推进 / 战斗推进;
- 前往挑战的成功出边必须存在(到达简报/节点画面后由战斗推进接手);
- 同 (from, status) 的重复边会被框架后注册覆盖(实机故障:default 边被
  战斗循环的冗余边覆盖,入口成功直跳战斗循环,跳过清队/填队/装配)。

背景:实机跑 op 卡「编队屏上战斗进行中」空转,根因即节点图重复边,
本文件防回归。
"""

from __future__ import annotations

from one_dragon.base.operation.operation_edge import OperationEdge
from sr_od.operations.tl_as_challenge import TlApocalypticShadowChallengeOp
from test.conftest import SrTestContext

_TEAM = ['姬子•启行', '瓦尔特', '知更鸟', '丹恒•腾荒',
         '黄泉', '卡芙卡', '黑天鹅', '灵砂']


def _default_edges(edges: list[OperationEdge], from_cn: str) -> list[OperationEdge]:
    """某节点的全部成功态无 status 出边(default 流转边)。"""
    return [e for e in edges
            if e.node_from.cn == from_cn and e.success and e.status is None]


def _status_edge(edges: list[OperationEdge], from_cn: str, status: str) -> OperationEdge | None:
    """某节点指定 status 的出边(唯一性由调用方断言)。"""
    hits = [e for e in edges
            if e.node_from.cn == from_cn and e.success and e.status == status]
    return hits[0] if hits else None


def test_node_graph_default_edges_unique(test_context: SrTestContext) -> None:
    """default 出边每节点至多一条:重复边会被后注册覆盖(实机故障形态)。"""
    op = TlApocalypticShadowChallengeOp(test_context, _TEAM)
    _, _, edges = op._analyse_node_annotations()
    for from_cn in ('进入编队屏', '编队选人', '终焉公理装配', '前往挑战'):
        d_edges = _default_edges(edges, from_cn)
        assert len(d_edges) <= 1, (
            f'节点「{from_cn}」存在 {len(d_edges)} 条 default 出边,'
            f'后注册者会静默覆盖前者(实机故障形态):'
            f'{[e.node_to.cn for e in d_edges]}')


def test_node_graph_entry_dispatch(test_context: SrTestContext) -> None:
    """入口三态分流:成功→编队选人,BANNER_UP→战斗推进,BATTLE_ONGOING→战斗推进。"""
    op = TlApocalypticShadowChallengeOp(test_context, _TEAM)
    _, _, edges = op._analyse_node_annotations()

    d_edges = _default_edges(edges, '进入编队屏')
    assert len(d_edges) == 1 and d_edges[0].node_to.cn == '编队选人', (
        f'入口成功应唯一流向编队选人:{[e.node_to.cn for e in d_edges]}')

    banner = _status_edge(edges, '进入编队屏', 'BANNER_UP')
    assert banner is not None and banner.node_to.cn == '战斗推进', (
        f'BANNER_UP 应流向战斗推进:{banner and banner.node_to.cn}')

    ongoing = _status_edge(edges, '进入编队屏', 'BATTLE_ONGOING')
    assert ongoing is not None and ongoing.node_to.cn == '战斗推进', (
        f'BATTLE_ONGOING 应流向战斗推进:{ongoing and ongoing.node_to.cn}')


def test_node_graph_start_to_battle(test_context: SrTestContext) -> None:
    """前往挑战成功后必须接战斗推进(缺边 = _start 成功即 op 终止)。"""
    op = TlApocalypticShadowChallengeOp(test_context, _TEAM)
    _, _, edges = op._analyse_node_annotations()
    chain = [('编队选人', '终焉公理装配'), ('终焉公理装配', '前往挑战'),
             ('前往挑战', '战斗推进')]
    for from_cn, to_cn in chain:
        d_edges = _default_edges(edges, from_cn)
        assert len(d_edges) == 1 and d_edges[0].node_to.cn == to_cn, (
            f'{from_cn} 应唯一流向 {to_cn}:{[e.node_to.cn for e in d_edges]}')


def test_sub_ops_independent_start(test_context: SrTestContext) -> None:
    """三个子 op 可独立构造(start 节点在位):选人/装配/战斗推进。"""
    from sr_od.operations.tl_as_challenge import (
        TlAsAxiomEquipOp,
        TlAsBattleOp,
        TlAsTeamFillOp,
    )
    fill = TlAsTeamFillOp(test_context, _TEAM)
    equip = TlAsAxiomEquipOp(test_context, (1, 1))
    battle = TlAsBattleOp(test_context)
    for op in (fill, equip, battle):
        assert op._analyse_node_annotations()[0] is not None, (
            f'{type(op).__name__} 缺 start 节点')
