"""备战契约接口单动作形状锁(decide_prep_screen 恰返回一个 CwAction)。

出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2
备战接口行(``decide_prep_screen`` 行)——终态契约 §2.2 单动作词表:
返回**恰一个 CwAction** = 本帧要执行的那个;空发射帧 →
``CwActionObsParam(scope='outer_loop')``(本帧无动作可发,交回外循环
重观察;原 HoldFrame 通道收编,用户裁定 2026-09-20;``None`` 退役);
非法形状由消费端 F3 守卫拒绝。

三锁各辖一个契约点:

- 边界单动作:mandate_v1 具现对有动作帧返回恰一个 ``CwAction`` = 决策核
  发射序列**首项**(锁消费边界的映射形状;决策核内发射组织不在锁面);
- 空发射通道:决策核空发射 → 返回 ``CwActionObsParam(scope='outer_loop')``
  (备战域「本帧无动作」是合法通道,不折算出战替身,无 None);
- 消费端守卫:非 ``CwAction`` 的非法返回 → 决策循环 F3 fail(守卫断言
  语义:策略器 bug 响亮暴露,禁静默跳过)。

零真实副作用:①②经决策核发射缝桩(模块级 ``decide_prep_frame``)离线
直调,不读屏;③走 op 生命周期决策循环(harness run_node,fast_sleep
包裹),桩策略返回非法形状在执行前即被守卫拒绝,零点击零落盘。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import run_node

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwAction,
    CwActionObsParam,
    CwActionSellBenchParam,
    CwActionStartBattleParam,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    bridge as cw_bridge,
)


def _prep_strategy(monkeypatch: pytest.MonkeyPatch,
                   emission: list[CwAction]) -> tuple[
        cw_bridge.MandateV1Strategy, StrategySession]:
    """mandate_v1 具现(真实类)+ 决策核发射缝桩,离线直调备战契约入口。

    - ``decide_prep_frame`` 模块桩 = 决策核发射缝——本锁辖「边界把发射
      序列映射成单动作/空发射 obs」的形状,核内三遍编排/帧稳定截断不在
      锁面;预算披露(决策入口前置发射位之后)走真实现,零屏零外部面;
    - ``gs.frame_class_prep`` 缺省 'none' → 入口内务(帧代次消费)
      空转,方向刷新不触发,测试零全局残留。
    """
    session = StrategySession()
    strategy = cw_bridge.MandateV1Strategy(
        game_state_of(session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    # (黑板帧装配已随 gs.prep_obs 退役删除——阶段 3.5:决策输入 = 容器
    #  直读,「观察帧缺失即抛错」防线随黑板消亡,编排前提由画面 op 保证。)
    monkeypatch.setattr(
        cw_bridge, 'decide_prep_frame',
        lambda session_, config, registry=None: list(emission))
    return strategy, session


def test_prep_contract_returns_single_action_first_of_emission(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """备战契约边界:有动作帧 → 返回恰一个 ``CwAction`` = 发射序列首项。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(恰一个动作)。
    发射两动作只取首项:锁「单动作循环
    逐帧恰取一个动作」的边界映射——契约面返回列表整体(旧形状回潮)或
    取尾项都会在此红。
    """
    first = CwActionStartBattleParam()
    second = CwActionSellBenchParam(bench_idx=3)
    strategy, session = _prep_strategy(monkeypatch, [first, second])
    result = strategy.decide_prep_screen()
    assert isinstance(result, CwAction)
    assert result is first


def test_prep_contract_empty_emission_returns_hold_frame(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """备战契约边界:空发射 → 返回 ``CwActionObsParam(scope='outer_loop')``
    = 本帧无动作交回外循环。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(终态契约 §2.2:空发射帧 = 交回外循环重观察,None 退役;原 HoldFrame 收编,用户裁定 2026-09-20)。
    备战域
    「本帧无动作」是合法通道:返回必须是 obs 交回口径本身——返回
    ``None``(退役形状回潮)或空列表或抛错都不合格。
    """
    strategy, session = _prep_strategy(monkeypatch, [])
    result = strategy.decide_prep_screen()
    assert isinstance(result, CwAction)
    assert isinstance(result, CwActionObsParam)
    assert result.scope == 'outer_loop'


def test_prep_consumer_rejects_illegal_return_f3_fail(
        test_context, monkeypatch: pytest.MonkeyPatch) -> None:
    """消费端守卫:非法返回(非 ``CwAction``)→ 决策循环 F3 fail。

    出处 = docs/develop/sr_od/application/currency_war/flow/README.md §2.2 备战接口行(返回恰一个动作;非法形状不进执行)。
    守卫断言
    语义 = 策略器 bug 响亮暴露:决策循环在执行前拒绝并以具名 fail
    交回外循环,禁静默跳过。走 op 决策动作 node 路径(两 node 形态
    ()的 ③-⑤ 单动作决策循环宿主,
    守卫逐字同,单锁辖同一条契约)。
    """

    class _IllegalPrepStrategy:
        """桩策略:备战决策返回非法形状(字符串;非 CwAction)。"""

        def decide_prep_screen(self) -> str:
            return '备战动作'

    match = CurrencyWarMatch(_IllegalPrepStrategy(), StrategySession())
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    op = CwScreenPrep(test_context)
    # 阶段 3.5:黑板载体随 gs.prep_obs 退役——决策入口零参直读容器。
    rs = run_node(test_context, op, op.act)
    assert not rs.is_success
    assert rs.status == '策略输出非 CwAction(F3)'
