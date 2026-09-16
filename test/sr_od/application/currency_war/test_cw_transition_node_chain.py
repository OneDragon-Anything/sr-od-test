"""过渡屏链观察锁(链观察落地批 landing.md §3.3;语义正本 =
game_state/chain-observation.md §3:基线链 transition_row + 离场快照
transition_snapshot)。

写端 = cw_screen_plane_transition._write_transition_node_chain(模块级
纯函数,session/slots 参数注入,零读屏零真实 IO)。开局判别(镜像与 hist
双缺)/行归属位面/boss SIFT 禁回落/基线只写一次,逐项单测。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    NodeKey,
    TokenCell,
    game_state_of,
    register_sig_actors,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot
from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_transition import (
    _write_transition_node_chain,
)

register_sig_actors('TestChainWriter')
_SIG = ChannelSig(family='obs', actor='TestChainWriter', mode='read')


def _slot(idx: int, state: str = 'upcoming',
          node_type: str | None = None, hu_dist: float | None = 0.9,
          boss: str | None = None) -> NodeSlot:
    return NodeSlot(idx=idx, cx=0, cy=0, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _p1_slots(boss_hit: bool = True) -> list[NodeSlot]:
    """P1 过渡屏全亮行(九槽):8 类型槽 + boss 末槽。"""
    return [
        _slot(0, 'upcoming', 'reward'), _slot(1, 'upcoming', 'supply'),
        _slot(2, 'upcoming', 'battle'), _slot(3, 'upcoming', 'battle'),
        _slot(4, 'upcoming', 'supply'), _slot(5, 'upcoming', 'battle'),
        _slot(6, 'upcoming', 'encounter'), _slot(7, 'upcoming', 'supply'),
        _slot(8, 'upcoming', boss=('巳蛇' if boss_hit else None)),
    ]


def test_transition_opening_writes_baseline_and_snapshot():
    """开局过渡屏(镜像与 hist 双缺)→ 基线 transition_row + 现行链离场
    快照,行位面 = 1。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    assert gs.node.value is None and gs.node_hist_ord is None
    _write_transition_node_chain(session, _p1_slots())
    baseline = gs.node_path_baseline.value
    snapshot = gs.node_path.value
    assert baseline is not None and baseline.plane == 1, '开局写 P1 入口基线'
    assert snapshot is not None and snapshot.plane == 1, '离场快照同行同位面'
    assert baseline.seq[0].token == 'reward' and baseline.seq[0].channel == 'hu'
    assert baseline.seq[8] == TokenCell('boss', 'sift', 0.9), 'boss 末槽 SIFT'
    assert snapshot.seq == baseline.seq, '开局屏两笔同链'


def test_transition_non_opening_writes_snapshot_only():
    """非开局(镜像 P2 在位):只写离场快照(行位面 = 镜像 plane),基线
    不动。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=2, round_num=1, kind='prep'),
               evidence='t', sig=_SIG)
    _write_transition_node_chain(session, _p1_slots())
    assert gs.node_path.value is not None \
        and gs.node_path.value.plane == 2, '离场快照 = 镜像位面(刚离开)'
    assert gs.node_path_baseline.value is None, \
        'P2/P3 基线不来自过渡屏(首帧回填承接,链正本 §3)'


def test_transition_mirror_missing_non_opening_skips():
    """非开局且镜像缺(hist 在):行归属不可知 → 跳写(禁猜)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.node_hist_ord = 10   # 非开局信号在,镜像缺
    _write_transition_node_chain(session, _p1_slots())
    assert gs.node_path.value is None, '镜像缺跳写(诚实缺位)'
    assert gs.node_path_baseline.value is None


def test_transition_boss_sift_miss_and_none_cells():
    """boss SIFT miss → none 禁回落 Hu;无类型格 → none。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    slots = _p1_slots(boss_hit=False)
    slots[2] = _slot(2, 'upcoming', 'encounter', 3.5)   # 超阈未辨
    _write_transition_node_chain(session, slots)
    chain = gs.node_path.value
    assert chain.seq[8] == TokenCell(None, 'none'), 'SIFT miss 禁回落 Hu'
    assert chain.seq[2] == TokenCell(None, 'none'), '超阈未辨诚实缺位'


def test_transition_no_slots_or_no_session_noop():
    """slots 空 / session 缺 → 零写不炸。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    _write_transition_node_chain(session, None)
    _write_transition_node_chain(None, _p1_slots())
    assert gs.node_path.value is None and gs.node_path_baseline.value is None
    assert GAME_STATE_SCHEMA_VERSION >= 1
