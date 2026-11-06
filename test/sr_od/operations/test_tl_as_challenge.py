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

import pytest
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation_edge import OperationEdge
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from sr_od.application.treasures_lightward.obs.tl_team_obs import (
    AnchorCell,
    MemberGuess,
)
from sr_od.operations.tl_as_challenge import TlApocalypticShadowChallengeOp
from sr_od.operations.tl_as_challenge import TlAsTeamFillOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import fast_sleep

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


# --------------------------------------------------------------------------
# 星启填人单卡判定(约定锁,机制出处 = tl_as_challenge 星启交互注释块):
# 列表卡点击是加/移开关——点已入队角色的卡会把人移出队伍,所以找卡绝不点击
# 带「队伍N」标记的卡;落位复验只认被点那张卡上的标记(与翻页无关)。
# --------------------------------------------------------------------------

_ARC_TEAM = ['海瑟音', '波提欧', '花火', '灵砂',
             '姬子•启行', '瓦尔特', '知更鸟', '丹恒•腾荒',
             '千冶•刃', '风堇', '长夜月', '椒丘']


def _mk_cell(x: int, y: int, guess: MemberGuess) -> AnchorCell:
    """测试格:头像区 90x95(真实验标几何),中心即点击中心。"""
    return AnchorCell(
        center=Point(x, y), guess=guess,
        rect=Rect(x - 45, y - 47, x + 45, y + 48))


def test_arc_fill_skips_badged_cell(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """批量点卡不点带标记的卡:列表卡点击是加/移开关,点已入队卡 = 拆队。"""
    op = TlAsTeamFillOp(test_context, _ARC_TEAM)
    op._need_top = False
    op._char_idx = 2  # 行 1 目标 = [花火, 灵砂]
    badged = _mk_cell(300, 300, MemberGuess('花火', True, [('花火', 0.9)]))
    unbadged = _mk_cell(600, 300, MemberGuess(None, False, [('花火', 0.8)]))
    clicks: list[Point] = []
    paged: list[str] = []
    monkeypatch.setattr(op, '_team_tag_boxes', lambda image: [badged.rect.center])
    monkeypatch.setattr(op.ctx.controller, 'click',
                        lambda point, press_time=0.1: clicks.append(point))
    monkeypatch.setattr(op, '_page_down',
                        lambda cells, target, row_no: paged.append(target))
    with fast_sleep(op):
        result = op._arc_fill_round(None, [badged, unbadged], 1)
    assert result.result == OperationRoundResultEnum.WAIT
    assert clicks == [unbadged.center], f'点了带标记的卡:{clicks}'
    assert op._char_idx == 3, '点完花火应推进到灵砂'


def test_arc_fill_only_badged_skips_cursor(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """队首目标只剩带标记命中 = 已入队(重复生效的点击),跳过游标不点。"""
    op = TlAsTeamFillOp(test_context, _ARC_TEAM)
    op._need_top = False
    op._char_idx = 2
    badged = _mk_cell(300, 300, MemberGuess('花火', True, [('花火', 0.9)]))
    clicks: list[Point] = []
    paged: list[str] = []
    monkeypatch.setattr(op, '_team_tag_boxes', lambda image: [badged.rect.center])
    monkeypatch.setattr(op.ctx.controller, 'click',
                        lambda point, press_time=0.1: clicks.append(point))
    monkeypatch.setattr(op, '_page_down',
                        lambda cells, target, row_no: paged.append(target))
    with fast_sleep(op):
        op._arc_fill_round(None, [badged], 1)
    assert clicks == [], '点了带标记的卡(拆队行为)'
    assert op._char_idx == 3, '队首已带标记应跳过游标'
    assert paged == ['灵砂'], '跳过后应继续找下一目标'


def test_arc_batch_clicks_in_row_order(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """整页批量点卡必须按队伍顺序(列表卡点击落进选中行首个空槽,
    跳名点击会错槽):页面出现顺序与队伍顺序无关。"""
    op = TlAsTeamFillOp(test_context, _ARC_TEAM)
    op._need_top = False
    # 页面位置:波提欧在上、海瑟音在下(与队伍顺序相反)
    bo = _mk_cell(300, 200, MemberGuess('波提欧', True, [('波提欧', 0.9)]))
    hai = _mk_cell(300, 400, MemberGuess('海瑟音', True, [('海瑟音', 0.9)]))
    clicks: list[Point] = []
    monkeypatch.setattr(op, '_team_tag_boxes', lambda image: [])
    monkeypatch.setattr(op.ctx.controller, 'click',
                        lambda point, press_time=0.1: clicks.append(point))
    with fast_sleep(op):
        result = op._arc_fill_round(None, [bo, hai], 1)
    assert result.result == OperationRoundResultEnum.WAIT
    assert clicks == [hai.center, bo.center], f'点击顺序错:{clicks}'
    assert op._char_idx == 2, '应推进两个目标'
    assert op._need_top, '点完应回顶继续'


def test_arc_prefix_break_missing_head(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """队首目标不在本页时,后面的目标再可见也不点(保槽位顺序),转翻页。"""
    op = TlAsTeamFillOp(test_context, _ARC_TEAM)
    op._need_top = False
    bo = _mk_cell(300, 200, MemberGuess('波提欧', True, [('波提欧', 0.9)]))
    clicks: list[Point] = []
    paged: list[str] = []
    monkeypatch.setattr(op, '_team_tag_boxes', lambda image: [])
    monkeypatch.setattr(op.ctx.controller, 'click',
                        lambda point, press_time=0.1: clicks.append(point))
    monkeypatch.setattr(op, '_page_down',
                        lambda cells, target, row_no: paged.append(target))
    with fast_sleep(op):
        op._arc_fill_round(None, [bo], 1)
    assert clicks == [], '队首缺席时不得点后续目标'
    assert paged == ['海瑟音'], '应翻页找队首'


def test_arc_return_to_top_fixed_drags(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """回顶 = 固定几次大幅快速上拖 + 停 1 秒,不验证到位(2026-11-06 定案)。"""
    op = TlAsTeamFillOp(test_context, _ARC_TEAM)
    op._need_top = True
    drags: list[tuple[Point, Point]] = []
    monkeypatch.setattr(op.ctx.controller, 'drag_to',
                        lambda end, start, duration=0.2: drags.append((start, end)))
    with fast_sleep(op):
        result = op._return_to_top()
    assert result.result == OperationRoundResultEnum.WAIT
    assert len(drags) >= 3, f'回顶拖动次数不足:{len(drags)}'
    assert all(s.y < e.y for s, e in drags), (
        '回顶拖动方向错:手指应自上而下(上滑=向后翻页,反写会冲向列表尾)')
    assert op._need_top is False, '回顶后应清除回顶标记'
