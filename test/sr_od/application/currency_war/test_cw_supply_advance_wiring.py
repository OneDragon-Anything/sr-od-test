"""补给侧节点推进接线行为锁(迭代
changes/2026-09-20-node-advance-action-report landing 3.3 判据面):

- ``CwScreenSupplyNode`` 观察 node 节点条锚定(顶部「备战阶段 X-Y」→
  ``observe_node_anchor``)与 ``CwActionPickSupplyOp`` 确认链推进上报
  (supply_confirm,时点门 = 备战锚转移证据)的联合剧本;
- 判据 ↔ 测试对照(landing §3.3 完成判据):
  - 自动弹形态(结算确认→补给屏→锚定→确认→推进恰一次)
    → test_auto_popup_supply_advances_once
  - divert 形态(备战帧锚定→补给屏→确认→推进恰一次)
    → test_divert_form_supply_advances_once
  - 证据 miss = 不上报(不重试;下帧锚定补推归 kernel 测试覆盖)
    → test_evidence_miss_no_report

kernel 原语语义(门挡/去重/补推)由 test_cw_node_advance_report 承重,
本文件只锁接线面(读数→锚定→门放行恰一档 / miss 不报)。area 建档对账
(analyze_screen 离线命中)见交付报告,不入测试。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
    observe_node_anchor,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionPickSupplyParam

#: 剧本读数:节点条「备战阶段 1-5」→ 序号 5(补给节点 = 位面1 第5轮)。
_ORD_1_5 = (1 - 1) * 9 + 5


def _make_match(test_context, monkeypatch):
    """局容器装配:session + gs 挂 cw_match(game_state_from_ctx 供给口)。"""
    session = StrategySession()
    match = SimpleNamespace(session=session)
    match.gs = game_state_of(session)
    monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
    return match


def _run_pick_supply(test_context, monkeypatch, match, *, evidence_hit: bool):
    """跑 CwActionPickSupplyOp 确认链:宿主机械半全桩(点选/确认点击/证据
    单探),只留记录面(意图遥测 + 推进上报)真跑。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_overlay_pick_action as pa,
    )

    host = SimpleNamespace(
        ctx=SimpleNamespace(controller=SimpleNamespace(
            mouse_move=lambda p: None, click=lambda p, **k: None)),
        screenshot=lambda: object(),
        round_by_find_and_click_area=lambda *a, **k: _Area(True),
        round_by_find_area=lambda *a, **k: _Area(evidence_hit),
    )
    env = pa.OverlayPickExecEnv(op=host, match=None, idx=0,
                                target=SimpleNamespace(x=900, y=550),
                                picked=None)
    op = pa.CwActionPickSupplyOp(
        test_context, CwActionPickSupplyParam(idx=0), env)
    _run_node(test_context, op, op.run)


def _run_supply_observe(test_context, monkeypatch, ordinal: int | None):
    """跑 CwScreenSupplyNode 观察 node:门内 + 选项读/节点条读桩化
    (节点条返回剧本读数;None = 读不得跳过锁的对照位)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as sn,
    )

    op = sn.CwScreenSupplyNode(test_context)
    monkeypatch.setattr(op, 'last_screenshot', object(), raising=False)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(True))
    monkeypatch.setattr(sn, 'read_supply_options', lambda ctx, screen: [])
    monkeypatch.setattr(op, '_read_node_bar', lambda screen: ordinal)
    _run_node(test_context, op, op.observe)


def test_auto_popup_supply_advances_once(test_context, monkeypatch) -> None:
    """自动弹形态剧本:结算确认直接弹补给屏(无备战帧锚定,容器 v=None)
    → 补给屏观察 node 节点条读数首锚定(1-5 → 5)→ 选补给确认 + 备战锚
    转移证据在 → supply_confirm 推进恰一次(5 → 6);重复上报被观察态门
    结构挡(推进后 source=logic)。"""
    match = _make_match(test_context, monkeypatch)
    gs = match.gs
    _run_supply_observe(test_context, monkeypatch, _ORD_1_5)
    assert gs.node_ord.value == _ORD_1_5, \
        '自动弹形态:补给屏观察 node 完成首锚定(v=None 行)'
    assert gs.node_ord.source == 'observation'
    _run_pick_supply(test_context, monkeypatch, match, evidence_hit=True)
    assert gs.node_ord.value == _ORD_1_5 + 1, \
        '确认 + 转移证据在:推进恰一档'
    assert gs.node_ord.source == 'logic', '动作推进 = 推进未确认态'


def test_divert_form_supply_advances_once(test_context, monkeypatch) -> None:
    """divert 形态剧本:备战帧已锚(CwScreenPrep 写端形态,此处直接锚)
    → 补给屏(备战的 divert 分支)观察 node 等值 reanchor → 确认 +
    证据在 → supply_confirm 推进恰一次(5 → 6)。"""
    match = _make_match(test_context, monkeypatch)
    gs = match.gs
    observe_node_anchor(gs, _ORD_1_5, trigger_screen='货币战争-备战',
                        actor='CwScreenPrep')
    # 备战→补给 divert:补给屏等值读数 reanchor(仍 observation 态)
    _run_supply_observe(test_context, monkeypatch, _ORD_1_5)
    assert gs.node_ord.source == 'observation', 'divert 形态:等值 reanchor'
    _run_pick_supply(test_context, monkeypatch, match, evidence_hit=True)
    assert gs.node_ord.value == _ORD_1_5 + 1, 'divert 形态:推进恰一档'


def test_evidence_miss_no_report(test_context, monkeypatch) -> None:
    """证据 miss = 不上报不重试(辖域契约修正案:转移证据 = 上报时点门,
    非执行验证;兜底 = 观察锚定补推,归 kernel 测试覆盖):确认点击发出
    但备战锚单探 miss → 零推进、序号与源态原样(下帧锚定补推的输入面
    完好)。"""
    match = _make_match(test_context, monkeypatch)
    gs = match.gs
    observe_node_anchor(gs, _ORD_1_5, trigger_screen='货币战争-补给',
                        actor='CwScreenSupplyNode')
    _run_pick_supply(test_context, monkeypatch, match, evidence_hit=False)
    assert gs.node_ord.value == _ORD_1_5, '证据 miss:零推进不上报'
    assert gs.node_ord.source == 'observation', '源态原样(锚定态保持)'
