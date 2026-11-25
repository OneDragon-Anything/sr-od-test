"""银狼策划事件画面 op 决策出口守卫测试(CwScreenYinLang.act;守卫登记 =
docs/develop/sr_od/application/currency_war/screens/planner.md §8,族规 =
screens/op-layer.md §1.1 出口③ / §1.3)。

锁的故障形态:sim 局呈现策划事件模态而候选槽为空时,决策动作 node 对
``options[pick.idx]`` 无守卫 → IndexError 被外循环吞成连续 fail → 退局
(具名 fail 零派发才应是出口)。守卫序 = 选卡族规:① 候选空 → 具名
round_fail;② 策略返回词表外/None → 具名 round_fail;③ idx 越界 →
AssertionError(禁钳位)——三守卫均在取点与派发前、零点击。

演法 = 直调决策动作 node 方法:观察 node 产物 ``op._obs`` 由测试装配
(节点方法不替换——替换 @operation_node 方法会丢节点元数据);派发接缝 =
``cw_action_registry.action_op_for`` 模块级名字(act 内函数级 import,
monkeypatch 承接并计数)。
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext

from sr_od.application.currency_war.kernel.cw_events import (
    PLANNER_LEG_UPGRADE,
    PlannerOption,
    PlannerPick,
)
from sr_od.application.currency_war.kernel.cw_screen_report.planner import (
    CwScreenPlannerObs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickPlannerParam,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_yinlang,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_yinlang import (
    CwScreenYinLang,
)

_REGISTRY: str = ('sr_od.application.currency_war.operations.cw_op.'
                  'cw_action_registry')
_UPGRADE_TEXT: str = '提升费用至4费,变为1星银狼LV.999'
_OTHER_TEXT: str = '扑满病毒'


def _attach(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
            options: list[PlannerOption], pick: object,
            ) -> tuple[CwScreenYinLang, list[tuple[object, object]]]:
    """装配 op 与假局:观察产物直挂 ``op._obs``,策略器回 ``pick``,派发
    工厂换成计数桩(记录 (param, env),execute 空转)。"""
    op = CwScreenYinLang(test_context)
    op._obs = CwScreenPlannerObs(on_screen=True, options=list(options))
    match = SimpleNamespace(
        strategy=SimpleNamespace(decide_planner=lambda: pick))
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    dispatched: list[tuple[object, object]] = []
    stub = SimpleNamespace(execute=lambda: None)
    monkeypatch.setattr(
        f'{_REGISTRY}.action_op_for',
        lambda param, ctx, env: (dispatched.append((param, env)), stub)[1])
    return op, dispatched


def test_empty_options_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """守卫①:候选空 → 具名 round_fail(状态含「候选空」)、零派发。"""
    op, dispatched = _attach(test_context, monkeypatch, [],
                             CwActionPickPlannerParam(idx=0))

    result = op.act()

    assert result.is_fail, f'候选空应 fail 交外环,实际 {result.status!r}'
    assert '候选空' in (result.status or ''), result.status
    assert dispatched == [], f'候选空应零派发,实际 {dispatched}'


@pytest.mark.parametrize('bad', [None, PlannerPick(idx=0)])
def test_non_contract_return_named_fail_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        bad: object) -> None:
    """守卫②:decide_planner 返回 None / 词表外类型(kernel PlannerPick 非
    动作类型)→ 具名 round_fail 含原值 repr、零派发。"""
    options = [PlannerOption(idx=0, text=_UPGRADE_TEXT),
               PlannerOption(idx=1, text=_OTHER_TEXT)]
    op, dispatched = _attach(test_context, monkeypatch, options, bad)

    result = op.act()

    assert result.is_fail, f'词表外/None 应 fail,实际 {result.status!r}'
    assert '词表外/None' in (result.status or ''), result.status
    assert repr(bad) in (result.status or ''), result.status
    assert dispatched == [], f'词表外/None 应零派发,实际 {dispatched}'


@pytest.mark.parametrize('idx', [2, -1])
def test_idx_out_of_range_asserts_zero_dispatch(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        idx: int) -> None:
    """守卫③:idx 越界(上界外 / 负值)→ AssertionError(禁钳位)、零派发。"""
    options = [PlannerOption(idx=0, text=_UPGRADE_TEXT),
               PlannerOption(idx=1, text=_OTHER_TEXT)]
    op, dispatched = _attach(test_context, monkeypatch, options,
                             CwActionPickPlannerParam(idx=idx))

    with pytest.raises(AssertionError, match='越界'):
        op.act()
    assert dispatched == [], f'越界应零派发,实际 {dispatched}'


class _ListHandler(logging.Handler):
    """决策日志行采集器(框架 logger propagate=False,caplog 根处理器收不到)。"""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_valid_pick_dispatches_with_branch_and_logs_card_text(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """合法 pick(升费卡在右卡 idx=1)→ 右卡取点 → classify 出 upgrade →
    派发一次(param = 策略产值原对象;env.branch_type='upgrade'、target =
    右卡 area 推导点);决策日志行含所选卡文案。"""
    options = [PlannerOption(idx=0, text=_OTHER_TEXT),
               PlannerOption(idx=1, text=_UPGRADE_TEXT)]
    pick = CwActionPickPlannerParam(idx=1, reason='升费')
    op, dispatched = _attach(test_context, monkeypatch, options, pick)
    handler = _ListHandler()
    log = cw_screen_yinlang.log
    log.addHandler(handler)
    level_before = log.level
    log.setLevel(logging.INFO)
    try:
        result = op.act()
    finally:
        log.setLevel(level_before)
        log.removeHandler(handler)

    assert result.is_success, f'合法 pick 应派发后 success,实际 {result.status!r}'
    assert len(dispatched) == 1, f'应恰派发一次,实际 {dispatched}'
    param, env = dispatched[0]
    assert param is pick, '派发 param 应 = 策略产值原对象(直发零重建)'
    assert env.branch_type == PLANNER_LEG_UPGRADE and env.norm_item == ''
    expected = op._card_point(1)
    assert (env.target.x, env.target.y) == (expected.x, expected.y), \
        f'派发点应 = 右卡 area 推导点,实际 {env.target} 期望 {expected}'
    logged = [r.getMessage() for r in handler.records
              if '[cw][planner]' in r.getMessage()]
    assert any(_UPGRADE_TEXT[:24] in m and '右' in m for m in logged), \
        f'决策日志行应含所选卡文案与左右卡位,实际 {logged}'
