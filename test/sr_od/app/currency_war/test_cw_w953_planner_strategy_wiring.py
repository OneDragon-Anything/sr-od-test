"""W953 批1:策划事件选卡接线锁 + 零行为对拍。

背景:handle_planner_event 原直调 kernel ``cw_events.decide_planner``(固定升费偏好),
``DecisionV2Strategy.decide_planner`` 成死码;批1 改走策略层唯一入口(只改调用路径,
决策逻辑仍委托同一 kernel 纯函数,局面感知升级归批4)。设计单一源 =
``.debug/temp/currency_war/w953_overlay_strategy/DESIGN.md`` §3.4 调用规约。

两把锁:
1. 接线锁:handle 源码必须经 ``match.strategy.decide_planner`` 走策略层;
   kernel 直调只允许出现在无 match 防御分支(局外独立跑)。
2. 零行为锁:同输入下 DecisionV2Strategy.decide_planner 与 kernel 纯函数逐位一致
   (idx + reason)——委托语义不被接线破坏。
"""
import inspect
import sys

sys.path.insert(0, 'src')
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from types import SimpleNamespace

from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_events import (
    PlannerOption,
    decide_planner,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.operations.handlers.handle_planner_event import (
    HandlePlannerEvent,
)

_UPGRADE = PlannerOption(idx=0, text='提升费用至4费,变为1星银狼')
_WEAKEN = PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')


def _session(target_comp) -> SimpleNamespace:
    """最小 session stub:decide_planner 只读 target_comp。"""
    return SimpleNamespace(target_comp=target_comp)


def test_planner_handler_routes_through_strategy_layer() -> None:
    """接线锁:策略层路径被走;kernel 直调仅在无 match 防御分支。

    锁的是「调用路径」不是分布数值;改接线形态时先重推语义再改锁
    (锁的存在性纪律)。"""
    src = inspect.getsource(HandlePlannerEvent.handle)
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
    st = GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = DecisionV2Strategy()
    via_strategy = strat.decide_planner(opts, st, _session(None), SimpleNamespace())
    via_kernel = decide_planner(opts, st, None)
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)


def test_planner_strategy_uses_session_target_comp() -> None:
    """零行为锁:策略对象把 session.target_comp 喂给 kernel 判定(银狼线加成),
    与旧 handler 直传 target_comp 的行为一致(接线不丢参)。"""
    from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
    tgt = next(c for c in COMP_LIBRARY if c.name == '狼尊欢愉')
    st = GameState(hp=80)
    st.bench = [BenchChar(slot=1, char_id='银狼LV.999', faction='?', star=2,
                          position_pref='front')]
    opts = [_UPGRADE, _WEAKEN]
    strat = DecisionV2Strategy()
    via_strategy = strat.decide_planner(opts, st, _session(tgt), SimpleNamespace())
    via_kernel = decide_planner(opts, st, tgt)
    assert via_strategy.idx == 0 and '升费' in via_strategy.reason
    assert (via_strategy.idx, via_strategy.reason) == (via_kernel.idx, via_kernel.reason)
