"""buy_cards 防御路径改道引导漏斗·三行为差消除锁(终态契约 T-5 返工)。

病理(T-5-r1 验收①,.debug/change-reviews/2026-09-16-strategy-terminal-contract/
T-5-r1.md §5.1a):``cw_screen_buy_cards`` 独立单跑的 cw_match 缺席防御
分支此前裸构造 ``CurrencyWarMatch``,与生产容器建立漏斗
``establish_new_match`` 实差三处行为:rng 种子(漏斗按 config.strategy_seed
播 session.rng)/reset_layout_unknown_state(新局起点复位布局未知态计数)/
遥测 run_id_provider(局容器建立点注入 journal 装配)。修复 = 防御分支直调
漏斗(先 ``discard_stale_match_container`` 保「局外不复用」,再 establish)
——现居观察 node 首拍(两 node 规范形态:兜底建核 = 观察 node 第①步,
触发条件 = ctx.cw_match 缺席)。

锁三件(接线锁形态照 test_cw_journal_assembly_guard):
1. 种子:防御构建的容器 session.rng 按 config.strategy_seed 播种
   (seed=42 → Random(42);seed=None → 缺省固定 0 种不覆盖);
2. 复位:防御构建触发 reset_layout_unknown_state(cw_vocab 槽转发);
3. 遥测:防御构建经 game_state_of 建立点以遥测 ``current_run_id`` 为
   provider 触发 journal 装配。

离线宿主判据:cw_match 缺席入跑,防御建核后入口 area 校验处收工
(level 按钮缺失 → round_fail),执行段恰好只含防御建核 + 漏斗序 +
area 锚定,零读屏。驱动 = 真类实例 + 节点函数直驱(过渡薄壳已随 3.4
退役;先例 = test_cw_shop_two_node_form)。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_game_state as gs_mod
import sr_od.application.currency_war.kernel.cw_vocab as vocab_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
from sr_od.application.currency_war.telemetry import state as tel_state


def _run_observe_node(ctx: SimpleNamespace):
    """观察 node 直驱(薄壳退役承接):构造真类实例跑观察 node,返回
    轮次结果(防御路径锁只辖观察 node 段,决策循环不入锁面)。"""
    op = buy_mod.CwScreenBuyCards(ctx)
    return op.observe()


def _defense_host(monkeypatch: pytest.MonkeyPatch, *,
                  strategy_seed: int | None) -> SimpleNamespace:
    """替身缝 = 观察 node 顶部消费面:config 工厂(seed 可参)/
    点击点位/area 中心(恒缺 → 入口校验 round_fail 早退)。
    ctx.cw_match 缺席 = 独立单跑前提(兜底建核触发面)。"""
    monkeypatch.setattr(
        buy_mod, 'CurrencyWarConfig',
        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                    strategy_seed=strategy_seed))
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: None)
    return SimpleNamespace(
        current_instance_idx=1, cw_match=None,
        cw_selected_difficulty=None,
        currency_war_strategy_plugin_dirs=[])


def test_defense_path_wires_seed_and_telemetry_like_funnel(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """差①种子 + 差③遥测消除:防御构建 session.rng 按 strategy_seed
    播种;局容器建立点以遥测 current_run_id 为 provider 触发 journal
    装配;策略器/状态同源接线与漏斗同款。"""
    assembly_calls: list = []
    monkeypatch.setattr(gs_mod, 'ensure_journal_assembly',
                        lambda provider: assembly_calls.append(provider))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't-def-42')

    ctx = _defense_host(monkeypatch, strategy_seed=42)
    rr = _run_observe_node(ctx)

    assert rr is not None and rr.is_success is False, \
        '入口 area 校验早退(执行段零读屏)'
    assert 'area 缺失' in (rr.status or ''), 'area 缺失显式失败(带 area 名)'
    match = ctx.cw_match
    assert match is not None
    # 差①种子:漏斗同款(session.rng = Random(config.strategy_seed))
    assert match.session.rng.random() == random.Random(42).random()
    # 差③遥测:建立点注入 run_id_provider = 遥测 current_run_id 载体
    assert len(assembly_calls) == 1
    assert assembly_calls[0]() == 't-def-42'
    # 策略器经漏斗 StrategyManager 按 config.strategy_id 实例化
    assert match.strategy.STRATEGY_ID == 'mandate_v1'
    # 状态同源接线(漏斗 §2.6 过渡桥同款):session 键位状态 = 策略器状态
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        strategy_state_of,
    )
    assert strategy_state_of(match.session) is match.strategy.state


def test_defense_path_seed_none_keeps_default_rng(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """种子 None 臂:漏斗同款不播(config.strategy_seed=None 不覆盖
    session.rng,保持 StrategySession 缺省固定 0 种)。"""
    monkeypatch.setattr(gs_mod, 'ensure_journal_assembly', lambda _p: None)

    ctx = _defense_host(monkeypatch, strategy_seed=None)
    _run_observe_node(ctx)

    match = ctx.cw_match
    assert match.session.rng.random() == random.Random(0).random()


def test_defense_path_resets_layout_unknown_state(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """差②复位消除:防御构建在新局起点触发 reset_layout_unknown_state
    (cw_vocab 槽转发计次;漏斗同款 best-effort 序)。"""
    reset_calls: list = []
    monkeypatch.setattr(vocab_mod, '_layout_unknown_reset',
                        lambda: reset_calls.append(True))
    monkeypatch.setattr(gs_mod, 'ensure_journal_assembly', lambda _p: None)

    _run_observe_node(_defense_host(monkeypatch, strategy_seed=None))

    assert len(reset_calls) == 1


def test_defense_path_rebuilds_fresh_per_invocation(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """防御语义保持(局外不复用):cw_match 缺席的独立调用先弃置残留
    容器再新建(discard+establish 同款衔接),session 全量重建非复用——
    与入口链 CwEntryStart 的残留弃置纪律一致。"""
    monkeypatch.setattr(gs_mod, 'ensure_journal_assembly', lambda _p: None)
    ctx = _defense_host(monkeypatch, strategy_seed=None)

    _run_observe_node(ctx)
    first = ctx.cw_match
    ctx.cw_match = None   # 再次独立单跑(cw_match 缺席前提)
    _run_observe_node(ctx)
    second = ctx.cw_match

    assert first is not None and second is not None
    assert second is not first
    assert second.session is not first.session
