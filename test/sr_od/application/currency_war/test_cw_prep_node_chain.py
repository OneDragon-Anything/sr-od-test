"""备战帧现行链写端锁(链观察落地批 landing.md §3.2;语义正本 =
game_state/chain-observation.md §3)。

写端 = cw_screen_prep._write_prep_node_chain(模块级纯函数,session/slots/
sig 全参数注入,零读屏零真实 IO)。轮位对齐门/左移携带/boss SIFT 禁回落/
变异窗新语义(窗内照写+对齐读关窗)/基线回填,逐项单测。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import (
    get_node_ledger,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeChain,
    NodeKey,
    TokenCell,
    game_state_of,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    _write_prep_node_chain,
)

_SIG = ChannelSig(family='obs', actor='TestChainWriter', mode='read')


def _slot(idx: int, state: str, node_type: str | None = None,
          hu_dist: float | None = None, boss: str | None = None) -> NodeSlot:
    return NodeSlot(idx=idx, cx=0, cy=0, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _round3_slots(boss_hit: bool = True) -> list[NodeSlot]:
    """round 3 备战帧五槽:2 past + current(2) + upcoming battle + boss 末槽。"""
    return [
        _slot(0, 'past'),
        _slot(1, 'past'),
        _slot(2, 'current'),
        _slot(3, 'upcoming', 'battle', 0.8),
        _slot(4, 'upcoming', boss=('测试首领' if boss_hit else None)),
    ]


def _prev_chain() -> NodeChain:
    """round 2 帧写下的旧链:槽 2/3 为 upcoming Hu(supply/battle)。"""
    return NodeChain(plane=1, seq=[
        TokenCell(None, 'dim'),
        TokenCell(None, 'none'),
        TokenCell('supply', 'hu', 1.2),
        TokenCell('battle', 'hu', 0.8),
        TokenCell(None, 'none'),
    ])


def _setup():
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='prep'),
               evidence='t', sig=_SIG)
    ledger = get_node_ledger(session)
    ledger.env_grace_until = time.monotonic() + 45.0   # 预置开窗
    return session, gs, ledger


def test_prep_chain_whole_frame_write_with_carry_and_baseline():
    """对齐帧:整帧覆盖五格(past=dim/current=左移携带/upcoming=hu/boss=sift);
    基线回填 prep_row_first;对齐读关变异窗。"""
    session, gs, ledger = _setup()
    gs.observe(gs.node_path, _prev_chain(), evidence='t', sig=_SIG)
    _write_prep_node_chain(session, _round3_slots(), _SIG)
    chain = gs.node_path.value
    assert isinstance(chain, NodeChain) and chain.plane == 1
    assert [(c.token, c.channel) for c in chain.seq] == [
        (None, 'dim'), (None, 'dim'),
        ('supply', 'hu'),          # 左移携带:上帧 upcoming 本轮 current
        ('battle', 'hu'),
        ('boss', 'sift'),
    ], '逐格映射:past=dim/current=携带/upcoming=hu/boss=SIFT'
    assert chain.seq[2].hu_dist == 1.2, '携带格残差随值'
    baseline = gs.node_path_baseline.value
    assert baseline is not None and baseline.seq == chain.seq, \
        '首写回填基线(prep_row_first)'
    assert ledger.env_grace_until == 0.0, '对齐 clean 读关变异窗'


def test_prep_chain_misaligned_frame_rejected():
    """轮位对齐门:current 槽 idx != round-1(漏检左移错位帧)→ 拒写不关窗。"""
    session, gs, ledger = _setup()
    gs.observe(gs.node_path, _prev_chain(), evidence='t', sig=_SIG)
    bad = [_slot(0, 'past'), _slot(1, 'current'),   # current 在 idx1,round=3
           _slot(2, 'upcoming', 'battle', 0.8),
           _slot(3, 'upcoming'), _slot(4, 'upcoming')]
    _write_prep_node_chain(session, bad, _SIG)
    assert gs.node_path.value == _prev_chain(), '错位帧拒写'
    assert ledger.env_grace_until > time.monotonic(), '错位帧不关窗'


def test_prep_chain_first_frame_no_carry_baseline_filled():
    """首帧(无旧链):current 无携带 = none/None(fail-open 等价现役);
    基线仍回填。"""
    session, gs, ledger = _setup()
    _write_prep_node_chain(session, _round3_slots(boss_hit=False), _SIG)
    chain = gs.node_path.value
    assert chain.seq[2] == TokenCell(None, 'none'), '无携带首帧 current 诚实缺位'
    assert chain.seq[4] == TokenCell(None, 'none'), \
        'boss SIFT miss → none 禁回落 Hu(对抗 F14)'
    assert gs.node_path_baseline.value is not None, '首写回填基线'
    assert ledger.env_grace_until == 0.0


def test_prep_chain_plane_mismatch_no_carryover():
    """旧链跨位面(换位面未重写)→ 不跨面携带,current 诚实缺位。"""
    session, gs, ledger = _setup()
    gs.observe(gs.node_path, NodeChain(plane=2, seq=[
        TokenCell('supply', 'hu', 1.2), TokenCell(None, 'none'),
    ]), evidence='t', sig=_SIG)
    _write_prep_node_chain(session, _round3_slots(), _SIG)
    chain = gs.node_path.value
    assert chain.plane == 1 and chain.seq[2].token is None, \
        '跨位面旧链不携带(防陈旧链污染)'
    assert gs.node_path_baseline.value.seq == chain.seq


def test_prep_chain_unrecognized_upcoming_is_none():
    """upcoming Hu 超阈未辨 → none/None(不猜);窗内照写(链写不受窗门)。"""
    session, gs, ledger = _setup()
    slots = [
        _slot(0, 'past'), _slot(1, 'past'), _slot(2, 'current'),
        _slot(3, 'upcoming', 'encounter', 3.5),   # > 2.8 未识别
        _slot(4, 'upcoming', boss='测试首领'),
    ]
    _write_prep_node_chain(session, slots, _SIG)
    chain = gs.node_path.value
    assert chain.seq[3] == TokenCell(None, 'none'), '超阈未辨诚实缺位'
    assert ledger.env_grace_until == 0.0, '窗内照写且关窗(新语义)'
