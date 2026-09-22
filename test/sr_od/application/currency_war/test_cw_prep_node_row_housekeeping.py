"""节点行观察归位·备战观察域消费位锁(迭代
changes/2026-09-21-shop-refresh-terminal 详设 §2.8;landing 3.4 判据
「备战入口 heavy 观察触发槽序表/台账写」)。

节点行写点原宿主 = 商店访问尾探针(``cw_screen_buy_cards.probe_node_type``,
已随其退役删除),整体迁备战 heavy 观察链节点行消费位
(``cw_screen_prep._write_prep_node_chain`` 同帧同点),识别零新增
(``observe_full`` 现役 ``read_node_sequence`` 调用回传 slots)。守卫逐位
随迁(本文件锁面):

1. 槽序表 :func:`store_plane_table`:按位面首帧写(位面锚 write-once,
   同位面不覆写;换位面重写)+ ``plane_lengths_seen`` 追加(现役口径 =
   类型可读槽数,过滤 node_type=None 位);**无轮位对齐门**(随迁原语义);
2. 台账按位合并 :func:`ledger_update_plane`('prep_row' 源):轮位对齐门
   (current 槽 idx == round_num−1,错位帧拒写)+ 环境宽限窗(窗内节点行
   合法变异中不落账;窗关判定在链写端关窗之前评估 = 探针时点语义平移);
3. 未识别图标采集:300s 防抖随迁(screen 注入;落盘经 cw_observe
   _SHOT_DIR 桩进 tmp_path,测试零真实副作用);
4. 备战入口 heavy 观察触发(接线锁):``CwScreenPrep._observe`` heavy 经
   ``observe_full`` 回传 slots → 槽序表/台账落位(触发面覆盖申报:每次
   备战入口 ≥ 现役仅商店尾触发)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
    run_node,
)

import sr_od.application.currency_war.kernel.cw_observe as cw_observe_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as prep_mod
from sr_od.application.currency_war.kernel.cw_exec_state import (
    get_node_ledger,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot

_SIG = ChannelSig(family='obs', actor='TestNodeRowHousekeeping', mode='read')


def _slot(idx: int, state: str, node_type: str | None = None,
          hu_dist: float | None = None, boss: str | None = None,
          cx: int = 0, cy: int = 0) -> NodeSlot:
    return NodeSlot(idx=idx, cx=cx, cy=cy, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _round3_slots() -> list[NodeSlot]:
    """round 3 对齐帧五槽:2 past + current(2)+ upcoming battle + boss 末槽
    (与链锁 test_cw_prep_node_chain 同形;past/boss 位类型恒 None = 现役
    识别口径)。"""
    return [
        _slot(0, 'past'),
        _slot(1, 'past'),
        _slot(2, 'current'),
        _slot(3, 'upcoming', 'battle', 0.8),
        _slot(4, 'upcoming', boss='测试首领'),
    ]


def _setup(plane: int = 1, round_num: int = 3):
    """容器 + 节点读口种子(窗口缺省关 = 非变异态)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind='prep'),
               evidence='t', sig=_SIG)
    return session, gs


def test_slot_table_first_frame_per_plane_write_once():
    """槽序表按位面首帧写:首帧落表 + 位面锚 + 长度追加;同位面二次读
    不覆写(write-once);换位面重写并续追长度史。"""
    session, gs = _setup(plane=1, round_num=3)
    _write = prep_mod._write_prep_node_chain

    _write(session, _round3_slots(), _SIG)
    nb = gs.node_books
    assert nb.plane_node_table == ['battle'], '槽序表 = 类型可读槽序(过滤 None 位)'
    assert nb.plane_node_table_plane == 1, '位面锚落位'
    assert nb.plane_lengths_seen == [1], '位面长度史追加(现役口径 = 类型可读槽数)'

    _write(session, _round3_slots(), _SIG)
    assert nb.plane_lengths_seen == [1], '同位面不覆写(write-once 守卫)'

    gs.observe(gs.node, NodeKey(plane=2, round_num=1, kind='prep'),
               evidence='t', sig=_SIG)
    _write(session, _round3_slots(), _SIG)
    assert nb.plane_node_table_plane == 2, '换位面重写'
    assert nb.plane_lengths_seen == [1, 1], '长度史按位面续追'


def test_ledger_merge_aligned_frame_with_window_closed():
    """台账按位合并(对齐帧 ∧ 宽限窗关):全槽序(含 past/boss None 位)
    按 'prep_row' 源合并落账。"""
    session, _gs = _setup(plane=1, round_num=3)
    prep_mod._write_prep_node_chain(session, _round3_slots(), _SIG)
    ledger = get_node_ledger(session)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '按位合并:None 位原样落位(合并语义 None 保旧)'
    assert ledger.seq_source[1] == 'prep_row', '备战行源标记'


def test_ledger_merge_rejected_on_misaligned_frame():
    """轮位对齐门随迁:current 槽 idx != round_num−1(漏检左移错位帧)
    → 台账拒写;槽序表无对齐门照写(守卫面不对称 = 随迁原语义)。"""
    session, gs = _setup(plane=1, round_num=3)
    bad = [_slot(0, 'past'), _slot(1, 'current'),
           _slot(2, 'upcoming', 'battle', 0.8),
           _slot(3, 'upcoming'), _slot(4, 'upcoming')]
    prep_mod._write_prep_node_chain(session, bad, _SIG)
    ledger = get_node_ledger(session)
    assert 1 not in ledger.seq_by_plane, '错位帧拒写台账(对齐门)'
    assert gs.node_books.plane_node_table == ['battle'], \
        '槽序表不受对齐门辖(守卫逐位随迁)'


def test_ledger_merge_skipped_while_env_window_open():
    """环境宽限窗随迁:变异窗开(投资环境选择后)→ 台账不落账,链照写
    且关窗(窗关判定在关窗之前评估 = 探针时点语义平移);窗关后的下帧
    补落账。"""
    import time

    session, gs = _setup(plane=1, round_num=3)
    ledger = get_node_ledger(session)
    ledger.env_grace_until = time.monotonic() + 45.0   # 预置开窗

    prep_mod._write_prep_node_chain(session, _round3_slots(), _SIG)
    assert 1 not in ledger.seq_by_plane, '变异窗内节点行合法变异中,不落账'
    assert gs.node_path.value is not None, '链写不受窗门(新语义)'
    assert ledger.env_grace_until == 0.0, '对齐 clean 读关窗'

    prep_mod._write_prep_node_chain(session, _round3_slots(), _SIG)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '窗关后下帧补落账'


def test_icon_capture_debounced_300s(monkeypatch, tmp_path):
    """未识别图标采集防抖随迁:超阈 upcoming 槽首帧采集(落盘进
    tmp_path);同 idx 300s 窗内不重采(帧内容已变仍拦 = 防抖在先);
    screen 缺席(离线)零采集。"""
    monkeypatch.setattr(prep_mod, '_NODE_ICON_SHOT_TS', {})   # 模块态隔离
    monkeypatch.setattr(cw_observe_mod, '_SHOT_DIR', tmp_path)
    from sr_od.application.currency_war.obs import cw_node_reader
    monkeypatch.setattr(cw_node_reader, 'NODE_ROW_RECT', (0, 0, 200, 200))

    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    slots = [_slot(0, 'past'), _slot(2, 'current'),
             _slot(4, 'upcoming', None, 3.5, cx=100, cy=100)]   # 超阈未识别

    session, _gs = _setup(plane=1, round_num=3)
    prep_mod._write_prep_node_chain(session, slots, _SIG, screen=frame)
    shots = list(tmp_path.glob('node_unknown_*'))
    assert len(shots) == 1, '超阈首采落盘(内容哈希命名)'
    assert 4 in prep_mod._NODE_ICON_SHOT_TS, '防抖时间戳落位'

    frame[50:150, 50:150] = 255   # 帧内容已变(哈希必新)
    prep_mod._write_prep_node_chain(session, slots, _SIG, screen=frame)
    assert len(list(tmp_path.glob('node_unknown_*'))) == 1, \
        '同 idx 300s 窗内不重采(防抖先于哈希去重)'

    prep_mod._write_prep_node_chain(session, slots, _SIG, screen=None)
    assert len(list(tmp_path.glob('node_unknown_*'))) == 1, \
        'screen 缺席 = 离线零采集(测试零 IO 面)'


def test_prep_entry_heavy_observation_triggers_writes(test_context, monkeypatch):
    """备战入口 heavy 观察触发(接线锁):CwScreenPrep._observe heavy 经
    observe_full 回传 slots → 节点行消费位同帧同点落位(槽序表 + 台账)。
    识别零新增:observe_full 桩只回传「现役 read_node_sequence 的产物
    形态」,读链不入桩面。"""
    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='prep'),
               evidence='t', sig=_SIG)

    def _fake_observe_full(ctx, screen, **kw):
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': SimpleNamespace(plane=1, round_num=3, level=None),
            'node_slots': _round3_slots(),
            'owned_equips': None, 'occupied_equips': None,
            'substate': {'node_seq': True},
        }

    monkeypatch.setattr(ofm, 'observe_full', _fake_observe_full)
    op = CwScreenPrep(test_context)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: SimpleNamespace(is_success=False))
    monkeypatch.setattr(op, '_reconcile_tracking',
                        lambda bv, dr, screen: (None, None, None))
    monkeypatch.setattr(prep_mod, 'row_area_centers', lambda ctx, name: [])
    monkeypatch.setattr(prep_mod, 'read_ore_sights', lambda ctx, screen: [])
    monkeypatch.setattr(prep_mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(prep_mod, 'read_deployed_count',
                        lambda ctx, screen: None)

    run_node(test_context, op, lambda: op._observe(True, screen=object()))

    assert gs.node_books.plane_node_table == ['battle'], \
        '备战入口 heavy 观察触发槽序表写(归位接线)'
    ledger = get_node_ledger(session)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '备战入口 heavy 观察触发台账落账(prep_row)'
