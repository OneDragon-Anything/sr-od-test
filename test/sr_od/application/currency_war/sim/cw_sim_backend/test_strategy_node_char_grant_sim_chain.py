"""sim 策略卡每节点绑定角色复制发放窗口腿测试(镜像 src = sim/
cw_sim_backend.py 的 _begin_node_window 复制发放腿 + kernel 获得效果体的
sim 门控绑定写;kernel 原语单元面 =
kernel/cw_gain_chain/test_check_strategy_node_char_grants.py,本文件锁
sim 窗口接线与世界真值落地面)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-165-jiazhi-touzi-jin.md(定稿)§4 锁 2(sim 世界形)/锁 5(补给后)/
锁 6(幂等):

- 获得时点(sim 装配)= 采样即世界真值:固定 rng → 备战 +1 名 2★ ∈
  1 费池 + 绑定域写入(sim 门控 True = 绑定即世界真值,复制发放腿
  判据落账);
- 每节点窗(进窗事实点在窗口幂等守卫内):+1 名 1★ 绑定同名;同节点
  窗重放(_window_begun_pos 守卫整段早退)零新增写行不双发;
- 补给后继窗(同位面 P1r5→P1r6):+3 名(1+2=3,「补给后」文义直读);
  批内同名凑三升星级联沿链现役(副本质量守恒断言:3^(星级-1) 求和
  对合并不变量,发放名数线性)。

驱动形态 = _enter_node_window 直通点 / _drive_until 引擎步进(锚定补推
路径真形态);引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_strategy_delayed_grant_sim_chain.py)。
"""
from __future__ import annotations

import random

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _backend,
    _drive_until,
    _record_all_writes,
)

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    bench_units_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RandomCharSpec,
    random_char_pool,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

_CARD = '价值投资·金'

_PICK_SEED = 200401


def _bound_name() -> str:
    """期望绑定名(与效果体同 rng 消费序:采样恰 1 次先掷)。"""
    return random.Random(_PICK_SEED).choice(
        random_char_pool(RandomCharSpec(cost=1, star=2)))


def _copy_mass(gs, name: str) -> int:
    """绑定名副本质量(3^(星级-1) 求和,备战 ∪ 上阵 ∪ 溢出;升星合并
    不变量下的发放量线性读数)。溢出位身份 = 角色名直读(角色两分)。"""
    mass = sum(3 ** (u.star - 1) for u in bench_units_of(gs)
               if u.char_id == name)
    ovf = str(gs.overflow_card.value or '')
    if ovf == name:
        mass += 1
    return mass


@pytest.fixture
def _prep_backend():
    """装配后端至 P1r1 备战窗 + 持卡获得(sim 世界:绑定即真值;调用方
    负责 uninstall;驱动形态先例 = 同目录
    test_strategy_delayed_grant_sim_chain)。"""
    from sr_od.application.currency_war.sim.cw_sim_backend import (
        SCREEN_BRIEFING,
    )
    b = _backend(31)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    gain_invest_strategy(b.gs, None, _CARD, rand=False, sig=_SIG,
                         rng=random.Random(_PICK_SEED))
    yield b
    uninstall_backend()


def test_pick_writes_binding_world_truth(_prep_backend) -> None:
    """获得时点 sim 世界形(锁 2 链面):绑定域 = {卡名: 采样名} + 备战
    +1 名 2★ ∈ 1 费池(采样即世界真值;live 零写形态归 kernel 锁文件)。"""
    b = _prep_backend
    gs = b.gs
    expected = _bound_name()
    assert gs.strategy_char_grant_bindings.value == {_CARD: expected}, \
        'sim 门控绑定写 = 世界真值'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert (expected, 2) in units, f'备战含 1 名 2★ 采样名: {units}'


def test_node_window_grant_and_replay_guard(
        _prep_backend, monkeypatch: pytest.MonkeyPatch) -> None:
    """每节点窗发放(锁 4 sim 链面)+ 窗重放守卫(锁 6 幂等):进 (1,2)
    窗 → +1 名 1★ 绑定同名;同节点窗重放(_begin_node_window 二次进入,
    _window_begun_pos 守卫整段早退)→ 零新增写行、副本质量不双发。"""
    b = _prep_backend
    gs = b.gs
    name = _bound_name()
    mass0 = _copy_mass(gs, name)
    assert mass0 == 3, '前置:获得腿 1 名 2★ = 3 份副本质量'
    b._enter_node_window((1, 2))
    assert _copy_mass(gs, name) == mass0 + 1, '窗内 +1 名 1★(基础发放)'
    calls = _record_all_writes(gs, monkeypatch)
    b._begin_node_window()   # 同节点窗重放(直构)
    assert calls == [], '窗重放出现新增写行'
    assert _copy_mass(gs, name) == mass0 + 1, '窗重放双发'


def test_supply_successor_window_grants_three(_prep_backend) -> None:
    """补给后继窗(锁 5 sim 链面):P1r5 补给 → P1r6 窗 +3 名(同位面
    「前一进入节点为补给」形态,现役日程);累计副本质量 = 获得 2★(3)
    + r2..r5 基础(4)+ r6 补给后继(3)= 10(升星合并不变量下线性)。"""
    b = _prep_backend
    gs = b.gs
    name = _bound_name()
    _drive_until(b, lambda: b._node_pos() == (1, 6))
    assert _copy_mass(gs, name) == 3 + 4 + 3, \
        f'累计副本质量(获得+四基础窗+补给后继): {_copy_mass(gs, name)}'
    assert b._node_pos() == (1, 6), '前置:驱动至 P1r6(battle)'
