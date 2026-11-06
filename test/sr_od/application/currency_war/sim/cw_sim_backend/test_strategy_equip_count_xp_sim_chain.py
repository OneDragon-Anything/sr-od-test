"""sim 策略卡装备计数经验节点窗腿测试(镜像 src = sim/cw_sim_backend.py
的 _begin_node_window 装备计数 XP 腿 + kernel 纯判定
check_strategy_equip_count_xp 的 sim 调用点世界写;kernel 原语单元面 =
kernel/cw_gain_chain/test_check_strategy_equip_count_xp.py,本文件锁
sim 窗口接入调用与世界真值落地面;先例 = 同目录
test_strategy_bench_count_xp_sim_chain.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-272-zanmei-
taiyang.md(定稿)§4 + §2.1(卡面官方原文:「每拥有一件【白昼装备】以及
其原型装备，在进入新节点时就获得1点经验。」):

- sim 世界锁:持卡 + 白昼系持有局节点窗推进 → gs.xp/gs.level 按
  xp_apply_amount 结转(含跨级结转算例),evidence ``xp:equip_count``
  独立笔 + sig 组 'sim:xp' 断言;零持有/未持卡零写;
- 幂等锁:同节点窗重放(_window_begun_pos 守卫整段早退)零新增写行;
  连续两个满足节点各发一次(零 done 一次性标志位可重复性);
- 拿卡当节点不发锁(结构性):选卡落地所在节点窗(P1r1)前置段已跑过,
  本卡后补零发放(发放起点 = 下一节点窗)。

驱动形态 = _enter_node_window 直通点(锚定补推路径真形态);引擎驱动助手
import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只 import
复用不改;族先例同上)。sim 世界零羁绊不产白昼件——持有面经观察通道
直构(观察→观察覆盖静默,族先例同法);原型件 = sim 结构性可达面
(进阶合成),白昼件直构等价计件,计数器不区分来源。
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

_CARD = '赞美太阳'

_PICK_SEED = 20261103

_XP_EV = 'sim:engine:xp:equip_count'

#: 原型代表件×2(白昼系名集成员,sim 可达面代表;计数器按名集不区分
#: 白昼/原型两亚类)。
_HOLDING = ['光速螺旋桨', '武器大师']


def _setup(seed: int = 31, *, grant: bool = True,
           holding: list[str] | None = None):
    """装配后端至 P1r1 备战窗并按需种持有面(调用方负责 uninstall;驱动
    形态先例 = 同目录备战席计数 sim 链锁;观察→观察覆盖静默)。"""
    b = _backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    if grant:
        gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                             rng=random.Random(_PICK_SEED))
    if holding is not None:
        b.gs.observe(b.gs.equips, list(holding), evidence='t:seed:equips',
                     sig=_SIG_OBS)
    return b


def test_pick_window_structural_no_fire() -> None:
    """拿卡当节点不发(结构性):P1r1 窗前置段先于选卡落地跑过(窗守卫
    已记 (1,1)),后补拿卡+持有当窗零发放——经验笔 evidence 无
    equip_count(发放起点 = 下一节点窗)。"""
    b = _setup(holding=_HOLDING)
    try:
        assert b.gs.xp.value is not None, '前置:sim 开局经验种子已登记'
        assert b.gs.xp.evidence != _XP_EV, '拿卡当窗不应发放'
    finally:
        uninstall_backend()


def test_node_window_holding_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    """持有窗发放(主条):持卡 + 库存 2 件原型,进 (1,2) 窗 → xp 恰 +2
    按纯函数结转,evidence 独立笔 + sig 组 'sim:xp';本窗恰两笔 xp 域写
    (level+xp)。"""
    b = _setup(holding=_HOLDING)
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
        assert gs.xp.source == 'observation', '世界数值面 = 观察通道'
        assert gs.xp.evidence == _XP_EV, f'独立笔缺失: {gs.xp.evidence}'
        xp_calls = [c for c in calls if c[1] in ('level', 'xp')]
        assert [(c[1], c[2]) for c in xp_calls] == [
            ('level', _XP_EV), ('xp', _XP_EV)], \
            f'本窗 xp 域写恰两笔: {xp_calls}'
        assert all(c[3].family == 'obs' and c[3].group_id == 'sim:xp'
                   for c in xp_calls), 'sig 组 = sim:xp(apply_node_xp 同域)'
    finally:
        uninstall_backend()


def test_holding_carry_levelup(monkeypatch: pytest.MonkeyPatch) -> None:
    """跨级结转算例:门槛恰跨形态(3 级差 1 + 2 → 4 级余 1)——世界等级
    随经验真实推进(升级联动发牌概率的耦合面以此为底,调用点钉在商店全刷
    前的语义锚)。"""
    b = _setup(holding=_HOLDING)
    try:
        gs = b.gs
        gs.observe(gs.level, 3, evidence='t:seed:lv', sig=_SIG_OBS)
        gs.observe(gs.xp, (XP_TO_NEXT_LEVEL[3] - 1, XP_TO_NEXT_LEVEL[3]),
                   evidence='t:seed:xp', sig=_SIG_OBS)
        b._enter_node_window((1, 2))
        assert gs.level.value == 4, '升一级'
        assert gs.xp.value == (1, XP_TO_NEXT_LEVEL[4]), \
            f'跨级余量: {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '跨级笔 evidence 不变'
    finally:
        uninstall_backend()


def test_replay_guard_no_double_fire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """同节点窗重放守卫(幂等):_begin_node_window 二次进入
    (_window_begun_pos 整段早退)→ 零新增写行、xp 不双发。"""
    b = _setup(holding=_HOLDING)
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
    """连续两满足节点各发一次(可重复性):零 done 一次性标志位的结构差异锁(与
    首购经验 at-most-once 分道)——(1,2)/(1,3) 两窗各 +2。"""
    b = _setup(holding=_HOLDING)
    try:
        gs = b.gs
        b._enter_node_window((1, 2))
        first = gs.xp.value
        lv_after_first = int(gs.level.value)
        want_lv, want_cur = xp_apply_amount(lv_after_first, first[0], 2)
        b._enter_node_window((1, 3))
        assert gs.level.value == want_lv, '第二窗 +2 按结转式推进'
        assert gs.xp.value == (want_cur,
                               XP_TO_NEXT_LEVEL.get(want_lv, first[1])), \
            f'第二窗 +2 结转: {first} → {gs.xp.value}'
        assert gs.xp.evidence == _XP_EV, '第二窗独立笔'
    finally:
        uninstall_backend()


def test_no_card_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """未持卡零写(反向):持有已登记但不持卡 → 零发放(白名单表外禁从
    效果原文自动猜装的窗口面)。"""
    b = _setup(grant=False, holding=_HOLDING)
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


def test_zero_holding_zero_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """零持有零写(反向):持卡但白昼系零持有(开局库存种子无装备)→
    谓词件数 0,窗推进零 xp 写(动态计数不虚发——静态挂值形态的对照
    面本锁钉死)。"""
    b = _setup(holding=[])
    try:
        gs = b.gs
        xp0 = gs.xp.value
        calls = _record_all_writes(gs, monkeypatch)
        b._enter_node_window((1, 2))
        assert [c for c in calls if c[1] in ('level', 'xp')] == [], \
            '零持有窗零 xp 域写'
        assert gs.xp.value == xp0, 'xp 零增量'
    finally:
        uninstall_backend()
