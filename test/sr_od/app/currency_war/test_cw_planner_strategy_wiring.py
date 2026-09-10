"""test_cw_planner_strategy_wiring 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_strategy_planner.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_events import (
    PlannerOption,
    decide_planner,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.operations.cw_screen.cw_screen_planner import (
    CwScreenPlanner,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import MandateV1Live

_UPGRADE = PlannerOption(idx=0, text='提升费用至4费,变为1星银狼')
_WEAKEN = PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')


def _session(target_comp) -> SimpleNamespace:
    """最小 session stub:decide_planner 只读 state_of(session).target_comp
    (target_comp 已迁 MandateState;state_of 对 SimpleNamespace 桩惰性冷建)。"""
    s = SimpleNamespace()
    state_of(s).target_comp = target_comp
    return s


def _planner_state() -> GameState:
    """备战态:bench 持有银狼(在场判定保守,不触发降权分支)。"""
    st = GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    return st


def test_planner_handler_routes_through_strategy_layer() -> None:
    """接线锁:策略层路径被走;kernel 直调仅在无 match 防御分支。

    锁的是「调用路径」不是分布数值;改接线形态时先重推语义再改锁
    (锁的存在性纪律)。
    锁面随试点步骤 3 迁移(handle 体纯移入 ``_handle_overlay`` 共享体,
    两路径共用零转录;统一观察架构 B3 三段走第二段,验收
    reviews/T-215-r1.md 先例)自 handle 改指共享体——接线语义零改动,
    仅断言面跟随代码移动。"""
    src = inspect.getsource(CwScreenPlanner._handle_overlay)
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
    """零行为锁:策略对象与 kernel 纯函数同输入逐位一致(委托不变形),
    target_comp 经 state_of(session) 透传(接线不丢参)。

    ADR-0517 迁移批:旧死码核具现(_decide_prep_action_impl 桥)退役,
    本测直用活策略核(MandateV1Live 接口)。

    两面:①target 缺省(None)——state_of 冷建默认 None 原样透传,
    禁注入替身阵容;②target=狼尊欢愉——银狼线加成(+30/+银狼线)真实
    流入,与旧 handler 直传 target_comp 行为一致,防委托退化成丢参直调。
    """
    opts = [_UPGRADE, _WEAKEN]
    strat = MandateV1Live()
    # ① 无 target
    via_strategy = strat.decide_planner(
        opts, _planner_state(), _session(None), SimpleNamespace())
    via_kernel = decide_planner(opts, _planner_state(), None)
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)
    # ② target 在案(银狼线加成经 session 透传生效)
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    via_strategy = strat.decide_planner(
        opts, _planner_state(), _session(tgt), SimpleNamespace())
    via_kernel = decide_planner(opts, _planner_state(), tgt)
    assert via_strategy.idx == 0 and '升费' in via_strategy.reason
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)
