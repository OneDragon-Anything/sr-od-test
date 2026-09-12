"""购买执行结果落地门调用环锁(落地审 C1 调用环级;检出→False→投影/
守卫双跳过)。

承载体 = cw_op_buy_cards.apply_action_outcome(调用环单一源,run_buy_waves
消费位已收编):未落地 ⇒ 两侧都不动(不投影/不守卫/不入「已买」集);
落地 ⇒ 容器规则通道投影(投影口直写 + 合成升星腿;T-163 纯规则路线——
原 ShopActionOp.project 的 simulate 前瞻投影已删)+ guard_expected_vs_tracked。

锁语义重推记录(T-163):本锁钉的是调用环门(哪些挂点按什么序触发),
不是投影公式本身——投影公式对 simulate 的等价性归 M1
(test_cw_shop_projection_logic)。project 方法删除后,spy 面从
``aop.project`` 切到 kernel 两写口(apply_shop_action_logic /
apply_shop_merge_leg;apply_action_outcome 内惰性 import,monkeypatch
kernel 模块属性即拦截)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_game_state
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CwWorkFrame,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op import (
    cw_op_buy_cards,
    cw_shop_action_ops,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    BuyCardOp,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _action() -> BuyCard:
    return BuyCard(card=ShopCard(x=50, name='杰帕德', cost=4, star=1),
                   reason='m2_stockpile')


def _drive(monkeypatch, ok: bool):
    calls: list = []
    monkeypatch.setattr(cw_shop_action_ops, 'guard_expected_vs_tracked',
                        lambda proj, session, stage='project': calls.append(
                            ('guard', proj)))
    # kernel 两写口 spy(apply_action_outcome 函数内惰性 import,每次调用
    # 时从 kernel 模块属性取,monkeypatch 生效)。
    monkeypatch.setattr(
        cw_game_state, 'apply_shop_action_logic',
        lambda bs, action, **kw: calls.append(
            ('logic', type(action).__name__)))
    monkeypatch.setattr(
        cw_game_state, 'apply_shop_merge_leg',
        lambda bs, action, **kw: calls.append(
            ('merge', type(action).__name__)))
    aop = BuyCardOp(_action())
    # ledger 桩字段对齐生产 ShopVisitLedger 消费面(buy_purchases = W536
    # merge_expect 基座,执行回执 k 计数读点;缺字段 = SimpleNamespace
    # 桩滞后,非语义锁面)。
    ledger = SimpleNamespace(refresh_first_action=True, buy_purchases=[])
    match = SimpleNamespace(session=SimpleNamespace(
        shop_state_frame=None))
    state_of(match.session).cw4_visit_bought_names = []
    state = CwWorkFrame(bench=[])
    visit_actions: list = []
    cw_op_buy_cards.apply_action_outcome(
        aop, aop.action, ok, state, match, ledger, visit_actions)
    return calls, visit_actions, ledger, match


class TestCallerOutcomeGate:

    def test_ineffective_gates_project_and_guard(self, monkeypatch):
        """检出(False)⇒ 投影双写口不触 + guard 不触 + 不入「已买」集
        (期望账不得投影未发生的买入,调用环级)。"""
        calls, visit, ledger, match = _drive(monkeypatch, ok=False)
        assert calls == []                       # 投影/守卫挂点全不触
        assert state_of(match.session).cw4_visit_bought_names == []   # 不入已买集
        assert [type(a).__name__ for a in visit] == ['BuyCard']
        assert ledger.refresh_first_action is True   # 未落地不置位

    def test_effective_runs_project_and_guard(self, monkeypatch):
        """对照:落地(True)⇒ 投影口直写 + 升星腿 + guard 依次触发,
        「已买」集入名。"""
        calls, visit, ledger, match = _drive(monkeypatch, ok=True)
        assert [k for k, _ in calls] == ['logic', 'merge', 'guard']
        assert state_of(match.session).cw4_visit_bought_names == ['杰帕德']
        assert ledger.refresh_first_action is False
        assert len(visit) == 1
