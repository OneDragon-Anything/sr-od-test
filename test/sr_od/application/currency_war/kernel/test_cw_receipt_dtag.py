"""动作回执 dtag 关联契约锁面(镜像 src = kernel/cw_game_state.py 的
``note_action_receipt`` 读侧;同 src 兄弟测试 = kernel/test_cw_game_state.py
回放守恒主题 / kernel/test_game_state.py 状态容器机制主题,主题不同不混写)。

被测契约 = changes/2026-10-24-strategy-telemetry/details/capture-store.md §2
(dtag 进回执 = kernel 决策上下文槽,单写单读 take 读后清;四调用点零改动)
+ landing §3.2 完成判据(同帧信封同值 / 受阻回执同带 / 重试链多回执各带
各值 / 跨测试残留归 conftest 复位面——后者锁在 test_cw_decision_ctx.py)。
信封侧经 T-2 捕获缝(内存假 sink)装配;测试零真实副作用。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_decision_ctx import (
    reset_decision_tag,
    take_decision_tag,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
    note_action_receipt,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwAction,
    CwActionPickPartnerParam,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CwStrategy,
    set_decision_sink,
)


def _probe_action() -> CwActionPickPartnerParam:
    """探针动作(带归因字段;非空动作形态 = wrapper 盖槽分支)。"""
    return CwActionPickPartnerParam(idx=0, reason='probe', route_tag='probe_tag')


class _ReceiptProbeStrategy(CwStrategy):
    """最小具现探针:14 入口全部返回同一探针动作(空动作清槽分支已由
    test_cw_strategy.py 锁定,此处不复写);包裹面在类创建时挂上。"""

    STRATEGY_ID = 'probe'

    def decide_prep_screen(self) -> CwAction:
        return _probe_action()

    def decide_shop_action(self) -> CwAction:
        return _probe_action()

    def decide_invest_strategy(self) -> CwAction:
        return _probe_action()

    def decide_invest_env(self) -> CwAction:
        return _probe_action()

    def decide_supply(self) -> CwAction:
        return _probe_action()

    def decide_encounter(self) -> CwAction:
        return _probe_action()

    def decide_megastar(self) -> CwAction:
        return _probe_action()

    def decide_partner(self) -> CwAction:
        return _probe_action()

    def decide_planner(self) -> CwAction:
        return _probe_action()

    def decide_star_tome(self) -> CwAction:
        return _probe_action()

    def decide_wish_trial(self) -> CwAction:
        return _probe_action()

    def decide_box_card(self) -> CwAction:
        return _probe_action()

    def decide_fortune(self) -> CwAction:
        return _probe_action()

    def decide_expert_invite(self) -> CwAction:
        return _probe_action()


def _make() -> _ReceiptProbeStrategy:
    return _ReceiptProbeStrategy(
        GameState(schema_version=GAME_STATE_SCHEMA_VERSION),
        SimpleNamespace(strategy_seed=None))


@pytest.fixture
def capture_sink() -> list[dict]:
    """内存假 sink(T-2 捕获缝同款装配;teardown 摘 sink + 清决策上下文槽)。"""
    records: list[dict] = []
    set_decision_sink(records.append)
    yield records
    set_decision_sink(None)
    reset_decision_tag()


def test_receipt_carries_dtag_matching_envelope(capture_sink) -> None:
    """判据①:回执行含 dtag 且与同帧信封 dtag 同值;take 读后清——
    合并后槽空,同一 dtag 不搭后续无关回执。"""
    strat = _make()
    strat.decide_partner()
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    note_action_receipt(gs, op='CwActionPickPartnerParam',
                        actor='TestProbeOp')
    rec = gs.receipts.value[0]
    assert rec['dtag'] == capture_sink[0]['envelope']['dtag'] == 'probe:1'
    assert take_decision_tag() is None


def test_blocked_receipt_also_carries_dtag(capture_sink) -> None:
    """判据②:受阻回执(reason 非空受阻码)同形态带 dtag——dtag 并入
    与 reason 正交,未发出行照带决策帧锚。"""
    strat = _make()
    strat.decide_shop_action()
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    note_action_receipt(gs, op='CwActionBuyCardParam',
                        reason='未执行:无简易武装箱', actor='TestProbeOp')
    rec = gs.receipts.value[0]
    assert rec['reason'] == '未执行:无简易武装箱'
    assert rec['dtag'] == capture_sink[0]['envelope']['dtag']


def test_retry_chain_each_receipt_own_dtag(capture_sink) -> None:
    """判据③:重试链一节多回执各带各自 dtag(逐帧盖新 + take 读后清
    防跨帧串号);槽空回执(无前置决策帧)零 dtag 键——shape 对存量
    消费者(精确 shape 断言)零新增键。"""
    strat = _make()
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    for _ in range(2):
        strat.decide_partner()
        note_action_receipt(gs, op='CwActionPickPartnerParam',
                            actor='TestProbeOp')
    recs = gs.receipts.value
    assert [r['dtag'] for r in recs] == ['probe:1', 'probe:2']
    assert recs[0]['dtag'] != recs[1]['dtag']
    note_action_receipt(gs, op='CwOpOpenShop', actor='TestProbeOp')
    assert 'dtag' not in gs.receipts.value[-1]
