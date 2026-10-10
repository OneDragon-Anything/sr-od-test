"""节点行观察归位·备战观察域消费位锁(迭代
商店刷新终结判据
「备战入口 heavy 观察触发槽序表/台账写」)。

节点行写点原宿主 = 商店访问尾探针(``cw_screen_shop.probe_node_type``,
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
   备战入口 ≥ 现役仅商店尾触发);
5. 晶矿奖励通道 live 接线锁(迭代 2026-10-10-ore-reward-attach 3.4,详设
   ore-reward-channel §4-§5):备战 heavy 观察 spheres 写端过挂接入口
   ``report_spheres_observed``(单一写径),声明入队/过期电平检查在
   observe_full 回执后、spheres 写前——**入队测试的 fake observe_full 必须
   真实写 node/level 容器域**(与 read_game_state 漏斗写点同构;在 setup
   预置 node 则「回执后读 plane」与「回执前读」不可分辨,按漏斗前值构造
   的断言假绿)。
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
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    game_state_of,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot

_SIG = ChannelSig(family='obs', actor='TestNodeRowHousekeeping', mode='read')
# live 挂接写 sig 形态(详设 ore-reward-channel §5:logic_hook 族,
# group_id 'prep:ore-channel',actor=CwScreenPrep;与生产
# cw_screen_prep._ORE_HOOK_SIG 同构)
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenPrep',
                       group_id='prep:ore-channel')
_ENV = '增发货币'


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


# ============================================================ 晶矿奖励通道 live 接线(3.4)


def _run_prep_heavy_with_fakes(test_context, monkeypatch, session, *,
                               plane: int, round_num: int = 1,
                               ores: list | None = None,
                               level: int | None = 5):
    """备战 heavy 观察跑壳(ore 通道接线测试专用;每调用 = 一个备战环,
    op 现场重建——跨环幂等守卫不住 op 实例,测试形态与生产每环重建对齐)。

    fake ``observe_full`` **真实写 node/level 容器域**(与 read_game_state
    漏斗写点同构):node 域 plane 的权威写点在漏斗内,接线判据 = 回执后
    现值——fake 不写 node 而在 setup 预置,则「回执后读 plane」与
    「回执前读」不可分辨,按漏斗前值构造的断言假绿(landing 3.4 测试
    构造约束)。

    ``ores`` 元素 = ``(色档, 点, 半径)``(read_ore_sights 产物形态,
    点带 x/y 属性);``level`` = fake 同帧写入的 level 域值(None = 不写,
    容器保现值)。
    """
    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    gs = game_state_of(session)

    def _fake_observe_full(ctx, screen, **kw):
        gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num,
                                    kind='prep'), evidence='t', sig=_SIG)
        if level is not None:
            gs.observe(gs.level, int(level), sig=_SIG)
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': SimpleNamespace(plane=plane, round_num=round_num,
                                            level=level),
            'node_slots': None,
            'owned_equips': None, 'occupied_equips': None,
            'substate': {},
        }

    monkeypatch.setattr(ofm, 'observe_full', _fake_observe_full)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = CwScreenPrep(test_context)
    monkeypatch.setattr(op, 'park_cursor', lambda **k: None)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: SimpleNamespace(is_success=False))
    monkeypatch.setattr(op, '_reconcile_tracking',
                        lambda bv, dr, screen: (None, None, None))
    monkeypatch.setattr(prep_mod, 'row_area_centers', lambda ctx, name: [])
    monkeypatch.setattr(prep_mod, 'read_ore_sights',
                        lambda ctx, screen: list(ores or ()))
    monkeypatch.setattr(prep_mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(prep_mod, 'read_deployed_count',
                        lambda ctx, screen: None)
    run_node(test_context, op, lambda: op._observe(True, screen=object()))
    return gs


def _record_logic_writes(gs, monkeypatch) -> list[tuple[str, str | None, int]]:
    """包装 write_logic 记录声明域写行 ``(字段名, evidence, 条数增量)``——
    入队与消费移除写行同样无 evidence,靠条数增量分向(入队 = 增量 > 0);
    同构 test_cw_ore_channel._record_writes 的 logic 腿。"""
    calls: list[tuple[str, str | None, int]] = []
    real = gs.write_logic

    def rec(target, value, *, produced_by, evidence=None, sig, note=''):
        name = gs._field_name(target)
        old_v = getattr(gs, name, None)
        old = getattr(old_v, 'value', None)
        try:
            delta = len(tuple(value)) - len(tuple(old or ()))
        except TypeError:
            delta = 0
        calls.append((name, evidence, delta))
        real(target, value, produced_by=produced_by, evidence=evidence,
             sig=sig, note=note)

    monkeypatch.setattr(gs, 'write_logic', rec)
    return calls


def test_prep_ore_enqueue_before_same_frame_spheres_write(
        test_context, monkeypatch):
    """入队先于同帧 spheres 写(次序硬约束承载性判据):位面过渡帧
    (fake 漏斗真实写 node plane=2)矿首现 → 该帧生成即含声明附着
    (位面 2 档 = 8 金)+ 消费闭合。次序接反则本帧生成时 pending 空,
    附着为普通采样值且声明留队(该帧后无新现即永不附着)。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.active_env, _ENV, sig=_SIG)

    _run_prep_heavy_with_fakes(
        test_context, monkeypatch, session, plane=2,
        ores=[('金', SimpleNamespace(x=100, y=100), 30)])

    attached = (gs.ore_rewards.value or {}).get('100,100')
    assert attached == OreReward(kind='gold', gold=8), \
        f'位面首帧生成即含声明附着(8 金): {attached}'
    assert gs.ore_declared_pending.value == (), '声明消费(pending 移除)'
    assert gs.ore_declared_done.value == ((_ENV, 2),), '消费标记(done 追加)'


def test_prep_ore_level_idempotent_across_prep_rings(
        test_context, monkeypatch):
    """电平静幂等(跨环单发):同位面多备战环(op 每环重建、环间声明已
    消费)声明仅入队一次、仅兑现一次——6 金真值场景;守卫失效形态 =
    每环重发(3 环 3×6=18 金),以入队写行计数作对照断言(恰 1 行)。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.active_env, _ENV, sig=_SIG)
    calls = _record_logic_writes(gs, monkeypatch)

    # 环 1:位面 1 首备战环,矿未现(位面开局声明时点常先于矿呈现)
    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=1, ores=[])
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), \
        '环 1 入队(位面 1 档 = 6 金),矿未现留队'

    # 环 2:op 重建;矿现 → 入队幂等守卫(pending 在册不重发)+ 生成即消费
    _run_prep_heavy_with_fakes(
        test_context, monkeypatch, session, plane=1,
        ores=[('金', SimpleNamespace(x=100, y=100), 30)])
    assert (gs.ore_rewards.value or {}).get('100,100') \
        == OreReward(kind='gold', gold=6), '声明金 6 兑现为附着'
    assert gs.ore_declared_pending.value == ()
    assert gs.ore_declared_done.value == ((_ENV, 1),)

    # 环 3:op 又重建;矿已点掉(空读)→ cleanup;done 守卫不重入队
    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=1, ores=[])
    assert gs.ore_declared_pending.value == (), 'done 守卫:跨环不重入队'
    assert gs.ore_declared_done.value == ((_ENV, 1),), '仅兑现一次'
    assert not (gs.ore_rewards.value or {}), '矿消失清洗(空读照写 count=0)'

    # 入队写行计数:pending 追加写(条数增量 > 0)恰 1 行——守卫失效
    # (每环重发)时为 3 行(3×6=18 金对照面);消费移除写(增量 < 0)
    # 不计入
    enqueues = [c for c in calls
                if c[0] == 'ore_declared_pending' and c[2] > 0]
    assert len(enqueues) == 1, f'跨三环入队仅一次: {calls}'


def test_prep_ore_expiry_cleanup_trace_on_plane_transition(
        test_context, monkeypatch):
    """电平过期清理留痕(live 接线面):位面过渡帧(p1 残留 → p2)旧
    plane 条目移除(pending/done 同清理),evidence 逐旧位面留痕
    ``ore_declared_expired#p1``;当前面声明照常入队(矿未现留队)。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.active_env, _ENV, sig=_SIG)
    # 旧位面残留(位面 1 声明已入队且已消费)
    gs.write_logic(gs.ore_declared_pending, ((_ENV, 1, 6),),
                   produced_by='test-seed', sig=_SIG_HOOK)
    gs.write_logic(gs.ore_declared_done, ((_ENV, 1),),
                   produced_by='test-seed', sig=_SIG_HOOK)
    calls = _record_logic_writes(gs, monkeypatch)

    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=2, ores=[])

    assert gs.ore_declared_pending.value == ((_ENV, 2, 8),), \
        '旧位面条目过期清理 + 当前面声明入队(矿未现留队)'
    assert gs.ore_declared_done.value == (), 'done 同清理'
    expiry = [e for _n, e, _d in calls
              if _n.startswith('ore_declared') and e is not None]
    assert expiry == ['ore_declared_expired#p1', 'ore_declared_expired#p1'], \
        f'pending/done 各一行过期留痕: {calls}'


def test_prep_ore_restored_snapshot_done_no_reenqueue(
        test_context, monkeypatch):
    """恢复局(快照含 done)不重发:声明已消费的局断点经快照恢复(done
    随快照存续)后续跑,同位面电平检查命中 done 守卫 → 零入队写行、
    pending/done 域零变化。"""
    donor = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    donor.write_logic(donor.ore_declared_done, ((_ENV, 1),),
                      produced_by='t', sig=_SIG_HOOK)
    snap = donor.full_state_snapshot()

    session = cw4_session()
    gs = game_state_of(session)
    restore_state_snapshot(gs, snap)
    # 恢复局续跑首帧 env 观察(电平输入;快照直构 donor 无 env 值)
    gs.observe(gs.active_env, _ENV, sig=_SIG)
    calls = _record_logic_writes(gs, monkeypatch)

    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=1, ores=[])

    assert gs.ore_declared_done.value == ((_ENV, 1),), 'done 随快照存续'
    assert gs.ore_declared_pending.value == (), '零重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')], \
        f'done 守卫命中零声明域写行: {calls}'
