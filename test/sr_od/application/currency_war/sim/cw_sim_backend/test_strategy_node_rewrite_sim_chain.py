"""sim 策略卡条件节点序列改写腿测试(镜像 src = sim/cw_sim_backend.py
的 _enter_node_window 窗开调用点 + kernel 纯决策 check_strategy_node_rewrite
的 sim 接入调用与世界真值落地面;kernel 原语单元面 = kernel/cw_gain_chain/
test_check_strategy_node_rewrite.py,本文件锁 sim 窗口接入调用)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-318-jueyi-yule-xingqiu.md §4 附锁(REVIEW-T318 §五④,sim 全链锁形态 =
T-105/T-283 sim 锁先例):

- 世界写锁:battle 位窗开 gold≥180 → node_seq_by_plane 整表改写 logic 写
  (evidence 'sim:engine:node_seq:strategy',sig 组 'sim:strategy')+
  strategy_conditional_done 纯卡名一次性标志位同拍追加;当前位 kind 不变
  (改写不含当前位,本窗收尾重读零失真);
- 短路锁:reward 位窗开 / gold<180 → 零策略写;
- 幂等锁:一次性标志位置位后任意窗开零新增策略写;
- 消费跟随锁:改写后 sequence_next 与节点窗 kind 取值按新序列。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _record_all_writes,
)

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    sequence_next,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    uninstall_backend,
)

_CARD = '决议:娱乐星球'

_PICK_SEED = 20261103

_RW_EV = 'sim:engine:node_seq:strategy'

#: 默认地面真值 P1(断言面 = 当前位与改写形逐槽值)。
_P1 = ('reward', 'reward', 'battle', 'battle', 'supply', 'battle',
       'encounter', 'reward', 'boss')


def _setup(seed: int = 31, *, grant: bool = True):
    """装配后端至 P1r1 备战窗(调用方负责 uninstall;驱动形态先例 =
    同目录 test_strategy_bench_leave_gold_sim_chain——本卡选卡无采样面,
    金现值由调用方观察覆盖)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    if grant:
        gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                             rng=random.Random(_PICK_SEED))
    return b


def _strategy_writes(calls: list[tuple]) -> list[tuple]:
    """本腿写行过滤(node_seq:strategy 证据,logic 通道)。"""
    return [c for c in calls if c[0] == 'logic' and c[2] == _RW_EV]


def test_battle_window_rewrites_world_and_latches(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """世界写锁主条:P1r3(battle)窗开 gold=200 → 场字段整表改写 + 纯卡名
    一次性标志位同拍;当前位 kind 保持 battle(窗收尾重读零失真);两笔写 sig 组
    'sim:strategy' logic 族。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.gold, 200, evidence='t:seed:gold', sig=_SIG_OBS)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 3))
        writes = _strategy_writes(calls)
        assert len(writes) == 2, f'本腿恰两笔写(改写+一次性标志位): {writes!r}'
        assert all(c[3].group_id == 'sim:strategy'
                   and c[3].family == 'logic_action' for c in writes), \
            '本腿写均 logic 族组 sim:strategy'
        seqs = gs.node_seq_by_plane.value
        assert seqs is not None, '改写写落场字段'
        assert seqs[1] == ('reward', 'reward', 'battle',
                           *(('reward',) * 5), 'boss'), \
            f'P1 改写形(当前位 r3 保留): {seqs[1]!r}'
        assert seqs[2][6] == 'boss' and seqs[3][6] == 'boss', 'boss 位保留'
        assert _CARD in (gs.strategy_conditional_done.value or ()), \
            '一次性标志位追加(纯卡名键)'
    finally:
        uninstall_backend()


def test_reward_window_no_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """短路锁(类型读法):P1r2(reward)窗开 gold≥180 → 零策略写(reward
    轴排除,裁决点 2 默认案)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.gold, 200, evidence='t:seed:gold', sig=_SIG_OBS)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert _strategy_writes(calls) == [], 'reward 位误触发'
        assert gs.node_seq_by_plane.value is None, '场字段未注册态维持'
    finally:
        uninstall_backend()


def test_gold_below_threshold_no_rewrite(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """短路锁(金门槛):battle 位窗开 gold=179 → 零策略写。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.gold, 179, evidence='t:seed:gold', sig=_SIG_OBS)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 3))
        assert _strategy_writes(calls) == [], '门槛下误触发'
    finally:
        uninstall_backend()


def test_latch_prevents_second_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    """幂等锁:改写命中后再进任意窗 → 零新增策略写(一次性标志位命中;改写后剩余
    槽位无 battle 位,重入天然零操作,一次性标志位仅省同值冗余写)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.gold, 200, evidence='t:seed:gold', sig=_SIG_OBS)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 3))
        assert len(_strategy_writes(calls)) == 2, '前置:首窗命中两笔'
        b._enter_node_window((1, 4))
        assert len(_strategy_writes(calls)) == 2, '一次性标志位后窗开零新增策略写'
    finally:
        uninstall_backend()


def test_consumers_follow_new_sequence(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """消费跟随锁:改写后 sequence_next 按新序列推导,下一窗节点 kind
    取值 = reward(节点窗 observe 锚定消费场字段现值)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.gold, 200, evidence='t:seed:gold', sig=_SIG_OBS)
        b._enter_node_window((1, 3))
        seqs = gs.node_seq_by_plane.value
        assert seqs is not None and sequence_next((1, 3), seqs) == (1, 4), \
            '后继按改写序列推导'
        b._enter_node_window((1, 4))
        node = gs.node.value
        assert node is not None and node.plane == 1 and node.round_num == 4 \
            and node.kind == 'reward', \
            f'节点窗 kind 按新序列取值: {node!r}'
    finally:
        uninstall_backend()


def test_unheld_card_no_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """短路锁(未持卡):金与节点位全达标但零持卡 → 零策略写(表外零
    条目对偶面)。"""
    b = _setup(grant=False)
    try:
        gs = b.gs
        gs.observe(gs.gold, 200, evidence='t:seed:gold', sig=_SIG_OBS)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 3))
        assert _strategy_writes(calls) == [], '未持卡误触发'
    finally:
        uninstall_backend()
