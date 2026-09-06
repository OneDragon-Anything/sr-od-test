"""商店访问编排 visit_open_shop(店已开态入口)锁:策略器决策路径。

背景(ADR-0562,用户裁定 2026-09-06):外循环 0n 分支处理由「硬编码点
收起交回重判」改为转交 CwScreenPrep.visit_open_shop——「收不收」由策略器
基于期望态决定(CloseShop = 商店画面 op 的一等终结动作,ADR-0517 决策
4/5),路由层不越权。本文件锁其编排语义:

- 店已开 + 有可买牌 → 买入发生 + CloseShop 收尾(编排恰调一次关店);
- 店已开 + 无可买牌 → CloseShop 直接收尾零买入(全函数「无动作可做」
  = 直接选终结 op,决策 5);
- 关店未生效 → 访问失败返回(失败路径如实申报,不冒充进展);
- 入口观察重建期望态(session.last_state 由入口现读刷新——0n 进入时
  last_state 可能是外循环上一轮的陈旧值,靠入口观察归零,ADR-0517 决策 8)。

分层声明:0n 分支路由面(判定互斥/序位/转交分键)单一源 =
test_cw_shop_open_branch.py;run_buy_waves 循环内部语义(刷新终结/帧帽/
落地门)单一源 = test_cw_shop_refresh.py——本文件只锁「店已开入口 →
策略器决策 → 关店终结」的编排面,离线手法(替身读数/台账隔离)复刻
test_cw_shop_refresh._make_op 同款,不跨文件 import 测试私有夹具。
"""
from __future__ import annotations
from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import state_of

import pathlib
from typing import Any

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    CloseShop,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
)
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_OLD_NAMES = ['希儿', '景元', '布洛妮娅', '克拉拉', '杰帕德']


def _shop_cards(names: list[str]) -> list[ShopCard]:
    return [ShopCard(x=i, faction='?', name=n, cost=3, star=1)
            for i, n in enumerate(names)]


class _StubStrategy:
    """替身决策源(ADR-0517 单动作形态):按调用次序逐帧吐单动作,
    耗尽后恒吐 CloseShop(「无动作可做」的终结语义,决策 4/6)。"""

    def __init__(self, actions: list[Any]):
        self._acts = list(actions)
        self.calls = 0

    def update_target(self, state, session, config) -> None:
        pass

    def decide_shop_action(self, session, config) -> Any:
        i = self.calls
        self.calls += 1
        return self._acts[i] if i < len(self._acts) else CloseShop()


def _make_prep(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
               tmp_path: pathlib.Path, actions: list[Any]) -> Any:
    """装配被测 CwScreenPrep + 全部替身(观测输入/决策源/台账隔离/关店桩)。

    返回 (prep, close_calls)。替身面(与 test_cw_shop_refresh._make_op
    同款手法):read_game_state 逐次读数(入口观察重建)、read_shop_cards
    牌名序列、read_gold/opt 金读数、关店桩记录调用不真点击、
    save_decision_frame 桩(零真实 .debug 落盘)、节点探针零序列跳过。
    """
    from sr_od.application.currency_war.obs import cw_observation as cwo
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards as buy_cards_mod,
    )
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_close_shop as close_mod,
    )

    # 台账隔离(不写真实 .debug;唯一拥有者 = telemetry.state 单例簇)
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                   replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'cw0nvt')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(defects, 'record_defect', lambda *a, **k: None)

    # 入口观察替身:恒同帧(单段场景,无刷新重观察);gold>0 免触发救援读
    _state = GameState(gold=10, plane=1, round_num=5, level=5,
                       shop=_shop_cards(_OLD_NAMES))
    monkeypatch.setattr(cwo, 'read_game_state', lambda *a, **k: _state)
    monkeypatch.setattr(buy_cards_mod, 'read_game_state',
                        lambda *a, **k: _state)
    monkeypatch.setattr(cwo, 'read_gold', lambda *a, **k: 10)
    monkeypatch.setattr(buy_cards_mod, 'read_gold', lambda *a, **k: 10)
    monkeypatch.setattr(buy_cards_mod, 'read_gold_opt', lambda *a, **k: 10)
    monkeypatch.setattr(buy_cards_mod, 'read_shop_cards',
                        lambda *a, **k: _shop_cards(_OLD_NAMES))
    monkeypatch.setattr(cwo, 'read_hp_opt', lambda *a, **k: None)
    monkeypatch.setattr(cwo, 'read_phase_round', lambda *a, **k: (1, 5))
    monkeypatch.setattr(cw_telemetry, 'set_unit_exec_facts',
                        lambda **k: None)
    # 决策帧留证钩子桩(零真实落盘;挂点行在生产代码中保留)
    monkeypatch.setattr(buy_cards_mod, 'save_decision_frame',
                        lambda *a, **k: 'stub.png')
    # 节点探针零序列(离线无模板装配,探针自跳过)
    monkeypatch.setattr(cwo, 'read_node_sequence', lambda *a, **k: [])

    # 关店桩:记录调用,恒成功(关店失败锁单独翻转)
    close_calls: list[bool] = []

    class _CloseRes:
        is_success = True
        status = '成功'

    def _close(op, *a, **k):
        close_calls.append(True)
        return _CloseRes()

    monkeypatch.setattr(close_mod, 'close_shop', _close)

    # 决策源替身挂 match(直接构造,不经 ctx 装配链)
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_StubStrategy(actions),
                                         StrategySession()))

    # 被测对象:真实 CwScreenPrep(生产唯一宿主;0n 转交同款)
    prep = CwScreenPrep(test_context)
    # 截图桩:逐帧翻转亮度(买前/买后裁片不同 → buy_click_ineffective 判
    # 有效,买入落地;帧须真 ndarray——bench pixel-diff 通道会做矩阵切片)
    import numpy as np
    _shot_i = {'i': 0}

    def _shot():
        _shot_i['i'] += 1
        v = 40 if _shot_i['i'] % 2 else 200
        return np.full((1080, 1920, 3), v, dtype=np.uint8)

    monkeypatch.setattr(prep, 'screenshot', _shot)
    monkeypatch.setattr(prep, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(prep, 'save_screenshot', lambda *a, **k: '<shot>')
    # BuyCard 点击走 ctx.controller.click:桩记录,不真点
    clicks: list[Any] = []

    class _Ctrl:
        def click(self, pt, *a, **k):
            clicks.append(pt)

    monkeypatch.setattr(test_context, 'controller', _Ctrl())
    return prep, close_calls, clicks


def _visit(prep) -> tuple[bool, str]:
    enter_running_state(prep.ctx)
    try:
        with fast_sleep():
            return prep.visit_open_shop()
    finally:
        reset_running_state(prep.ctx, prep)


def test_visit_open_shop_buys_then_closes(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path) -> None:
    """策略路径锁①:店已开 + 有可买牌 → 买入发生(买入动作恰一次,tracked
    入账)+ CloseShop 收尾(编排恰调一次关店)+ 访问成功返回。"""
    prep, close_calls, clicks = _make_prep(
        test_context, monkeypatch, tmp_path,
        [BuyCard(card=ShopCard(x=0, faction='?', name='希儿',
                               cost=3, star=1)), CloseShop()])
    ok, detail = _visit(prep)
    assert ok, f'有可买牌访问应成功收尾:{detail!r}'
    assert len(close_calls) == 1, (
        f'CloseShop 收尾应编排恰一次关店:close_calls={close_calls}')
    assert len(clicks) >= 1, '买入点击未发生(策略器提案未落地)'
    sess = test_context.cw_match.session
    bought = [c.char_id for c in exec_state_of(sess).tracked_bench_chars if c is not None]
    assert '希儿' in bought, (
        f'买入未入 tracked 账(落地门/记账面破缺):{bought}')


def test_visit_open_shop_no_buyable_closes_directly(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path) -> None:
    """策略路径锁②:店已开 + 无可买牌(策略器无动作可做)→ CloseShop
    直接收尾、零买入、访问成功——全函数「无动作可做 = 选终结 op」的
    0n 入口形态(决策 5)。"""
    prep, close_calls, clicks = _make_prep(
        test_context, monkeypatch, tmp_path, [])
    ok, detail = _visit(prep)
    assert ok, f'无可买牌访问应直接收尾:{detail!r}'
    assert len(close_calls) == 1, (
        f'CloseShop 应直接收尾(恰一次关店):{close_calls}')
    assert clicks == [], '零买入面不得有点击(决策循环直落终结)'
    # tracked 账迁 ExecState(session 职责分离批):经 exec_state_of 抽读
    from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
    assert not [c for c in exec_state_of(
                    test_context.cw_match.session).tracked_bench_chars
                if c is not None], '零买入面 tracked 账不得有进账'


def test_visit_open_shop_close_fail_reported(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path) -> None:
    """编排锁③:关店未生效 → 访问失败如实返回(不冒充进展;店留着交
    上层重新识别,失败路径语义与显式开店路径同款)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_close_shop as close_mod,
    )

    def _close_fail(op, *a, **k):
        return type('R', (), {'is_success': False, 'status': '失败'})()

    prep, _close_calls, _clicks = _make_prep(
        test_context, monkeypatch, tmp_path, [])
    # 先装配(内含关店成功桩)再翻转失败桩——被测方法调用时取模块属性,
    # 后设的桩生效
    monkeypatch.setattr(close_mod, 'close_shop', _close_fail)
    ok, detail = _visit(prep)
    assert not ok and '关店未生效' in detail, (
        f'关店失败须如实申报:{ok!r} {detail!r}')


def test_visit_open_shop_entry_rebuilds_last_state(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path: pathlib.Path) -> None:
    """入口观察重建锁:进入前 session.last_state 为陈旧值(0n 进入形态:
    外循环上一轮的残值)→ 访问后 last_state = 入口现读重建态(plane/
    round/shop 与替身观察一致)——入口观察即对账(ADR-0517 决策 8)。"""
    sess0 = StrategySession()
    sess0.last_state = GameState(gold=99, plane=7, round_num=7, level=9,
                                 shop=[])   # 陈旧残值
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_StubStrategy([]), sess0))
    prep, _close_calls, _clicks = _make_prep(
        test_context, monkeypatch, tmp_path, [])
    # _make_prep 重挂了 match,取其 session 注入陈旧值
    test_context.cw_match.session.last_state = GameState(
        gold=99, plane=7, round_num=7, level=9, shop=[])
    ok, detail = _visit(prep)
    assert ok, detail
    ls = test_context.cw_match.session.last_state
    assert (ls.plane, ls.round_num) == (1, 5), (
        f'入口观察未重建 last_state(仍陈旧):plane={ls.plane} '
        f'round={ls.round_num}')
    assert [c.name for c in (ls.shop or [])] == _OLD_NAMES, (
        '入口观察未现读牌面')
