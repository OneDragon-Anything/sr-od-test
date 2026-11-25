"""MandateV1Strategy.decide_synthesis_overlay:合成确认浮层处置。

锁的设计约定:
- 浮层在场(状态容器字段是读数结构):返回确认动作,坐标 = 字段里的 ✓ 中心。
  框架直接确认,不看两件原料与产物预览(合成是已经发起的动作,浮层只是收尾)。
  入口不依赖帧的新旧标记——裸状态容器上照样可用;
- 字段不是读数结构时被调用 = 观察层失约(画面 op 只在本次访问观察到浮层时才调
  这个入口),显式抛 AssertionError,不猜坐标。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_decision_ctx import (
    reset_decision_tag,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSynthesisConfirmParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)

_OVERLAY = {
    'ok_xy': (1821, 402),
    'cancel_xy': (1707, 402),
    'panel_rect': [1597, 299, 1872, 436],
    'inputs': [
        {'name': '轮滑鞋', 'conf': 0.901, 'cx': 1632, 'cy': 328},
        {'name': '折叠小刀', 'conf': 0.867, 'cx': 1731, 'cy': 328},
    ],
    'product': {'name': '火力风暴潮', 'conf': 0.636, 'cx': 1838, 'cy': 325},
}


def _strategy_with(value: object) -> MandateV1Strategy:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if value is not None:
        gs.observe(gs.synthesis_overlay, value,
                   sig=ChannelSig(family='obs', actor='test'))
    return MandateV1Strategy(gs, SimpleNamespace())  # type: ignore[arg-type]


def test_decide_synthesis_overlay_confirms_at_field_point() -> None:
    """浮层在场:返回确认动作,坐标取字段里的 ✓ 中心(不看合成内容)。"""
    reset_decision_tag()
    try:
        action = _strategy_with(_OVERLAY).decide_synthesis_overlay()

        assert isinstance(action, CwActionSynthesisConfirmParam)
        assert (action.cx, action.cy) == _OVERLAY['ok_xy']
    finally:
        reset_decision_tag()


@pytest.mark.parametrize('value', ['none', None], ids=['确认无浮层', '从未观察'])
def test_decide_synthesis_overlay_without_overlay_is_observation_fault(value: object) -> None:
    """字段不是读数结构时被调用 = 观察层失约:显式抛错,不猜坐标。"""
    with pytest.raises(AssertionError, match='观察层失约'):
        _strategy_with(value).decide_synthesis_overlay()
