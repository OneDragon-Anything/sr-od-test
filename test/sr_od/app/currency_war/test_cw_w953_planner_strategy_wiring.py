"""test_cw_w953_planner_strategy_wiring 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

import inspect
import sys as _w953_planner_strategy_wiring_sys

_w953_planner_strategy_wiring_sys.path.insert(0, 'src')
_w953_planner_strategy_wiring_sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from types import SimpleNamespace as _w953_planner_strategy_wiring_SimpleNamespace

from sr_od.application.currency_war.kernel.cw_events import (
    PlannerOption as _w953_planner_strategy_wiring_PlannerOption,
)
from sr_od.application.currency_war.kernel.cw_events import (
    decide_planner as _w953_planner_strategy_wiring_decide_planner,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _w953_planner_strategy_wiring_BenchChar,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _w953_planner_strategy_wiring_GameState,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_planner import (
    CwScreenPlanner,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live as _w953_planner_strategy_wiring_MandateV1Strategy,
)

_UPGRADE = _w953_planner_strategy_wiring_PlannerOption(idx=0, text='提升费用至4费,变为1星银狼')
_WEAKEN = _w953_planner_strategy_wiring_PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')


# ADR-0517 迁移批:旧死码核具现(_decide_prep_action_impl 桥)退役,
# 直用活策略核(下述测试全部消费 live 接口)。
_FlowStrategy = _w953_planner_strategy_wiring_MandateV1Strategy
def _session(target_comp) -> _w953_planner_strategy_wiring_SimpleNamespace:
    """最小 session stub:decide_planner 只读 state_of(session).target_comp
    (target_comp 已迁 MandateState;state_of 对 SimpleNamespace 桩惰性冷建)。"""
    s = _w953_planner_strategy_wiring_SimpleNamespace()
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of
    state_of(s).target_comp = target_comp
    return s


def test_planner_handler_routes_through_strategy_layer() -> None:
    """接线锁:策略层路径被走;kernel 直调仅在无 match 防御分支。

    锁的是「调用路径」不是分布数值;改接线形态时先重推语义再改锁
    (锁的存在性纪律)。"""
    src = inspect.getsource(CwScreenPlanner.handle)
    # ① 唯一入口 = 策略对象(DESIGN §3.4 规约1)
    assert '_match.strategy.decide_planner(' in src, \
        'handle 必须经 match.strategy.decide_planner(策略层唯一入口)'
    # ② kernel 纯函数直调只允许在 else(无 match 防御)分支:直调行位于
    #    else 块内(其前最近的控制行是 else:)。W953 批1 治的就是
    #    「有 match 也直调 kernel」→ 策略对象被绕过。
    lines = src.splitlines()
    direct = [i for i, ln in enumerate(lines)
              if 'decide_planner(options' in ln and 'strategy' not in ln]
    assert len(direct) == 1, f'kernel 直调应恰一处(防御分支),实得 {len(direct)}'
    _head = [ln for ln in lines[:direct[0]] if ln.strip() == 'else:']
    assert _head, 'kernel 直调必须位于无 match 防御(else)分支内'


def test_planner_strategy_delegates_kernel_bitwise() -> None:
    """零行为锁:策略对象实现与 kernel 纯函数同输入逐位一致(委托不变形)。"""
    st = _w953_planner_strategy_wiring_GameState(hp=80)
    st.bench = [_w953_planner_strategy_wiring_BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = _FlowStrategy()
    via_strategy = strat.decide_planner(opts, st, _session(None), _w953_planner_strategy_wiring_SimpleNamespace())
    via_kernel = _w953_planner_strategy_wiring_decide_planner(opts, st, None)
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)


def test_planner_strategy_uses_session_target_comp() -> None:
    """零行为锁:策略对象把 state_of(session).target_comp 喂给 kernel 判定(银狼线加成),
    与旧 handler 直传 target_comp 的行为一致(接线不丢参)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = _w953_planner_strategy_wiring_GameState(hp=80)
    st.bench = [_w953_planner_strategy_wiring_BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = _FlowStrategy()
    via_strategy = strat.decide_planner(opts, st, _session(tgt), _w953_planner_strategy_wiring_SimpleNamespace())
    via_kernel = _w953_planner_strategy_wiring_decide_planner(opts, st, tgt)
    assert via_strategy.idx == 0 and '升费' in via_strategy.reason
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)
