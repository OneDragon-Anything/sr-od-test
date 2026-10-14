"""商店执行链端口接线锁(迭代 2026-10-12-prep-shop-workflow-redesign 3.5)。

锁的语义(纯执行层,零策略判据):

1. 端口连通:商店域发射 CwActionSellBenchParam / CwActionLevelUpShopParam
   可执行(ShopExecEnv.executor 注入适配,不 AttributeError);
2. 执行参数直达机械层:卖出拖拽两端坐标按商店画面档解析
   (row_area_centers / sell_point 的 screen_name = 商店开画面——商店
   画面档自备 备战栏/出售区 area 的坐标地基消费);买经验按 ``clicks``
   整批连点(升级判据重轴批的整批接口在店内可发);
3. 发出即记账 + 容器上报对账一致:访问账 total_sell / total_xp_buy,
   容器卖出槽位置空、金按上报函数口径推进(gold −cost×clicks);
4. 守卫链照常:SellBench 名-槽不一致在商店域同辖响亮暴露。

驱动方式 = 真类实例 + 节点函数直驱(先例 = test_cw_shop_two_node_form;
读链/拖拽/连点全桩化,零真实副作用)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_game_state as gs_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_shop as buy_mod
import sr_od.application.currency_war.prep_actions as prep_actions_mod
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_obs_core import (
    SHOP_SCREEN_NAME,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCloseShopParam,
    CwActionLevelUpShopParam,
    CwActionSellBenchParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
    CwActionCloseShopOp,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_shop import (
    CwScreenShop,
)
from sr_od.application.currency_war.operations.dev.drag_cw_char import (
    DragCwChar,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)

_LEVEL_BTN_PT = Point(123, 456)   # 购买经验按钮锚(观察 node area 桩值)
_BENCH_PTS = [Point(500 + i * 125, 910) for i in range(9)]   # 商店画面档备战栏桩
_SELL_PT = Point(75, 840)        # 商店画面档出售区桩


class _ScriptedStrategy:
    """脚本化决策源:按序弹出动作。"""

    def __init__(self, actions: list) -> None:
        self._actions = list(actions)

    def decide_shop_action(self):
        return self._actions.pop(0)


class _Ctrl:
    """截图/点击/移动/光标停车替身(op 框架经 ctx.controller 触达)。"""

    def __init__(self) -> None:
        self.clicks: list[Point] = []
        self.moves: list[Point] = []

    def screenshot(self, *a, **k):
        return (0.0, b'')

    def mouse_move(self, pos) -> None:
        self.moves.append(pos)

    def click(self, pos) -> None:
        self.clicks.append(pos)

    def park_cursor(self, *a, **k) -> None:
        pass


def _exec_port_host(monkeypatch: pytest.MonkeyPatch, strategy,
                    bench_entries: list) -> tuple:
    """端口连通锁共用离线宿主(沿 test_cw_shop_two_node_form 同式):
    入口读/决策帧/点位锚定/关店执行位全桩化;卖出拖拽的坐标解析走真
    实链(row_area_centers/sell_point/DragCwChar.drag_char 逐层捕获参数)。
    返回 (op, match, gs, 拖拽记录, 行读记录, 出售区读记录, 回执 op 名表)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_bc, cw4_gs

    match = CurrencyWarMatch(strategy, StrategySession())
    gs = cw4_gs(match.session, gold=30, level=3,
                shop=[ShopCard(x=0, name='花火', faction='?', cost=3,
                               star=1)],
                bench=bench_entries)
    match.session.strategy_state = SimpleNamespace(
        cw4_counters={}, cw4_segment_serial=0)

    class _Op:
        ctx = SimpleNamespace(current_instance_idx=1, cw_match=match,
                              controller=_Ctrl())

    def _entry_receipt(*a, **k):
        from sr_od.application.currency_war.obs.cw_observation import (
            GameStateReadReceipt,
        )
        return GameStateReadReceipt(gold=30, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=3, plane=1, round_num=2)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame',
                        lambda op_, tag, screen=None: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: [Point(50, 50)] * 5)
    monkeypatch.setattr(buy_mod, 'area_center',
                        lambda *a, **k: _LEVEL_BTN_PT)
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    # 卖出机械链参数捕获:坐标解析走真实 drag_bench_to_sell,area 读与
    # 拖拽原语逐层桩化记录(锁「执行参数直达机械层 + 域坐标权威画面」)。
    row_reads: list[tuple[str, str]] = []
    sell_reads: list[str] = []
    drags: list[tuple[Point, Point]] = []

    def _fake_rows(ctx, prefix, screen_name=prep_actions_mod.SCREEN_NAME):
        row_reads.append((prefix, screen_name))
        return list(_BENCH_PTS)

    def _fake_sell(ctx, screen_name=prep_actions_mod.SCREEN_NAME):
        sell_reads.append(screen_name)
        return _SELL_PT

    monkeypatch.setattr(prep_actions_mod, 'row_area_centers', _fake_rows)
    monkeypatch.setattr(prep_actions_mod, 'sell_point', _fake_sell)
    monkeypatch.setattr(DragCwChar, 'drag_char',
                        staticmethod(lambda op, src, dst: drags.append((src, dst))))

    import sr_od.application.currency_war.operations.cw_op.cw_prep_sell_bench_action as sell_mod  # noqa: E501
    monkeypatch.setattr(sell_mod.time, 'sleep', lambda s: None)

    close_clicks: list = []

    def _fake_close_click(self, *a, **k):
        close_clicks.append(1)
        return SimpleNamespace(is_success=True)

    monkeypatch.setattr(CwActionCloseShopOp, 'screenshot', lambda self: None)
    monkeypatch.setattr(CwActionCloseShopOp, 'round_by_find_and_click_area',
                        _fake_close_click)

    receipt_ops: list = []

    def _note_action_receipt(gs_, *, op, applied, reason='', screen='',
                             actor='', extra=None):
        receipt_ops.append(op)

    monkeypatch.setattr(gs_mod, 'note_action_receipt', _note_action_receipt)

    op = CwScreenShop(_Op.ctx)
    return op, match, gs, drags, row_reads, sell_reads, receipt_ops


def test_shop_sell_bench_executes_via_port(monkeypatch):
    """商店域发射 CwActionSellBenchParam:端口连通执行落地——拖拽两端
    按商店画面档解析(screen_name 绑定),容器槽位置空,访问账计数,
    非终结 round_wait 续循环。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_bc

    strategy = _ScriptedStrategy([
        CwActionSellBenchParam(bench_idx=0, expect='灵砂'),
        CwActionCloseShopParam(),
    ])
    op, match, gs, drags, row_reads, sell_reads, receipt_ops = \
        _exec_port_host(monkeypatch, strategy, bench_entries=[cw4_bc('灵砂')])
    assert op.observe().is_success

    rr = op.act()

    assert not rr.is_success and rr.status is None, \
        '卖出非终结 → round_wait(帧不消费)'
    assert drags == [(_BENCH_PTS[0], _SELL_PT)], \
        '拖拽参数直达机械层:源 = 商店画面档备战栏槽 1 中心,目标 = 出售区'
    assert row_reads == [('备战栏', SHOP_SCREEN_NAME)], \
        '备战栏坐标按商店画面档解析(域坐标权威画面绑定)'
    assert sell_reads == [SHOP_SCREEN_NAME], \
        '出售区坐标按商店画面档解析'
    assert op.ledger.total_sell == 1, '访问账卖出计数(发出即记账)'
    _slots = gs.bench.value.slots
    assert _slots[0].kind == 'empty', '容器上报对账:卖出槽位置空'
    assert 'CwActionSellBenchParam' in receipt_ops, '商店动作回执行在册'

    assert op.act().is_success, '后续关店终结照常'


def test_shop_level_up_executes_batch_clicks(monkeypatch):
    """商店域发射 CwActionLevelUpShopParam(clicks 整批):端口连通执行
    落地——连点击数 = clicks(整批接口店内可发),金按上报口径 −cost×
    clicks,访问账计数,非终结 round_wait 续循环。"""
    strategy = _ScriptedStrategy([
        CwActionLevelUpShopParam(cost=4, clicks=3),
        CwActionCloseShopParam(),
    ])
    op, match, gs, drags, _row_reads, _sell_reads, receipt_ops = \
        _exec_port_host(monkeypatch, strategy, bench_entries=[])
    assert op.observe().is_success

    rr = op.act()

    assert not rr.is_success and rr.status is None, \
        '买经验非终结 → round_wait(帧不消费)'
    assert op.ctx.controller.clicks == [_LEVEL_BTN_PT] * 3, \
        '连点击数 = clicks(决策帧零介入的整批形态)'
    assert op.ctx.controller.moves, '连点前光标 settle(mouse_move)已发'
    assert op.ledger.total_xp_buy == 3, '访问账经验击数计数(发出即记账)'
    assert gs.gold.value == 30 - 4 * 3, \
        '容器上报对账:金 −cost×clicks(上报函数单点)'
    assert 'CwActionLevelUpShopParam' in receipt_ops, '商店动作回执行在册'
    assert drags == [], '买经验不涉拖拽'

    assert op.act().is_success, '后续关店终结照常'


def test_shop_sell_guard_name_mismatch_still_loud(monkeypatch):
    """守卫链照常:SellBench 名-槽不一致在商店域同辖响亮暴露
    (guard_proposal_vs_expected 先于执行端口,端口接线不改守卫辖面)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_bc

    strategy = _ScriptedStrategy([
        CwActionSellBenchParam(bench_idx=0, expect='别人'),
    ])
    op, match, gs, _drags, _row_reads, _sell_reads, _receipt_ops = \
        _exec_port_host(monkeypatch, strategy, bench_entries=[cw4_bc('灵砂')])
    assert op.observe().is_success

    with pytest.raises(AssertionError, match='名-槽不一致'):
        op.act()
