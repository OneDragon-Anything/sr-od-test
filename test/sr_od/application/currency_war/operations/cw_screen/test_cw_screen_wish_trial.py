"""祈愿试炼画面 op 决策出口守卫测试(CwScreenWishTrial.act;守卫登记 =
docs/develop/sr_od/application/currency_war/screens/wish_trial.md §8,族规 =
screens/op-layer.md §1.1 出口③ / §1.3;同构样板 = test_cw_screen_yinlang)。

锁的故障形态:候选数为 0(obs 载体缺席 / 读链产空)时进策略器——策略器
对空候选回落 idx=0,放进去 = 盲选派发;修前形态 = 越界断言(非具名 fail,
且策略器已被盲选调用一次)。守卫序 = 选卡族规:① 候选空 → 具名 round_fail
(调策略器前);② 策略返回词表外/None → 具名 round_fail;③ idx 越界 →
AssertionError(禁钳位)——三守卫均在派发前、零点击。

边界(防守卫①误伤):OCR 空桶(候选文本为空串)≠ 候选空——空桶照持仍是
合法候选,合法 pick 照常派发。

演法 = 直调决策动作 node 方法:观察 node 产物 ``op._obs`` 由测试装配
(节点方法不替换——替换 @operation_node 方法会丢节点元数据);派发接缝 =
``cw_action_registry.action_op_for`` 模块级名字(act 内函数级 import,
monkeypatch 承接并计数);策略器桩记录调用次数(锁「候选空不进策略器」)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import fast_sleep

from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
    CwScreenWishTrialObs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickWishTrialParam,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_wish_trial import (
    CwScreenWishTrial,
)

_REGISTRY: str = ('sr_od.application.currency_war.operations.cw_op.'
                  'cw_action_registry')
_OPT_A: str = '累计刷新10次'
_OPT_B: str = '获得20金币'
_OPT_C: str = '进行一场难度3+遭遇节点战斗'


def _attach(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
            options: list[str], pick: object,
            ) -> tuple[CwScreenWishTrial, list[tuple[object, object]],
                       list[int]]:
    """装配 op 与假局:观察产物直挂 ``op._obs``(坐标域与名字域同序等长),
    策略器回 ``pick`` 并记录调用,派发工厂换成计数桩(记录 (param, env),
    execute 空转)。"""
    op = CwScreenWishTrial(test_context)
    op._obs = CwScreenWishTrialObs(
        on_screen=True, options=list(options),
        option_points=[(660, 340)] * len(options))
    strategy_calls: list[int] = []
    match = SimpleNamespace(strategy=SimpleNamespace(
        decide_wish_trial=lambda: (strategy_calls.append(1), pick)[1]))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    dispatched: list[tuple[object, object]] = []
    stub = SimpleNamespace(execute=lambda: None)
    monkeypatch.setattr(
        f'{_REGISTRY}.action_op_for',
        lambda param, ctx, env: (dispatched.append((param, env)), stub)[1])
    return op, dispatched, strategy_calls


def test_empty_options_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """守卫①:候选空 → 具名 round_fail(状态含「候选空」)、零派发、
    策略器零调用(空候选不进策略器——进去 = 盲选派发)。"""
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, [], CwActionPickWishTrialParam(idx=0))

    result = op.act()

    assert result.is_fail, f'候选空应 fail 交外环,实际 {result.status!r}'
    assert '候选空' in (result.status or ''), result.status
    assert strategy_calls == [], f'候选空不应进策略器,实际调用 {len(strategy_calls)} 次'
    assert dispatched == [], f'候选空应零派发,实际 {dispatched}'


@pytest.mark.parametrize('bad', [None, SimpleNamespace(idx=0)])
def test_non_contract_return_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        bad: object) -> None:
    """守卫②:decide_wish_trial 返回 None / 词表外类型(非动作类型对象)→
    具名 round_fail 含原值 repr、零派发。"""
    op, dispatched, _ = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B], bad)

    result = op.act()

    assert result.is_fail, f'词表外/None 应 fail,实际 {result.status!r}'
    assert '词表外/None' in (result.status or ''), result.status
    assert repr(bad) in (result.status or ''), result.status
    assert dispatched == [], f'词表外/None 应零派发,实际 {dispatched}'


@pytest.mark.parametrize('idx', [3, -1])
def test_idx_out_of_range_asserts_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        idx: int) -> None:
    """守卫③:idx 越界(上界外 / 负值)→ AssertionError(禁钳位)、零派发。"""
    op, dispatched, _ = _attach(
        test_context, monkeypatch, [_OPT_A, _OPT_B, _OPT_C],
        CwActionPickWishTrialParam(idx=idx))

    with pytest.raises(AssertionError, match='越界'):
        op.act()
    assert dispatched == [], f'越界应零派发,实际 {dispatched}'


def test_empty_bucket_text_still_dispatches(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """边界:OCR 空桶(候选文本空串)≠ 候选空——候选 ``['', '获得20金币', '']``
    合法 pick idx=1 → 守卫① 放行、恰派发一次(param = 策略产值原对象)、
    返回 round_wait 循环推进。"""
    pick = CwActionPickWishTrialParam(idx=1)
    op, dispatched, strategy_calls = _attach(
        test_context, monkeypatch, ['', _OPT_B, ''], pick)

    with fast_sleep():
        result = op.act()

    assert not result.is_fail, f'空桶候选合法 pick 不应 fail,实际 {result.status!r}'
    assert strategy_calls == [1], '合法候选应恰调策略器一次'
    assert len(dispatched) == 1, f'应恰派发一次,实际 {dispatched}'
    param, env = dispatched[0]
    assert param is pick, '派发 param 应 = 策略产值原对象(直发零重建)'
    assert env.op is op, '派发 env 应仅携 op(坐标由动作 op 自状态容器取)'
