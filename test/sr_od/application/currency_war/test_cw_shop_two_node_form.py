"""商店画面 op 两 node 规范形态锁(迭代 changes/2026-09-21-shop-refresh-terminal
3.4:run_buy_waves 解体为观察 node + 决策动作 node)。

锁的语义(op-layer §1.1 两 node 形态;离线宿主替身沿 test_cw_budget_
disclosure 同式,零真实副作用):

1. 观察 node 每访问恰一次读:入口读恰一次(决策循环零读屏),段首簿记
   迁入(段序号 +1 / 帧代次 ``frame_class_shop = 'full'`` / obs 镜像挂
   实例属性 / shop_entry 决策帧恰一帧);
2. 决策动作 node round_wait 单动作循环:非终结动作执行后 round_wait
   (帧不消费),终结动作执行后 round_success 交回——全动作统一路径,
   零特例拦截(CloseShop 经注册表真执行,不提前退出);
3. 「终结不入 decisions 行」契约:CwActionCloseShopParam 不落商店动作
   回执行(执行事实回执由关店动作 op 自身承担)。

驱动方式 = 真类实例 + 节点函数直驱,读链/点击链桩化(先例 =
test_cw_screen_two_node_family)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_game_state as gs_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
    CwActionCloseShopOp,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards import (
    CwScreenBuyCards,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards',
                        mode='compute')


class _ScriptedStrategy:
    """脚本化决策源:按序弹出动作(记录咨询次数供断言)。"""

    def __init__(self, actions: list) -> None:
        self._actions = list(actions)
        self.calls = 0

    def decide_shop_action(self):
        self.calls += 1
        return self._actions.pop(0)


class _Ctrl:
    """截图/点击/光标停车替身(op 框架经 ctx.controller 触达)。"""

    def __init__(self) -> None:
        self.clicks: list[Point] = []

    def screenshot(self, *a, **k):
        return (0.0, b'')

    def click(self, pos) -> None:
        self.clicks.append(Point(int(pos.x), int(pos.y)))

    def park_cursor(self, *a, **k) -> None:
        pass


def _shop_host(monkeypatch: pytest.MonkeyPatch, strategy) -> tuple:
    """两 node 形态锁共用离线宿主:入口读/决策帧/点位锚定/关店执行位
    点击全桩化,容器在屏 payload 槽1 = 花火。返回 (op, match, gs,
    读数计数, 决策帧 tag 表, 关店点击记录, 商店动作回执 op 名表)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_gs

    match = CurrencyWarMatch(strategy, StrategySession())
    gs = cw4_gs(match.session, gold=30, level=3,
                shop=[ShopCard(x=0, name='花火', faction='?', cost=3,
                               star=1)])
    match.session.strategy_state = SimpleNamespace(
        cw4_counters={}, cw4_segment_serial=0)

    class _Op:
        ctx = SimpleNamespace(current_instance_idx=1, cw_match=match,
                              controller=_Ctrl())

    reads: list = []

    def _entry_receipt(*a, **k):
        reads.append(1)
        from sr_od.application.currency_war.obs.cw_observation import (
            GameStateReadReceipt,
        )
        return GameStateReadReceipt(gold=30, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=3, plane=1, round_num=2)

    frame_tags: list = []
    close_clicks: list = []
    receipt_ops: list = []

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame',
                        lambda op_, tag, screen=None: frame_tags.append(tag))
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: [Point(50, 50)])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    # 预算披露桩化(真实现经 mandate state_of 对异型状态对象冷建覆写,
    # 会换掉宿主的 SimpleNamespace 状态载体;与本锁无关)。
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)
    # 关店执行位点击桩化(「收起」命中 → 点击臂;动画等待已随 time 桩)。
    def _fake_close_click(self, *a, **k):
        close_clicks.append(1)
        return SimpleNamespace(is_success=True)

    monkeypatch.setattr(CwActionCloseShopOp, 'screenshot', lambda self: None)
    monkeypatch.setattr(CwActionCloseShopOp, 'round_by_find_and_click_area',
                        _fake_close_click)
    # 商店动作回执行捕获(kernel 口 lazy import,每次调用取模块属性)。
    def _note_action_receipt(gs_, *, op, applied, reason='', screen='',
                             actor='', extra=None):
        receipt_ops.append(op)

    monkeypatch.setattr(gs_mod, 'note_action_receipt', _note_action_receipt)

    op = CwScreenBuyCards(_Op.ctx)
    return op, match, gs, reads, frame_tags, close_clicks, receipt_ops


def test_observe_node_reads_once_and_books_segment_head(monkeypatch):
    """观察 node 每访问恰一次读 + 段首簿记:入口读恰一次;段序号 +1;
    帧代次 full(每访问入口,刷新后新访问重估方向视图);obs 镜像挂
    实例属性;shop_entry 决策帧恰一帧。"""
    strategy = _ScriptedStrategy([CwActionCloseShopParam()])
    op, match, gs, reads, frame_tags, _close_clicks, _receipts = _shop_host(
        monkeypatch, strategy)

    rr = op.observe()

    assert rr.is_success
    assert reads == [1], '入口观察恰一次读(单次读零防抖)'
    st = match.session.strategy_state
    assert st.cw4_segment_serial == 1, '段序号 +1(visit 边界 = op 边界)'
    assert gs.frame_class_shop == 'full', '帧代次 = 每访问入口 full'
    assert op._obs is not None and op._obs.gold == 30, \
        'CwScreenBuyCardsObs 镜像挂实例属性'
    assert frame_tags == ['shop_entry'], 'shop_entry 决策帧恰一帧'


def test_act_node_round_wait_until_terminal_unified_path(monkeypatch):
    """决策动作 node round_wait 单动作循环(全动作统一路径零拦截):
    非终结买牌执行后 round_wait(零读屏);终结关店经注册表真执行后
    round_success 交回;CloseShopParam 不落商店动作回执行(终结不入
    decisions 行),执行事实回执由关店动作 op 自身承担。"""
    strategy = _ScriptedStrategy([
        CwActionBuyCardParam(card=ShopCard(x=0, name='花火', faction='?',
                                           cost=3, star=1)),
        CwActionCloseShopParam(),
    ])
    op, match, gs, reads, _frame_tags, close_clicks, receipt_ops = \
        _shop_host(monkeypatch, strategy)
    assert op.observe().is_success
    reads.clear()

    rr1 = op.act()
    assert reads == [], '决策循环零读屏(帧不消费)'
    assert not rr1.is_success and rr1.status is None, \
        '非终结动作 → round_wait(帧不消费,零拦截)'
    assert op.ledger.total_buy == 1, '买牌执行落地(账本计数)'
    assert op.ctx.controller.clicks, '买牌点击已发出'

    rr2 = op.act()
    assert rr2.is_success, '终结动作(RefreshShop/CloseShop)→ round_success 交回'
    assert close_clicks == [1], 'CloseShop 经注册表真执行(收起点击)'
    assert strategy.calls == 2, '逐动作决策(零特例拦截,无提前退出)'
    assert receipt_ops == ['CwActionBuyCardParam', 'CwActionCloseShopOp'], \
        ('CwActionCloseShopParam 不入 decisions 行(终结回执由关店动作 op '
         '自身承担);买牌回执行在册')


def test_act_node_unobserved_close_skips_then_executes(monkeypatch):
    """未观察跳过链(留痕后照常执行):未观察态策略关店 → 留痕/熔断判
    定后仍走统一执行路径(零消费动作 = 仅执行关店离店),非提前退出。"""
    from sr_od.application.currency_war.telemetry import defects

    rows: list = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append(kind)

    monkeypatch.setattr(defects, 'record_defect', _rec)

    class _ObsStrategy:
        """未观察门同形替身(恒返回关店;观察态判定 = kernel 字段)。"""

        def decide_shop_action(self):
            return CwActionCloseShopParam()

    strategy = _ObsStrategy()
    op, match, gs, _reads, _frame_tags, close_clicks, _receipts = \
        _shop_host(monkeypatch, strategy)
    game_state_of(match.session).write_logic(
        game_state_of(match.session).tracked_account_observed, False,
        produced_by='test', evidence='takeover_invalidation',
        sig=_LOGIC_SIG)
    assert op.observe().is_success

    rr = op.act()

    assert rr.is_success, '留痕后照常执行(关店终结交回)'
    assert close_clicks == [1], '跳过访问 = 零消费动作,关店离店仍真执行'
    assert 'shop_skipped_unobserved' in rows, '留痕分键显影'
