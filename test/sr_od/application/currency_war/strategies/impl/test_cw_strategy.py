"""CwStrategy 决策入口闭集:合成确认浮层处置入口的登记。

锁的设计约定(出处 = 开发 skill flow/strategy-contract.md「决策入口清单」):
- 合成确认浮层处置是基类的抽象入口,并且在决策记录闭集里。闭集决定记录包裹
  挂不挂在入口上——现役策略器调一次,这次决策的标记就写进了回执要读的槽
  (标记缺失 = 复盘里这个入口的动作没有决策依据)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_decision_ctx import (
    reset_decision_tag,
    take_decision_tag,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    DECISION_ENTRY_NAMES,
    CwStrategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)


def test_synthesis_overlay_entry_gets_decision_tag() -> None:
    """合成确认浮层处置入口:基类上是抽象入口、在决策记录闭集里;现役策略器
    调用一次,回执要读的槽里留下这次决策的标记(记录包裹对它生效)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(
        gs.synthesis_overlay,
        {'ok_xy': (1821, 325), 'cancel_xy': (1707, 325)},
        sig=ChannelSig(family='obs', actor='test'),
    )
    strategy = MandateV1Strategy(gs, SimpleNamespace())  # type: ignore[arg-type]
    reset_decision_tag()
    try:
        strategy.decide_synthesis_overlay()

        assert getattr(CwStrategy.decide_synthesis_overlay, '__isabstractmethod__', False)
        assert 'decide_synthesis_overlay' in DECISION_ENTRY_NAMES
        assert take_decision_tag() == f'{MandateV1Strategy.STRATEGY_ID}:1'
    finally:
        reset_decision_tag()
