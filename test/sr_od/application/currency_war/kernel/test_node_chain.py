"""链观察测试面(链观察载体/查询/派生直定 + 过渡屏写端 + 备战帧写端 +
节点行归位 + 晶矿奖励通道挂接)。

语义权威版本 = game_state/chain-observation.md §2/§3/§6(载体与两链字段、
过渡屏基线/离场快照、备战屏现行链写、零内建回落);节点行归位判据 =
商店刷新终结判据迭代「备战入口 heavy 观察触发槽序表/台账写」;晶矿奖励
通道挂接 = ore-reward-channel 详设 §4-§5。

本文件按写端分三节,全部零读屏零真实 IO(模块级构造函数参数注入 /
harness run_node):
- 现行链载体与查询(kernel 字段语义 + 商店查链派生直定消费面);
- 过渡屏(``cw_screen_plane_transition._build_transition_chain`` +
  ``report_screen_plane_transition_obs``;写闸防御测试在
  test_screen_report_ports 承担,本文件不重复);
- 备战帧(``cw_screen_prep._write_prep_node_chain``:轮位对齐门/左移
  携带/boss SIFT 禁回落/变异窗/基线回填 + 槽序表/台账/未识别图标采集
  的节点行消费位 + heavy 观察触发接入调用)。
"""
from __future__ import annotations

import time
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
    NodeChain,
    NodeKey,
    TokenCell,
    chain_node_type,
    game_state_of,
    restore_state_snapshot,
)
from sr_od.application.currency_war.kernel.cw_ore_reward import (
    OreReward,
)
from sr_od.application.currency_war.kernel.cw_screen_report.boss_briefing import (
    CwScreenBossBriefingObs,
    report_screen_boss_briefing_obs,
)
from sr_od.application.currency_war.kernel.cw_screen_report.plane_transition import (
    CwScreenPlaneTransitionObs,
    report_screen_plane_transition_obs,
)
from sr_od.application.currency_war.obs.cw_node_reader import NodeSlot
from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_transition import (
    _build_transition_chain,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    _write_prep_node_chain,
)

_SIG = ChannelSig(family='obs', actor='TestChainWriter', mode='read')

# 节点行归位节 sig(live 挂接写 sig 形态,详设 ore-reward-channel §5:
# logic_hook 族,group_id 'prep:ore-channel',actor=CwScreenPrep,与生产
# cw_screen_prep._ORE_HOOK_SIG 同构)
_SIG_ROW = ChannelSig(family='obs', actor='TestNodeRowHousekeeping',
                      mode='read')
_SIG_HOOK = ChannelSig(family='logic_hook', actor='CwScreenPrep',
                       group_id='prep:ore-channel')
_ENV = '增发货币'


# ================================================================ 载体与查询

def _chain(plane: int, *tokens: str | None) -> NodeChain:
    """构造测试链:逐 token 生成 hu 通道格(None → none 通道)。"""
    cells = [TokenCell(token=t, channel=('none' if t is None else 'hu'))
             for t in tokens]
    return NodeChain(plane=plane, seq=cells)


def test_node_chain_fields_default_and_whole_frame_replace():
    """字段缺省 None;现行链整帧覆盖(不按位合并);基线独立不被现行链写触碰。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.node_path.value is None
    assert gs.node_path_baseline.value is None
    gs.observe(gs.node_path, _chain(1, 'reward', 'battle'),
               evidence='t', sig=_SIG)
    first = gs.node_path.value
    assert first is not None and first.plane == 1 \
        and first.seq[1].token == 'battle'
    gs.observe(gs.node_path, _chain(1, None, None, 'supply'),
               evidence='t', sig=_SIG)
    second = gs.node_path.value
    assert len(second.seq) == 3 and second.seq[0].token is None, \
        '整帧覆盖:第二帧全量替换,不留旧位'
    assert gs.node_path_baseline.value is None, \
        '现行链写不触基线(两字段独立)'
    gs.observe(gs.node_path_baseline, _chain(1, 'reward'),
               evidence='t', sig=_SIG)
    assert gs.node_path_baseline.value.seq[0].token == 'reward'


def test_chain_node_type_query_states():
    """查询口四态:命中/该格未辨/位越界/位面不匹配,外加链未写与零内建回落。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert chain_node_type(gs, 1, 2).token is None, '链未写 = 诚实缺位'
    gs.observe(gs.node_path, _chain(1, 'reward', None, 'battle'),
               evidence='t', sig=_SIG)
    assert chain_node_type(gs, 1, 1).token == 'reward'
    assert chain_node_type(gs, 1, 2).token is None, '该格未辨(None)'
    assert chain_node_type(gs, 1, 4).token is None, '位越界'
    assert chain_node_type(gs, 2, 1).token is None, '位面不匹配'
    gs.observe(gs.node_path_baseline,
               _chain(1, 'encounter', 'encounter', 'encounter'),
               evidence='t', sig=_SIG)
    assert chain_node_type(gs, 1, 2).token is None, \
        '零内建回落:基线在场也不兜底(链权威版本 §6)'


def test_derivation_shop_panel_chain_query_writes_kind():
    """类型派生商店查现行链(landing 消费接入调用):店开上下文写入
    → node.kind = 查链直定值(目标 = hist 反解位);生产时序等价形态 =
    N-1 帧 upcoming Hu 在 N 帧进店时在位。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('supply', 'hu', 1.1),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    gs.node_hist_pos = (1, 2)   # P1 r2(商店弹在 r2)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is not None, '直定写经节点域(node.kind)'
    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 2, 'supply'), '查链直定 = hist 反解位类型'


def test_derivation_shop_panel_chain_missing_zero_write():
    """链缺位(未写)→ 零写(禁猜,kind 保持缺省);hist 未推进亦零写。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is None, '链缺位零写(零内建回落)'
    # hist 未推进:链在位亦零写(目标位不可知)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)
    assert gs.node.value is None, 'hist 未推进 = 目标位不可知零写'


def test_derivation_non_shop_screen_no_chain_query():
    """非商店画面零查链零写:备战画面不触发查链派生(kind 不被链值污染)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('supply', 'hu'), TokenCell('battle', 'hu'),
    ]), evidence='t', sig=_SIG)
    gs.node_hist_pos = (1, 2)
    gs.observe_screen_context('货币战争-备战', sig=_SIG)
    assert gs.node.value is None, '非商店画面零查链零写'


_HOOK_SIG = ChannelSig(family='logic_hook', actor='TestChainWriter',
                       mode='compute')


def _seed_watermark(gs, pos_val: tuple[int, int]) -> None:
    """推进水位播种(备战分支等价形态:node_pos 逻辑层 + hist 双写)。"""
    gs.write_logic(gs.node_pos, pos_val, produced_by='TestChainWriter',
                   sig=_HOOK_SIG)
    gs.node_hist_pos = pos_val


def test_derivation_shop_panel_targets_observed_node_not_stale_hist():
    """查链目标 = 生效序与观察镜像的最新者(20260918-reconcile 第 11 例
    事故形态回归测试,run_20260918_074040)。

    病理:镜像已被读链写到 r3(店开帧 votes 读,(1,3,reward),观察源),
    推进水位仍 r2(备战帧未过,备战分支未计数);旧写法按 hist 反解查链
    (1,2) 并把 logic 回写 (1,2,reward)——后续备战帧真读 (1,3,battle)
    对 logic 旧键类型失配 → 统一观察对账安灯停局。修法:目标取
    max(生效序, 镜像序) = r3,查链 (1,3) 直定 battle,失配不发生。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('reward', 'hu', 0.1),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    _seed_watermark(gs, (1, 2))
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),
               evidence='votes', sig=_SIG)

    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'battle'), \
        '查链目标 = 镜像序 r3(不回写 r2),类型 = 链值 battle'


def test_derivation_shop_panel_popup_advanced_hist_wins_over_stale_mirror():
    """max 取向的推进优先分支:弹窗分支先推进(hist=3)而镜像仍滞留 r2 时,
    查链目标 = hist(shop 弹在刚进入的节点上,与旧 hist 单源行为一致)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node_path, NodeChain(plane=1, seq=[
        TokenCell('reward', 'hu'), TokenCell('supply', 'hu'),
        TokenCell('battle', 'hu', 0.7),
    ]), evidence='t', sig=_SIG)
    _seed_watermark(gs, (1, 3))
    gs.observe(gs.node, NodeKey(plane=1, round_num=2, kind='reward'),
               evidence='votes', sig=_SIG)

    gs.observe_screen_context('货币战争-备战-开商店', sig=_SIG)

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'battle'), \
        '镜像滞留时目标 = 推进水位 r3(推进分支已计数的新节点)'


def test_derived_node_type_regression_write_dropped_with_event():
    """类型直定倒退免疫测试(规则三同簇):目标序 < 镜像序 → 丢弃留证
    不写(镜像比派生目标鲜活,直定旧节点 = 把新节点回写旧键);镜像值
    保持,arbitrate obs_event 在案。走 BOSS 简报直定路径(类型直定迁移后
    的专属屏直定写端,design §2.5 表,目标 = hist)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='reward'),
               evidence='votes', sig=_SIG)
    gs.node_hist_pos = (1, 2)
    events = []
    gs.note_obs_event = (  # 实例级捕获(obs_event 发射面)
        lambda event, field, payload, verdict='', sig=None:
        events.append((event, field, payload)))

    report_screen_boss_briefing_obs(
        gs, CwScreenBossBriefingObs(on_screen=True))

    assert (gs.node.value.plane, gs.node.value.round_num,
            gs.node.value.kind) == (1, 3, 'reward'), \
        '倒退直定丢弃:镜像 (1,3) 不被 (1,2,boss) 回写'
    assert events and events[0][0] == 'arbitrate' and events[0][1] == 'node'
    assert events[0][2]['target_pos'] == '1-2', '留证行携带被拒目标'


# ================================================================ 过渡屏写端

def _tr_slot(idx: int, state: str = 'upcoming',
             node_type: str | None = None, hu_dist: float | None = 0.9,
             boss: str | None = None) -> NodeSlot:
    return NodeSlot(idx=idx, cx=0, cy=0, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _tr_p1_slots(boss_hit: bool = True) -> list[NodeSlot]:
    """P1 过渡屏全亮行(九槽):8 类型槽 + boss 末槽。"""
    return [
        _tr_slot(0, 'upcoming', 'reward'), _tr_slot(1, 'upcoming', 'supply'),
        _tr_slot(2, 'upcoming', 'battle'), _tr_slot(3, 'upcoming', 'battle'),
        _tr_slot(4, 'upcoming', 'supply'), _tr_slot(5, 'upcoming', 'battle'),
        _tr_slot(6, 'upcoming', 'encounter'), _tr_slot(7, 'upcoming', 'supply'),
        _tr_slot(8, 'upcoming', boss=('巳蛇' if boss_hit else None)),
    ]


def test_transition_opening_pipeline_writes_baseline_and_snapshot():
    """开局过渡屏(镜像与 hist 双缺)→ 观察管线(构造 → obs → report)
    写 P1 入口基线(transition_row)+ 现行链离场快照,行位面 = 1。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    assert gs.node.value is None and gs.node_hist_pos is None
    chain = _build_transition_chain(gs, _tr_p1_slots())
    assert chain is not None and chain.plane == 1, '开局行归属位面 = 1'
    report_screen_plane_transition_obs(
        gs, CwScreenPlaneTransitionObs(on_screen=True, chain=chain))
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
    chain = _build_transition_chain(gs, _tr_p1_slots())
    assert chain is not None and chain.plane == 2, '行归属位面 = 镜像(刚离开)'
    report_screen_plane_transition_obs(
        gs, CwScreenPlaneTransitionObs(on_screen=True, chain=chain))
    assert gs.node_path.value is not None \
        and gs.node_path.value.plane == 2, '离场快照 = 镜像位面(刚离开)'
    assert gs.node_path_baseline.value is None, \
        'P2/P3 基线不来自过渡屏(首帧回填承接,链权威版本 §3)'


def test_transition_mirror_missing_non_opening_skips():
    """非开局且镜像缺(hist 在):行归属不可知 → 构造 None(禁猜),
    report 同门跳写(诚实缺位)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.node_hist_pos = (2, 1)   # 非开局信号在,镜像缺
    assert _build_transition_chain(gs, _tr_p1_slots()) is None, \
        '镜像缺禁猜(构造诚实缺位)'
    report_screen_plane_transition_obs(
        gs, CwScreenPlaneTransitionObs(on_screen=True, chain=None))
    assert gs.node_path.value is None, '镜像缺跳写(诚实缺位)'
    assert gs.node_path_baseline.value is None


def test_transition_boss_sift_miss_and_none_cells():
    """boss SIFT miss → none 禁回落 Hu;无类型格 → none。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    slots = _tr_p1_slots(boss_hit=False)
    slots[2] = _tr_slot(2, 'upcoming', 'encounter', 3.5)   # 超阈未辨
    chain = _build_transition_chain(gs, slots)
    assert chain is not None, '前置:开局构造出链'
    assert chain.seq[8] == TokenCell(None, 'none'), 'SIFT miss 禁回落 Hu'
    assert chain.seq[2] == TokenCell(None, 'none'), '超阈未辨诚实缺位'


def test_transition_no_slots_or_no_session_noop():
    """slots 空 / 状态容器缺 → 零构造不炸(观察侧诚实缺位,report 不写)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    assert _build_transition_chain(gs, None) is None
    assert _build_transition_chain(None, _tr_p1_slots()) is None
    report_screen_plane_transition_obs(
        gs, CwScreenPlaneTransitionObs(on_screen=True, chain=None))
    assert gs.node_path.value is None and gs.node_path_baseline.value is None


# ================================================================ 备战帧链写端

def _pc_slot(idx: int, state: str, node_type: str | None = None,
             hu_dist: float | None = None,
             boss: str | None = None) -> NodeSlot:
    return NodeSlot(idx=idx, cx=0, cy=0, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _pc_round3_slots(boss_hit: bool = True) -> list[NodeSlot]:
    """round 3 备战帧五槽:2 past + current(2) + upcoming battle + boss 末槽。"""
    return [
        _pc_slot(0, 'past'),
        _pc_slot(1, 'past'),
        _pc_slot(2, 'current'),
        _pc_slot(3, 'upcoming', 'battle', 0.8),
        _pc_slot(4, 'upcoming', boss=('测试首领' if boss_hit else None)),
    ]


def _pc_prev_chain() -> NodeChain:
    """round 2 帧写下的旧链:槽 2/3 为 upcoming Hu(supply/battle)。"""
    return NodeChain(plane=1, seq=[
        TokenCell(None, 'dim'),
        TokenCell(None, 'none'),
        TokenCell('supply', 'hu', 1.2),
        TokenCell('battle', 'hu', 0.8),
        TokenCell(None, 'none'),
    ])


def _pc_setup():
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
    session, gs, ledger = _pc_setup()
    gs.observe(gs.node_path, _pc_prev_chain(), evidence='t', sig=_SIG)
    _write_prep_node_chain(session, _pc_round3_slots(), _SIG)
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
    """轮位对齐门(守卫矩阵一帧三靶):current 槽 idx != round-1(漏检
    左移错位帧)→ 现行链拒写、节点行台账拒写,槽序表无对齐门照写
    (守卫不对称 = 随迁原语义),变异窗不关。"""
    session, gs, ledger = _pc_setup()
    gs.observe(gs.node_path, _pc_prev_chain(), evidence='t', sig=_SIG)
    bad = [_pc_slot(0, 'past'), _pc_slot(1, 'current'),   # current 在 idx1,round=3
           _pc_slot(2, 'upcoming', 'battle', 0.8),
           _pc_slot(3, 'upcoming'), _pc_slot(4, 'upcoming')]
    _write_prep_node_chain(session, bad, _SIG)
    assert gs.node_path.value == _pc_prev_chain(), '错位帧拒写现行链'
    assert 1 not in get_node_ledger(session).seq_by_plane, '错位帧拒写台账(对齐门)'
    assert gs.node_books.plane_node_table == ['battle'], \
        '槽序表不受对齐门辖(守卫逐位随迁)'
    assert ledger.env_grace_until > time.monotonic(), '错位帧不关窗'


def test_prep_chain_first_frame_no_carry_baseline_filled():
    """首帧(无旧链):current 无携带 = none/None(fail-open 等价现役);
    基线仍回填。"""
    session, gs, ledger = _pc_setup()
    _write_prep_node_chain(session, _pc_round3_slots(boss_hit=False), _SIG)
    chain = gs.node_path.value
    assert chain.seq[2] == TokenCell(None, 'none'), '无携带首帧 current 诚实缺位'
    assert chain.seq[4] == TokenCell(None, 'none'), \
        'boss SIFT miss → none 禁回落 Hu(对抗 F14)'
    assert gs.node_path_baseline.value is not None, '首写回填基线'
    assert ledger.env_grace_until == 0.0


def test_prep_chain_plane_mismatch_no_carryover():
    """旧链跨位面(换位面未重写)→ 不跨面携带,current 诚实缺位。"""
    session, gs, ledger = _pc_setup()
    gs.observe(gs.node_path, NodeChain(plane=2, seq=[
        TokenCell('supply', 'hu', 1.2), TokenCell(None, 'none'),
    ]), evidence='t', sig=_SIG)
    _write_prep_node_chain(session, _pc_round3_slots(), _SIG)
    chain = gs.node_path.value
    assert chain.plane == 1 and chain.seq[2].token is None, \
        '跨位面旧链不携带(防陈旧链污染)'
    assert gs.node_path_baseline.value.seq == chain.seq


def test_prep_chain_unrecognized_upcoming_is_none():
    """upcoming Hu 超阈未辨 → none/None(不猜);窗内照写(链写不受窗门)。"""
    session, gs, ledger = _pc_setup()
    slots = [
        _pc_slot(0, 'past'), _pc_slot(1, 'past'), _pc_slot(2, 'current'),
        _pc_slot(3, 'upcoming', 'encounter', 3.5),   # > 2.8 未识别
        _pc_slot(4, 'upcoming', boss='测试首领'),
    ]
    _write_prep_node_chain(session, slots, _SIG)
    chain = gs.node_path.value
    assert chain.seq[3] == TokenCell(None, 'none'), '超阈未辨诚实缺位'
    assert ledger.env_grace_until == 0.0, '窗内照写且关窗'


# ================================================================ 节点行归位

def _hk_slot(idx: int, state: str, node_type: str | None = None,
             hu_dist: float | None = None, boss: str | None = None,
             cx: int = 0, cy: int = 0) -> NodeSlot:
    return NodeSlot(idx=idx, cx=cx, cy=cy, state=state, node_type=node_type,
                    hu_dist=hu_dist, boss=boss)


def _hk_round3_slots() -> list[NodeSlot]:
    """round 3 对齐帧五槽:2 past + current(2)+ upcoming battle + boss 末槽
    (与备战链测试同形;past/boss 位类型恒 None = 现役识别口径)。"""
    return [
        _hk_slot(0, 'past'),
        _hk_slot(1, 'past'),
        _hk_slot(2, 'current'),
        _hk_slot(3, 'upcoming', 'battle', 0.8),
        _hk_slot(4, 'upcoming', boss='测试首领'),
    ]


def _hk_setup(plane: int = 1, round_num: int = 3):
    """状态容器 + 节点读口种子(窗口缺省关 = 非变异态)。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind='prep'),
               evidence='t', sig=_SIG_ROW)
    return session, gs


def test_slot_table_first_frame_per_plane_write_once():
    """槽序表按位面首帧写:首帧落表 + 位面标记 + 长度追加;同位面二次读
    不覆写(write-once);换位面重写并续追长度史。"""
    session, gs = _hk_setup(plane=1, round_num=3)

    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    nb = gs.node_books
    assert nb.plane_node_table == ['battle'], '槽序表 = 类型可读槽序(过滤 None 位)'
    assert nb.plane_node_table_plane == 1, '位面标记落位'
    assert nb.plane_lengths_seen == [1], '位面长度史追加(现役口径 = 类型可读槽数)'

    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    assert nb.plane_lengths_seen == [1], '同位面不覆写(write-once 守卫)'

    gs.observe(gs.node, NodeKey(plane=2, round_num=1, kind='prep'),
               evidence='t', sig=_SIG_ROW)
    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    assert nb.plane_node_table_plane == 2, '换位面重写'
    assert nb.plane_lengths_seen == [1, 1], '长度史按位面续追'


def test_ledger_merge_aligned_frame_with_window_closed():
    """台账按位合并(对齐帧 ∧ 宽限窗关):全槽序(含 past/boss None 位)
    按 'prep_row' 源合并落账。"""
    session, _gs = _hk_setup(plane=1, round_num=3)
    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    ledger = get_node_ledger(session)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '按位合并:None 位原样落位(合并语义 None 保旧)'
    assert ledger.seq_source[1] == 'prep_row', '备战行源标记'


def test_ledger_merge_skipped_while_env_window_open():
    """环境宽限窗:变异窗开(投资环境选择后)→ 台账不落账,链照写
    且关窗(窗关判定在关窗之前评估 = 探针时点语义平移);窗关后的下帧
    补落账。"""
    session, gs = _hk_setup(plane=1, round_num=3)
    ledger = get_node_ledger(session)
    ledger.env_grace_until = time.monotonic() + 45.0   # 预置开窗

    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    assert 1 not in ledger.seq_by_plane, '变异窗内节点行合法变异中,不落账'
    assert gs.node_path.value is not None, '链写不受窗门'
    assert ledger.env_grace_until == 0.0, '对齐 clean 读关窗'

    _write_prep_node_chain(session, _hk_round3_slots(), _SIG_ROW)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '窗关后下帧补落账'


def test_icon_capture_debounced_300s(monkeypatch, tmp_path):
    """未识别图标采集防抖:超阈 upcoming 槽首帧采集(落盘进
    tmp_path);同 idx 300s 窗内不重采(帧内容已变仍拦 = 防抖在先);
    screen 缺席(离线)零采集。"""
    monkeypatch.setattr(prep_mod, '_NODE_ICON_SHOT_TS', {})   # 模块态隔离
    monkeypatch.setattr(cw_observe_mod, '_SHOT_DIR', tmp_path)
    from sr_od.application.currency_war.obs import cw_node_reader
    monkeypatch.setattr(cw_node_reader, 'NODE_ROW_RECT', (0, 0, 200, 200))

    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    slots = [_hk_slot(0, 'past'), _hk_slot(2, 'current'),
             _hk_slot(4, 'upcoming', None, 3.5, cx=100, cy=100)]   # 超阈未识别

    session, _gs = _hk_setup(plane=1, round_num=3)
    _write_prep_node_chain(session, slots, _SIG_ROW, screen=frame)
    shots = list(tmp_path.glob('node_unknown_*'))
    assert len(shots) == 1, '超阈首采落盘(内容哈希命名)'
    assert 4 in prep_mod._NODE_ICON_SHOT_TS, '防抖时间戳落位'

    frame[50:150, 50:150] = 255   # 帧内容已变(哈希必新)
    _write_prep_node_chain(session, slots, _SIG_ROW, screen=frame)
    assert len(list(tmp_path.glob('node_unknown_*'))) == 1, \
        '同 idx 300s 窗内不重采(防抖先于哈希去重)'

    _write_prep_node_chain(session, slots, _SIG_ROW, screen=None)
    assert len(list(tmp_path.glob('node_unknown_*'))) == 1, \
        'screen 缺席 = 离线零采集(测试零 IO 面)'


def test_prep_entry_heavy_observation_triggers_writes(test_context, monkeypatch):
    """备战入口 heavy 观察触发(接入调用测试):CwScreenPrep._observe heavy 经
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
               evidence='t', sig=_SIG_ROW)

    def _fake_observe_full(ctx, screen, **kw):
        return {
            'bench_view': None, 'deployed_rows': None,
            'read_receipt': SimpleNamespace(plane=1, round_num=3, level=None),
            'node_slots': _hk_round3_slots(),
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
        '备战入口 heavy 观察触发槽序表写(归位接入调用)'
    ledger = get_node_ledger(session)
    assert ledger.seq_by_plane[1] == [None, None, None, 'battle', None], \
        '备战入口 heavy 观察触发台账落账(prep_row)'


# ============================================================ 晶矿奖励通道挂接

def _run_prep_heavy_with_fakes(test_context, monkeypatch, session, *,
                               plane: int, round_num: int = 1,
                               ores: list | None = None,
                               level: int | None = 5):
    """备战 heavy 观察跑壳(ore 通道接入调用测试专用;每调用 = 一个备战环,
    op 现场重建——跨环幂等守卫不住 op 实例,测试形态与生产每环重建对齐)。

    fake ``observe_full`` **真实写 node/level 状态容器域**(与 read_game_state
    漏斗写点同构):node 域 plane 的权威写点在漏斗内,接入调用判据 = 回执后
    现值——fake 不写 node 而在 setup 预置,则「回执后读 plane」与
    「回执前读」不可分辨,按漏斗前值构造的断言假绿(ore-reward-channel
    接入调用批测试构造约束)。

    ``ores`` 元素 = ``(色档, 点, 半径)``(read_ore_sights 产物形态,
    点带 x/y 属性);``level`` = fake 同帧写入的 level 域值(None = 不写,
    状态容器保现值)。
    """
    from sr_od.application.currency_war.obs import cw_observe_full as ofm
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        CwScreenPrep,
    )

    gs = game_state_of(session)

    def _fake_observe_full(ctx, screen, **kw):
        gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num,
                                    kind='prep'), evidence='t', sig=_SIG_ROW)
        if level is not None:
            gs.observe(gs.level, int(level), sig=_SIG_ROW)
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
    同构 test_ore._record_gen_writes 的 logic 分支。"""
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
    gs.observe(gs.active_env, _ENV, sig=_SIG_ROW)

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
    gs.observe(gs.active_env, _ENV, sig=_SIG_ROW)
    calls = _record_logic_writes(gs, monkeypatch)

    # 环 1:位面 1 首备战环,矿未现(位面开局声明时点常先于矿呈现)
    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=1, ores=[])
    assert gs.ore_declared_pending.value == ((_ENV, 1, 6),), \
        '环 1 入队(位面 1 档 = 6 金),矿未现留队'

    # 环 2:op 重建;矿现 → 入队幂等守卫(pending 已登记不重发)+ 生成即消费
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
    """电平过期清理留痕(live 接入调用面):位面过渡帧(p1 残留 → p2)旧
    plane 条目移除(pending/done 同清理),evidence 逐旧位面留痕
    ``ore_declared_expired#p1``;当前面声明照常入队(矿未现留队)。"""
    session = cw4_session()
    gs = game_state_of(session)
    gs.observe(gs.active_env, _ENV, sig=_SIG_ROW)
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
    gs.observe(gs.active_env, _ENV, sig=_SIG_ROW)
    calls = _record_logic_writes(gs, monkeypatch)

    _run_prep_heavy_with_fakes(test_context, monkeypatch, session,
                               plane=1, ores=[])

    assert gs.ore_declared_done.value == ((_ENV, 1),), 'done 随快照存续'
    assert gs.ore_declared_pending.value == (), '零重发'
    assert not [c for c in calls if c[0].startswith('ore_declared')], \
        f'done 守卫命中零声明域写行: {calls}'
