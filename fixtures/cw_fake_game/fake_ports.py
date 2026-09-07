"""假游戏的两端口实现(T-120 批 0;方案 §2.3/§2.4 的 fake 侧)。

``FakeCwObserver``/``FakeActionSink`` 结构化满足
``sr_od.application.currency_war.cw_game_ports`` 的两个 Protocol
(conform 锁 = test_cw_game_ports.py)。真值来源 = ``FakeMatch`` 状态机
直出;本文件零识别逻辑、零平行真值——观察即状态快照,动作即状态转移。
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from fixtures.cw_fake_game.fake_match import PHASE_PREP_SHOP_OPEN, FakeMatch
from sr_od.application.currency_war.cw_game_ports import (
    ExecResult,
    ObservationBundle,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_state import (
    Action,
    GameState,
    ShopCard,
)

if TYPE_CHECKING:
    from sr_od.context.sr_context import SrContext


class FakeCwObserver:
    """观察源端口假实现:状态机真值直出(方案 §2.3 表「假游戏实现」列)。

    每次调用经 ``FakeMatch.record_observation`` 留痕——读屏次数语义保留
    (方案 §2.3 契约二则:注入换掉的是读图,不是观察这个语义事件)。
    """

    def __init__(self, match: FakeMatch) -> None:
        self._match: FakeMatch = match

    def screen_identity(self, ctx: SrContext) -> str:
        """画面档名 = 状态机 ``phase`` 直出(方案 §2.3 表)。"""
        self._match.record_observation('screen_identity', None)
        return self._match.phase

    def observe_prep(self, ctx: SrContext, phase: str) -> ObservationBundle:
        """入口观察:状态真值快照直填(方案 §2.3 表「保真位恒真」)。"""
        self._match.record_observation('observe_prep', phase)
        st = self._snapshot_state()
        # 契约一则:保真位恒真 = 「完美观测」环境参数(方案 §2.3;
        # sim-wiring 三节「完美观测=终态」既有豁免口径),判读按方案
        # §4-6 申报「执行/识别缺陷面结构性为零」,识别质量归实机遥测
        st.hp_readable = True
        st.hp_trusted = True
        st.gold_readable = True
        st.board_readable = True
        st.level_readable = True
        prep = PrepObservation(
            state=st,
            # state_gold_trusted 语义 = heavy 时 shop 开(PrepObservation
            # 字段注);假环境 gold 恒真读
            state_gold_trusted=True,
            shop_open=(self._match.phase == PHASE_PREP_SHOP_OPEN),
        )
        return ObservationBundle(state=st, prep=prep)

    def observe_shop_cards(self, ctx: SrContext) -> list[ShopCard]:
        """店面卡牌 = 状态机 shop 槽直出(快照拷贝,断对象别名)。"""
        self._match.record_observation('observe_shop_cards', None)
        return [replace(c) for c in self._match.state.shop]

    def overlay_options(self, ctx: SrContext, kind: str) -> list[Any]:
        """浮层选项 = 栈顶匹配浮层载荷直出(空栈/无匹配 = 空,非 None——
        「无浮层」与「浮层无选项」在假环境同义,消费方按空列表分流)。"""
        self._match.record_observation('overlay_options', kind)
        frame = self._match.top_overlay(kind)
        return list(frame.payload) if frame is not None else []

    def _snapshot_state(self) -> GameState:
        """状态快照:deepcopy 断别名(ADR-0465 §9 快照拷贝语义同源)——
        观察帧改动不得污染状态机真值(观察是快照,动作才转移)。"""
        return self._match.state.copy()


class FakeActionSink:
    """执行器端口假实现:动作落假游戏状态机(方案 §2.4)。

    直接委托 ``FakeMatch.apply``——ExecResult 的 applied/income/
    verification/observed 全部由状态机按真值填;本类零执行逻辑。
    """

    def __init__(self, match: FakeMatch) -> None:
        self._match: FakeMatch = match

    def execute_action(self, ctx: SrContext, action: Action) -> ExecResult:
        """执行动作 = 状态机转移(失败面结构性为零,方案 §2.4 边界申报)。"""
        return self._match.apply(action)
