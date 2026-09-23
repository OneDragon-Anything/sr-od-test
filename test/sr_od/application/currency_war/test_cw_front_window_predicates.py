"""前窗两谓词数据源锁(P90 面①;T-3 验收裁缺陷修:前窗/表就绪谓词
数据源归位 ``gs.node_books`` 单一源)。

病灶形态(本锁防复发):两谓词曾经裸 ``getattr(session, 'plane_node_table
/plane_node_table_plane')`` 读已退役 session 探针族(StrategySession 现值
仅 rng/performance/strategy_state)→ 恒 None → 谓词恒 False → 生产消费面
(shop.decide_shop_action 的零成型武装)fail-closed 静默失效。写端唯一 =
cw_screen_prep.store_plane_table(写 ``gs.node_books``),读端必须同源。

锁面(此前零覆盖):
1. 表在场真路径:node_books 在册(位面锚=1)→ 表就绪 True / 前窗帧
   轮窗(轮 1..首战槽+1)True,出窗 False;
2. fail-closed 负路径:表缺(裸容器)/ 锚不符(旧表滞留 P2)/ state
   位面非 1 / 脏表(全零战斗词)→ False(前窗行为不发生);
3. 写入点形状契约:store_plane_table 写入的形状(list[str] 槽序 + 位面
   锚落 ``gs.node_books``)= 谓词读的形状——写读异源即病灶本身,本锁
   单一源对账。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    store_plane_table,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

_SIG = ChannelSig(family='obs', actor='TestCwFrontWindowPredicates', mode='read')

#: P1 众数表形样例:首战在第 3 槽(0 基 idx=2)→ 前窗轮窗 = 1..3。
_P1_TABLE: list[str] = ['奖励', '补给', '战斗', '战斗', '战斗',
                        '战斗', '战斗', '战斗', '首领']


def _gs(plane: int = 1, round_num: int = 1) -> GameState:
    """容器 + 节点读口种子(位面/轮次即谓词的 plane/round 读口输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind='prep'),
               evidence='t', sig=_SIG)
    return gs


def _seed_table(gs: GameState, plane: int = 1,
                table: list[str] | None = None) -> None:
    """直写 node_books(谓词读端形状;表缺负路径不调用)。"""
    gs.node_books.plane_node_table = list(table or _P1_TABLE)
    gs.node_books.plane_node_table_plane = plane


def test_table_ready_true_and_front_window_round_window():
    """表在场真路径:node_books 在册(位面锚=1)→ 表就绪 True;前窗帧
    = 轮 1..首战槽+1(样例表首战第 3 槽 → 轮 1/2/3 True,轮 4 出窗)。"""
    gs = _gs(plane=1, round_num=1)
    _seed_table(gs)
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is True
    for r in (2, 3):
        gs_r = _gs(plane=1, round_num=r)
        _seed_table(gs_r)
        assert predicates.front_window_frame(gs_r) is True, f'轮 {r} 在前窗'
    gs_out = _gs(plane=1, round_num=4)
    _seed_table(gs_out)
    assert predicates.front_window_frame(gs_out) is False, '首战槽后帧出窗'


def test_fail_closed_when_table_or_anchor_or_plane_gate_fails():
    """fail-closed 负路径:表缺(裸容器)/ 锚不符(旧表滞留 P2)/
    state 位面非 1 → 两谓词 False(前窗行为不发生,不静默武装)。"""
    gs_bare = _gs()   # 未写表:plane_node_table / 位面锚均 None
    assert predicates.front_window_table_ready(gs_bare) is False
    assert predicates.front_window_frame(gs_bare) is False

    gs_stale = _gs()
    _seed_table(gs_stale, plane=2)   # 表在场但位面锚 = 2(旧表滞留形态)
    assert predicates.front_window_table_ready(gs_stale) is False
    assert predicates.front_window_frame(gs_stale) is False

    gs_p2 = _gs(plane=2, round_num=1)   # P2 帧挂 P1 表:位面门先拒
    _seed_table(gs_p2, plane=1)
    assert predicates.front_window_frame(gs_p2) is False


def test_dirty_table_frame_silent_false():
    """脏表退化域:表全为零战斗词(位面必有战斗的结构下不可能)→
    frame 静默 False(表就绪探针只辖「在场」,不受脏表辖)。"""
    gs = _gs()
    _seed_table(gs, table=['奖励', '补给'] * 4 + ['奖励'])
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is False


def test_store_plane_table_shape_feeds_predicates():
    """写入点形状契约:store_plane_table 写入(经 session 桥落
    ``gs.node_books``,与生产唯一写端同路)= 谓词读的形状 → 两谓词
    True。写读异源(session 探针读法)即本缺陷病灶,本锁单一源对账。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=2, kind='prep'),
               evidence='t', sig=_SIG)
    assert store_plane_table(session, _P1_TABLE, 1) is True
    assert gs.node_books.plane_node_table == _P1_TABLE, '槽序表按写端形状落位'
    assert gs.node_books.plane_node_table_plane == 1, '位面锚落位'
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is True, '写端形状 → 谓词 True'
