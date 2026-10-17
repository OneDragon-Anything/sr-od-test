"""补给节点 op 利息接线测试(镜像 src = operations/cw_screen/
cw_screen_supply_node.py 的来源 C 计数刻;op 流程面测试 =
test_obs_arch_event_screens.py〔超限只读〕,本文件按 src 镜像规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.4 复裁版)§2.5
来源 C + §4.8②:
- 常规形态(备战帧已锚本节点 = 形态门开)领取完成刻推算计数(基座 =
  备战帧 gs.gold 观察 = 领取前真值);
- 「自动弹」形态(本节点首次锚定发生在补给屏,形态门关)宁缺零计数;
  接管局形态同归宁缺;
- 刷新分支/对照闸拒绝路径不经计数体 = 天然防补给 op 重入双计;
- 局外兜底路径(match 缺席)零计数。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import cw4_session

from sr_od.application.currency_war.kernel.cw_economy import (
    DEFAULT_INTEREST_CAP,
    interest,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_supply_node import (
    CwScreenSupplyNode,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _bare_op(test_context, monkeypatch, *, prep_anchored: bool):
    """补给 op 裸实例(计数体单元面;形态门 = 观察轮锚定 token 判的
    产物载体,读屏链归流程测试辖)。"""
    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match', session, raising=False)
    op = CwScreenSupplyNode.__new__(CwScreenSupplyNode)
    op.ctx = test_context
    op._prep_anchored = prep_anchored
    gs = game_state_of(session)
    gs.observe(gs.active_env, '公司契约', sig=_SIG_OBS)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.gold, 100, sig=_SIG_OBS)
    return op, session


def test_source_c_pick_completion_counting(test_context, monkeypatch) -> None:
    """常规形态领取完成刻计数(T-27 设计 §4.8②):基座 = 备战帧 gs.gold
    观察 100 → 推算息 5(缺省 cap 满档,现算期望);cap/flat 推算单一源
    = estimate_node_interest;推算支与来源 A 面板读数无耦合(纯公式)。
    match 面 = 生产消费形态(gs 宿主)。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=True)
    gs = game_state_of(session)
    op._count_interest_after_pick(SimpleNamespace(gs=gs))
    assert gs.effects.interest_earned == interest(
        100, DEFAULT_INTEREST_CAP), '领取完成刻推算入账(基座 100,现算期望)'


def test_source_c_auto_popup_gate_counts_nothing(
        test_context, monkeypatch) -> None:
    """「自动弹」形态宁缺(T-27 设计 v2.4 复裁:无备战帧形态门关):
    基座不取(哪怕 gs.gold 在册——自动弹形态其值非本节点备战帧观察,
    禁用)→ 零计数;接管局形态同归宁缺口径。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=False)
    gs = game_state_of(session)
    op._count_interest_after_pick(SimpleNamespace(gs=gs))
    assert gs.effects.interest_earned == 0, '自动弹形态宁缺零计数'


def test_source_c_out_of_match_counts_nothing(
        test_context, monkeypatch) -> None:
    """局外兜底路径(match 缺席)零计数(容器不可得,禁猜)。"""
    op, session = _bare_op(test_context, monkeypatch, prep_anchored=True)
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    gs = game_state_of(session)
    op._count_interest_after_pick(None)
    assert gs.effects.interest_earned == 0, '局外路径零计数'
