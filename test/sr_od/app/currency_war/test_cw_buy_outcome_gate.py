"""购买执行结果落地门调用环锁(落地审 C1 调用环级;检出→False→投影/
守卫双跳过)。

承载体 = cw_op_buy_cards.apply_action_outcome(调用环单一源,run_buy_waves
消费位已收编):未落地 ⇒ 两侧都不动(不投影/不守卫/不入「已买」集);
落地 ⇒ 投影 + guard_expected_vs_tracked。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op import (
    cw_op_buy_cards,
    cw_shop_action_ops,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    BuyCardOp,
)


class _FakeAop(BuyCardOp):
    # project 方法体由 _drive 的 monkeypatch 覆盖,仅作 setattr 属性锚。

    def __init__(self, action):
        super().__init__(action)

    def project(self, state):
        return ('proj', state)


def _action() -> BuyCard:
    return BuyCard(card=ShopCard(x=50, name='杰帕德', cost=4, star=1),
                   reason='m2_stockpile')


def _drive(monkeypatch, ok: bool):
    calls: list = []
    monkeypatch.setattr(cw_shop_action_ops, 'guard_expected_vs_tracked',
                        lambda proj, session: calls.append(
                            ('guard', proj)))
    aop = _FakeAop(_action())
    monkeypatch.setattr(
        aop, 'project',
        lambda st: calls.append(('project', st)) or ('proj', st))
    ledger = SimpleNamespace(refresh_first_action=True)
    match = SimpleNamespace(session=SimpleNamespace(
        shop_state_frame=None, cw4_visit_bought_names=[]))
    state = GameState(bench=[])
    visit_actions: list = []
    cw_op_buy_cards.apply_action_outcome(
        aop, aop.action, ok, state, match, ledger, visit_actions)
    return calls, visit_actions, ledger, match


class TestCallerOutcomeGate:

    def test_ineffective_gates_project_and_guard(self, monkeypatch):
        """检出(False)⇒ project 不执行 + guard 不触 + 不入「已买」集
        (期望账不得投影未发生的买入,调用环级)。"""
        calls, visit, ledger, match = _drive(monkeypatch, ok=False)
        assert calls == []                       # project/guard 双不触
        assert match.session.cw4_visit_bought_names == []   # 不入已买集
        assert [type(a).__name__ for a in visit] == ['BuyCard']
        assert ledger.refresh_first_action is True   # 未落地不置位

    def test_effective_runs_project_and_guard(self, monkeypatch):
        """对照:落地(True)⇒ project + guard 双执行,「已买」集入名。"""
        calls, visit, ledger, match = _drive(monkeypatch, ok=True)
        kinds = [k for k, _ in calls]
        assert kinds == ['project', 'guard']
        assert match.session.cw4_visit_bought_names == ['杰帕德']
        assert ledger.refresh_first_action is False
        assert len(visit) == 1
