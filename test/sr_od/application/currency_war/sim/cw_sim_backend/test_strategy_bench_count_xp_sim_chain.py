"""sim 策略卡备战席计数经验节点窗效果条目测试(镜像 src = sim/cw_sim_backend.py
的 _begin_node_window 备战席计数 XP 效果条目 + kernel 纯判定
check_strategy_bench_count_xp 的 sim 调用点状态副本写;kernel 原语单元面 =
kernel/cw_gain_chain/test_check_strategy_bench_count_xp.py,本文件锁
sim 窗口接入调用与状态副本里的值落地面)。

测试面依据 = 设计稿(原件已退役) designs/
设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 3/4/5 + 已退役评审稿(§ 号 = 原稿节序)§四④:
- sim 状态副本锁(锁 3):持卡 + 席内单位 ≤4 局节点窗推进 → gs.xp/gs.level
  按 xp_apply_amount 结转(含跨级结转算例),evidence ``xp:bench_count``
  独立笔 + sig 组 'sim:xp' 断言;席 >4 零写;未持卡零写;
- 幂等锁(锁 4):同节点窗重放(_window_begun_pos 守卫整段早退)零新增
  写行;连续两个满足节点各发一次(可重复性——与孪生素数 at-most-once
  的结构差异锁);
- 拿卡当节点不发锁(锁 5):选卡落地所在节点窗(P1r1)前置段已跑过,
  本卡后补零发放(发放起点 = 下一节点窗)。

驱动形态 = _enter_node_window 直通点(锚定补推路径真形态);引擎驱动助手
import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只 import
复用不改;先例 = 同目录 test_strategy_empty_equip_xp_sim_chain.py)。
sim 开局备战席种子 = 4 单位(M06),恰在「≤4」门槛上——满足窗天然成立,
超门槛用例经观察通道覆盖席视图构造 5 单位。
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

from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
    xp_apply_amount,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    Unit,
    bench_units_of,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    uninstall_backend,
)

_CARD = '人才空洞'

_PICK_SEED = 20261103

_XP_EV = 'sim:engine:xp:bench_count'


def _setup(seed: int = 31, *, grant: bool = True):
    """装配后端至 P1r1 备战窗(调用方负责 uninstall;驱动形态先例 = 同目录
    test_strategy_empty_equip_xp_sim_chain——本卡无即时效果条目,无装备采样面,
    状态副本态即开局种子)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    if grant:
        gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                             rng=random.Random(_PICK_SEED))
    return b


def _bench_view(unit_count: int) -> BenchView:
    """N 单位 + 空槽 pad 的席视图(超门槛用例观察通道覆盖;先例 = 同文件
    族 equips 清空观察,观察→观察覆盖静默)。"""
    slots = [BenchSlot(kind='unit',
                       unit=Unit(char_id='希儿', star=1, equips=[]))
             for _ in range(unit_count)]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    return BenchView(slots=slots, capacity=9)


def test_pick_window_structural_no_fire() -> None:
    """拿卡当节点不发(锁 5,结构性):P1r1 窗前置段先于选卡落地跑过
    (窗守卫已记 (1,1)),后补拿卡当窗零发放——经验笔 evidence 无
    bench_count(发放起点 = 下一节点窗)。"""
    b = _setup()
    try:
        xp = b.gs.xp.value
        assert xp is not None, '前置:sim 开局经验种子已登记'
        assert b.gs.xp.evidence != _XP_EV, '拿卡当窗不应发放'
    finally:
        uninstall_backend()


def test_node_window_bench_at_threshold_grants(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """门槛窗发放(锁 3 主条):开局席种子 4 单位恰在「≤4」上,进 (1,2)
    窗 → xp 恰 +3 按纯函数结转,evidence 独立笔 + sig 组 'sim:xp';
    本窗恰两笔 xp 域写(level+xp)。"""
    b = _setup()
    try:
        gs = b.gs
        assert len(bench_units_of(gs)) == 4, \
            '前置:开局席种子 4 单位(M06)恰在门槛上'
        before_lv = int(gs.level.value)
        before_xp = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        want_lv, want_cur = xp_apply_amount(before_lv, int(before_xp[0]), 3)
        assert gs.level.value == want_lv, 'level 按结转式推进'
        assert gs.xp.value == (want_cur, XP_TO_NEXT_LEVEL.get(
            want_lv, before_xp[1])), f'xp 恰 +3: {gs.xp.value}'
        assert gs.xp.source == 'observation', '状态副本数值面 = 观察通道'
        assert gs.xp.evidence == _XP_EV, f'独立笔缺失: {gs.xp.evidence}'
        xp_calls = [c for c in calls if c[1] in ('level', 'xp')]
        assert [(c[1], c[2]) for c in xp_calls] == [
            ('level', _XP_EV), ('xp', _XP_EV)], \
            f'本窗 xp 域写恰两笔: {xp_calls}'
        assert all(c[3].family == 'obs' and c[3].group_id == 'sim:xp'
                   for c in xp_calls), 'sig 组 = sim:xp(apply_node_xp 同域)'
    finally:
        uninstall_backend()


def test_threshold_carry_levelup(monkeypatch: pytest.MonkeyPatch) -> None:
    """跨级结转算例(锁 3):门槛恰跨形态(3 级余 2 + 3 → 4 级余 1)——
    状态副本等级随白送经验真实推进(升级联动发牌概率的耦合面以此为底)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.level, 3, evidence='t:seed:lv', sig=_SIG_OBS)
        gs.observe(gs.xp, (XP_TO_NEXT_LEVEL[3] - 2, XP_TO_NEXT_LEVEL[3]),
                   evidence='t:seed:xp', sig=_SIG_OBS)
        b._enter_node_window((1, 2))
        assert gs.level.value == 4, '升一级'
        assert gs.xp.value == (1, XP_TO_NEXT_LEVEL[4]), \
            f'余量 4−2+3−4=1: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '跨级笔 evidence 不变'
    finally:
        uninstall_backend()


def test_replay_guard_no_double_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    """同节点窗重放守卫(锁 4 幂等):_begin_node_window 二次进入
    (_window_begun_pos 整段早退)→ 零新增写行、xp 不双发。"""
    b = _setup()
    try:
        gs = b.gs
        b._enter_node_window((1, 2))
        xp_after_first = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._begin_node_window()   # 同节点窗重放(直构)
        assert calls == [], '窗重放出现新增写行'
        assert gs.xp.value == xp_after_first, '窗重放双发'
    finally:
        uninstall_backend()


def test_consecutive_windows_each_fire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """连续两满足节点各发一次(锁 4 可重复性):零 done 一次性标志位的结构差异锁
    (与孪生素数 at-most-once 分道)——(1,2)/(1,3) 两窗各 +3(第二窗
    余量按纯函数期望对拍,不落跨级即按当前级门槛续攒)。"""
    b = _setup()
    try:
        gs = b.gs
        b._enter_node_window((1, 2))
        first = gs.xp.value
        lv_after_first = int(gs.level.value)
        want_lv, want_cur = xp_apply_amount(lv_after_first, first[0], 3)
        b._enter_node_window((1, 3))
        assert gs.level.value == want_lv, '第二窗 +3 按结转式推进'
        assert gs.xp.value == (want_cur,
                               XP_TO_NEXT_LEVEL.get(want_lv, first[1])), \
            f'第二窗 +3 结转: {first} → {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '第二窗独立笔'
    finally:
        uninstall_backend()


def test_bench_over_threshold_zero_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """席超门槛零写(锁 3 反向):观察通道覆盖席视图为 5 单位 → 谓词
    失败,窗推进零 xp 写(>4 不满足「小于等于4名」)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.bench, _bench_view(5), evidence='t:seed:bench',
                   sig=_SIG_OBS)
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '席 >4 窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()


def test_no_card_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """未持卡零写(锁 3 反向):门槛满足但不持卡 → 零发放(白名单表外
    禁从效果原文自动猜装的窗口面)。"""
    b = _setup(grant=False)
    try:
        gs = b.gs
        assert len(bench_units_of(gs)) == 4, '前置:门槛天然满足'
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '未持卡窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()


# ── 姊妹人才济济(202701,'ge' 行)sim 状态副本锁(T-193 批:机制件零新,
# 谓词 ge 分支在码,通道级 evidence 同笔族)──
_CARD2 = '人才济济'


def test_ge_eight_units_window_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """姊妹持卡+席 ≥8(锁):观察通道覆盖席视图为 8 单位 → 节点窗 XP +3
    状态副本写走全链(evidence 通道级 ``xp:bench_count`` 勿假设带卡名)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.write_logic(gs.active_strategies, [_CARD2],
                       produced_by='test-seed', evidence='t:card2',
                       sig=_SIG)
        gs.observe(gs.bench, _bench_view(8), evidence='t:seed:bench8',
                   sig=_SIG_OBS)
        before_lv = int(gs.level.value)
        before_xp = gs.xp.value
        b._enter_node_window((1, 2))
        want_lv, want_cur = xp_apply_amount(before_lv, int(before_xp[0]), 3)
        assert gs.level.value == want_lv, 'level 按结转式推进'
        assert gs.xp.value == (want_cur, XP_TO_NEXT_LEVEL.get(
            want_lv, before_xp[1])), f'xp 恰 +3: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, 'evidence 通道级笔'
    finally:
        uninstall_backend()


def test_ge_seven_units_zero_write(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """姊妹席不足零写(锁 3 反向):7 单位 → 谓词失败窗推进零 xp 写。"""
    b = _setup()
    try:
        gs = b.gs
        gs.write_logic(gs.active_strategies, [_CARD2],
                       produced_by='test-seed', evidence='t:card2',
                       sig=_SIG)
        gs.observe(gs.bench, _bench_view(7), evidence='t:seed:bench7',
                   sig=_SIG_OBS)
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '席 <8 窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()
