"""sim 策略卡空仓经验节点窗效果条目测试(镜像 src = sim/cw_sim_backend.py 的
_begin_node_window 空仓 XP 效果条目 + kernel 纯判定 check_strategy_empty_equip_xp
的 sim 调用点状态副本写;kernel 原语单元面 =
kernel/cw_gain_chain/test_check_strategy_empty_equip_xp.py,本文件锁
sim 窗口接入调用与状态副本里的值落地面)。

测试面依据 = 设计稿(原件已退役) designs/
设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 4/5/6/7 + 已退役评审稿(§ 号 = 原稿节序)§五④:
- sim 状态副本锁(锁 4):持卡空仓局节点窗推进 → gs.xp/gs.level 按
  xp_apply_amount 结转(含跨级结转算例),evidence ``xp:empty_slot``
  独立笔 + sig 组 'sim:xp' 断言;非空仓零写;未持卡零写;
- 幂等锁(锁 5):同节点窗重放(_window_begun_pos 守卫整段早退)零新增
  写行;连续两个空仓节点各发一次(可重复性——与孪生素数 at-most-once
  的结构差异锁);
- 拿卡当节点不发锁(锁 6):选卡落地所在节点窗(P1r1)前置段已跑过,
  本卡后补零发放(发放起点 = 下一节点窗)。

驱动形态 = _enter_node_window 直通点(锚定补推路径真形态);引擎驱动助手
import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只 import
复用不改;先例 = 同目录 test_strategy_node_char_grant_sim_chain.py)。
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
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    uninstall_backend,
)

_CARD = '空仓'

_PICK_SEED = 20261103

_XP_EV = 'sim:engine:xp:empty_slot'


def _setup(seed: int = 31, *, grant: bool = True,
           clear_equips: bool = True):
    """装配后端至 P1r1 备战窗(调用方负责 uninstall;驱动形态先例 = 同目录
    test_strategy_node_char_grant_sim_chain)。

    grant=True → 拿卡(P1r1 窗已开,选卡拍结构性晚于窗前置段);效果条目1 随卡
    采样 1 件简易入栏,clear_equips=True → 观察通道清空物品栏(模拟该件
    已售出/耗用后的状态副本态——条件谓词恢复成立;观察→观察覆盖静默,
    test_env_xp_window_sim_chain 等级种子同写入口先例)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    if grant:
        gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                             rng=random.Random(_PICK_SEED))
        if clear_equips:
            b.gs.observe(b.gs.equips, [], evidence='t:seed:sold',
                         sig=_SIG_OBS)
    return b


def test_pick_window_structural_no_fire() -> None:
    """拿卡当节点不发(锁 6,结构性):P1r1 窗前置段先于选卡落地跑过
    (窗守卫已记 (1,1)),后补拿卡当窗零发放——经验笔 evidence 无
    empty_slot(发放起点 = 下一节点窗)。"""
    b = _setup()
    try:
        xp = b.gs.xp.value
        assert xp is not None, '前置:sim 开局经验种子已登记'
        assert b.gs.xp.evidence != _XP_EV, '拿卡当窗不应发放'
    finally:
        uninstall_backend()


def test_node_window_empty_deck_grants_two(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """双空窗发放(锁 4 主条):进 (1,2) 窗 → xp 恰 +2 按纯函数结转,
    evidence 独立笔 + sig 组 'sim:xp';本窗恰两笔 xp 域写(level+xp)。"""
    b = _setup()
    try:
        gs = b.gs
        before_lv = int(gs.level.value)
        before_xp = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        want_lv, want_cur = xp_apply_amount(before_lv, int(before_xp[0]), 2)
        assert gs.level.value == want_lv, 'level 按结转式推进'
        assert gs.xp.value == (want_cur, XP_TO_NEXT_LEVEL.get(
            want_lv, before_xp[1])), f'xp 恰 +2: {gs.xp.value}'
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
    """跨级结转算例(锁 4):门槛恰跨形态(3 级余 2 + 2 → 4 级余 0)——
    状态副本等级随白送经验真实推进(升级联动发牌概率的耦合面以此为底)。"""
    b = _setup()
    try:
        gs = b.gs
        gs.observe(gs.level, 3, evidence='t:seed:lv', sig=_SIG_OBS)
        gs.observe(gs.xp, (XP_TO_NEXT_LEVEL[3] - 2, XP_TO_NEXT_LEVEL[3]),
                   evidence='t:seed:xp', sig=_SIG_OBS)
        b._enter_node_window((1, 2))
        assert gs.level.value == 4, '升一级'
        assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[4]), \
            f'余量 4−2+2−4=0: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '跨级笔 evidence 不变'
    finally:
        uninstall_backend()


def test_replay_guard_no_double_fire(monkeypatch: pytest.MonkeyPatch) -> None:
    """同节点窗重放守卫(锁 5 幂等):_begin_node_window 二次进入
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


def test_consecutive_empty_windows_each_fire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """连续两空仓节点各发一次(锁 5 可重复性):零 done 一次性标志位的结构差异锁
    (与孪生素数 at-most-once 分道)——(1,2)/(1,3) 两窗各 +2(第二窗
    恰跨 3 级门槛 = 跨级结转形态,按纯函数期望对拍)。"""
    b = _setup()
    try:
        gs = b.gs
        b._enter_node_window((1, 2))
        first = gs.xp.value
        lv_after_first = int(gs.level.value)
        want_lv, want_cur = xp_apply_amount(lv_after_first, first[0], 2)
        b._enter_node_window((1, 3))
        assert gs.level.value == want_lv, '第二窗 +2 按 3 级门槛 4 恰跨升级'
        assert gs.xp.value == (want_cur,
                               XP_TO_NEXT_LEVEL.get(want_lv, first[1])), \
            f'第二窗 +2 结转: {first} → {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '第二窗独立笔'
    finally:
        uninstall_backend()


def test_non_empty_deck_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """非空仓零写(锁 4 反向):效果条目1 采样的简易件在栏(非消耗品)→ 谓词
    失败,窗推进零 xp 写(结构性自洽:拿卡即破空仓)。"""
    b = _setup(grant=True, clear_equips=False)
    try:
        gs = b.gs
        assert gs.equips.value, '前置:效果条目1 采样件在栏'
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '非空仓窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()


def test_no_card_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """未持卡零写(锁 4 反向):空仓状态但不持卡 → 零发放(白名单表外
    禁从效果原文自动猜装的窗口面)。"""
    b = _setup(grant=False)
    try:
        gs = b.gs
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '未持卡窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()
