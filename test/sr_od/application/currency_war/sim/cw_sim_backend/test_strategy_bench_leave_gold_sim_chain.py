"""sim 策略卡备战席条件离场金节点窗效果条目测试(镜像 src = sim/cw_sim_backend.py
的 _begin_node_window 备战席条件离场金币效果条目 + kernel 纯判定
check_strategy_bench_leave_gold 的 sim 调用点状态副本写;kernel 原语单元面 =
kernel/cw_gain_chain/test_check_strategy_bench_leave_gold.py,本文件锁
sim 窗口接入调用与状态副本里的值落地面)。

测试面依据 = 原稿锁面 designs/
原稿锁面(§ 号 = 原稿节序)§4 锁 3 + 原稿评审锁(§ 号 = 原稿节序)§四④:
- sim 状态副本锁(锁 3):持卡 + 席内 1星花火/火花局节点窗推进 → 金 observe
  独立笔 = Σ计划金币(2+4=6)+ evidence 含逐单位明细 + sig 组
  'sim:strategy';匹配槽置空(卖备战席角色置 empty 同形);
- 幂等锁(锁 4):同节点窗重放(_window_begun_pos 守卫整段早退)零新增
  写行、金不双发;
- 移出制结构性零重发(锁 4 变体):单位离场后下一窗条件自然消失零发放
  (与零 done 一次性标志位计数效果条目「每窗重查」的结构差异——本卡产出含状态移除,
  同单位不可二次离场)。
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
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    Unit,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    uninstall_backend,
)

_CARD = '愚者恶作剧'

_PICK_SEED = 20261103

_GOLD_TOTAL = 6   # Σ计划金币 = 花火 2 + 火花 4

#: 逐单位明细 evidence(覆盖席视图 = 花火@s0 + 火花@s1;sim_evidence
#: 前缀 'sim:engine:' 契约,详 cw_sim_base 模块 docstring)。
_EV = (f'sim:engine:strategy:bench_leave_gold:{_CARD}'
       ':p1r2:花火@s0+2;火花@s1+4')


def _setup(seed: int = 31, *, grant: bool = True):
    """装配后端至 P1r1 备战窗(调用方负责 uninstall;驱动形态先例 =
    同目录 test_strategy_bench_count_xp_sim_chain——本卡无采样面,
    状态副本态 = 开局种子 + 观察覆盖席视图)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    if grant:
        gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                             rng=random.Random(_PICK_SEED))
    return b


def _bench_leave_view() -> BenchView:
    """覆盖席视图:s0 = 1星花火、s1 = 1星火花、余空槽(明细 evidence 的
    槽位坐标系基准)。"""
    slots = [
        BenchSlot(kind='unit',
                  unit=Unit(char_id='花火', star=1, equips=[])),
        BenchSlot(kind='unit',
                  unit=Unit(char_id='火花', star=1, equips=[])),
    ]
    slots += [BenchSlot(kind='empty')] * 7
    return BenchView(slots=slots, capacity=9)


def _watch_gold_writes(gs, monkeypatch: pytest.MonkeyPatch):
    """捕获 gold 域 observe 写值(记录包装透传真实现;窗口内金域多条效果条目分写,
    本效果条目金笔按 evidence 定位取值)。"""
    gold_writes: list[tuple[int, str | None]] = []
    real = gs.observe

    def rec(target, value, *, evidence=None, sig, note=''):
        if gs._field_name(target) == 'gold':
            gold_writes.append((int(value), evidence))
        real(target, value, evidence=evidence, sig=sig, note=note)

    monkeypatch.setattr(gs, 'observe', rec)
    return gold_writes


def test_node_window_leaves_gold_and_slots(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """窗发放主条(锁 3):持卡 + 席内 1星花火/火花 → 进 (1,2) 窗:金笔
    = 窗前现值 +6(evidence 逐单位明细),匹配槽置空、capacity 不动,
    两笔写均 obs 族组 'sim:strategy'。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.bench, _bench_leave_view(),
                   evidence='t:seed:bench', sig=_SIG_OBS)
        gold_before = int(gs.gold.value or 0)
        gold_writes = _watch_gold_writes(gs, monkeypatch)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        mine = [(v, ev) for v, ev in gold_writes if ev == _EV]
        assert mine == [(gold_before + _GOLD_TOTAL, _EV)], \
            f'金笔 = 窗前现值 + Σ计划金币: {mine}'
        view = gs.bench.value
        assert view is not None and view.capacity == 9, 'capacity 不动'
        assert view.slots[0].kind == 'empty', 's0 花火离场置空'
        assert view.slots[1].kind == 'empty', 's1 火花离场置空'
        bench_calls = [c for c in calls
                       if c[1] == 'bench' and c[2] == _EV]
        assert len(bench_calls) == 1, '离场写恰一笔'
        assert all(c[0] == 'obs' and c[3].family == 'obs'
                   and c[3].group_id == 'sim:strategy'
                   for c in calls if c[2] == _EV), \
            '本效果条目写均 obs 族组 sim:strategy'
    finally:
        uninstall_backend()


def test_replay_guard_no_double_fire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同节点窗重放守卫(锁 4 幂等):_begin_node_window 二次进入
    (_window_begun_pos 整段早退)→ 零新增写行、金不双发。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.bench, _bench_leave_view(),
                   evidence='t:seed:bench', sig=_SIG_OBS)
        b._enter_node_window((1, 2))
        gold_after_first = int(gs.gold.value or 0)
        calls = _record_all_writes(gs, monkeypatch)
        b._begin_node_window()   # 同节点窗重放(直构)
        assert calls == [], '窗重放出现新增写行'
        assert int(gs.gold.value or 0) == gold_after_first, '窗重放双发'
    finally:
        uninstall_backend()


def test_units_gone_next_window_no_refire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """移出制结构性零重发(锁 4 变体):单位已离场,下一节点窗条件自然
    消失零发放(状态移除制的可重复性语义——同单位不可二次离场,零 done
    一次性标志位不构成重发面)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.bench, _bench_leave_view(),
                   evidence='t:seed:bench', sig=_SIG_OBS)
        b._enter_node_window((1, 2))
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 3))
        assert [c for c in calls if c[2] and 'bench_leave_gold' in c[2]] \
            == [], '单位已离场下一窗零发放'
        assert gs.bench.value is not None, '窗照常推进'
    finally:
        uninstall_backend()


def test_no_card_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """未持卡零写(锁 3 反向):席内匹配单位已登记但不持卡 → 窗推进零本效果条目
    写(白名单表外禁从效果原文自动猜装的窗口面)。"""
    b = _setup(grant=False)
    try:
        gs = b.gs
        gs.observe(gs.bench, _bench_leave_view(),
                   evidence='t:seed:bench', sig=_SIG_OBS)
        gold_before = int(gs.gold.value or 0)
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[2] and 'bench_leave_gold' in c[2]] \
            == [], '未持卡窗零本效果条目写'
        view = gs.bench.value
        assert view.slots[0].kind == 'unit', '未持卡单位不离场'
        assert int(gs.gold.value or 0) >= gold_before, '金不减'
    finally:
        uninstall_backend()


def test_no_match_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """席内无匹配单位零写(锁 3 反向):持卡但席内全非 1星花火/火花
    (开局 4 希儿种子形态)→ 零本效果条目写、席视图不动。"""
    b = _setup()
    try:
        gs = b.gs
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[2] and 'bench_leave_gold' in c[2]] \
            == [], '无匹配单位窗零本效果条目写'
    finally:
        uninstall_backend()
