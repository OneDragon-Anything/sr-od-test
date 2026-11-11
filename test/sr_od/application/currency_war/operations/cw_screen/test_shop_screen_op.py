"""商店画面 op(CwScreenShop)与动作 op 执行链行为测试。

主题文件按机制分段(原六文件按机制归并;各段 docstring 保留出处):

1. **两 node 规范形态**(段机解体为观察 node + 决策动作 node;
   op-layer §1.1):观察 node 每访问恰一次读 + 段首簿记;决策动作 node
   round_wait 单动作循环(全动作统一路径零拦截);「终结不入 decisions
   行」契约;未观察跳过链(留痕后照常执行关店)。
2. **执行端口接入调用**(本文件锁面申报,
   纯执行层零策略判据):商店域发射 SellBench/LevelUp 可执行,执行参数
   直达机械层(拖拽两端按商店画面档解析/买经验整批连点),发出即记账 +
   状态容器上报对账一致,守卫链照常(名-槽不一致响亮暴露)。
3. **关店机械口 payload 清场**(T-40 并入面;病理 run_20260918_063249
   停局链:上轮买后 payload 跨轮残留 → 下轮开店帧实读失配安灯停局):
   关店两出口(点击已发/幂等已关)同清 payload;重开重洗采新对照;当轮
   买投影回归。
4. **防御建核漏斗 + 段首锚定门**(返工批):cw_match 缺席
   防御分支直调漏斗(种子/复位/遥测三行为差消除 + 局外不复用);A 层
   段首锚定门(牌位点表全 5 槽判据 + 升级钮/刷新钮缺失臂)。
5. **费用徽章解析**(银狼LV.999 升费形态;倍数体系 = 3^(星级−1)):
   resolve_cost_star 升费/普通回归/缺读兜底三面。
6. **刷价 Field 读口**(2026-09-15 04:37 实机停局事故:容器化后刷价
   属性是 Field 载体,``or`` 恒取 Field → TypeError 崩整局):未观察
   记基价不炸 / 现值记现值。

驱动方式 = 真类实例 + 节点函数直驱,读链/点击链/拖拽链桩化(先例 =
test_screen_two_node_family),零真实副作用。
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import Area

import sr_od.application.currency_war.kernel.cw_game_state as gs_mod
import sr_od.application.currency_war.kernel.cw_vocab as vocab_mod
import sr_od.application.currency_war.operations.cw_op.cw_close_shop_action as close_mod
import sr_od.application.currency_war.operations.cw_screen.cw_screen_shop as buy_mod
import sr_od.application.currency_war.prep_actions as prep_actions_mod
from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_economy import REFRESH_COST_BASE
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
    ShopPayload,
    ShopSlot,
    game_state_of,
    shop_payload_content_cards,
)
from sr_od.application.currency_war.kernel.cw_obs_core import (
    SHOP_SCREEN_NAME,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    CwActionRefreshShopParam,
    CwActionSellBenchParam,
    ShopCard,
)
from sr_od.application.currency_war.obs.cw_observation import (
    COST_SOURCE_ROSTER_FALLBACK,
    resolve_cost_star,
)
from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
    CwActionCloseShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_refresh_shop_action import (
    CwActionRefreshShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
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
from sr_od.application.currency_war.telemetry import state as tel_state

_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                        mode='compute', group_id='act:CwScreenShop@1')
_OBS_SIG = ChannelSig(family='obs', actor='cw_observation',
                      screen='货币战争-备战-开商店', mode='read')


# ============================================================
# 段 1:两 node 规范形态(观察 node + 决策动作 node)
# ============================================================


class _ScriptedStrategy:
    """脚本化决策源:按序弹出动作(记录咨询次数供断言)。"""

    def __init__(self, actions: list) -> None:
        self._actions = list(actions)
        self.calls = 0

    def decide_shop_action(self):
        self.calls += 1
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


def _shop_host(monkeypatch: pytest.MonkeyPatch, strategy) -> tuple:
    """两 node 形态测试共用离线宿主:入口读/决策帧/点位锚定/关店执行位
    点击全桩化,状态容器在屏 payload 槽1 = 花火。返回 (op, match, gs,
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
                        lambda ctx: [Point(50, 50)] * 5)   # 定长 5 槽(段首全 5 槽门)
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    # 预算披露桩化(真实现经 mandate state_of 对异型状态对象每局全新创建覆写,
    # 会换掉宿主的 SimpleNamespace 状态载体;与本测试无关)。
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
    def _note_action_receipt(gs_, *, op, reason='', screen='',
                             actor='', extra=None):
        receipt_ops.append(op)

    monkeypatch.setattr(gs_mod, 'note_action_receipt', _note_action_receipt)

    op = CwScreenShop(_Op.ctx)
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
        'CwScreenShopObs 镜像挂实例属性'
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
         '自身承担);买牌回执簿已登记')


def test_act_buy_card_slot_out_of_range_raises_no_receipt(monkeypatch):
    """槽号越界经 act 直驱 = op 内守卫断言 AssertionError 原样上抛
    (terminal-fail-status:参数违法由 op 自判,商店 visit 环零映射表)
    + 回执不产行(QA 例外从句:异常终止的分派不产行,回执义务由失败
    运行整体证据承接)。"""
    card6 = ShopCard(x=6, slot=6, name='卡六', faction='?', cost=3, star=1)
    cards = [ShopSlot(kind='content', card=_card(f'卡{i + 1}', i + 1))
             for i in range(5)]
    cards.append(ShopSlot(kind='content', card=card6))
    strategy = _ScriptedStrategy([CwActionBuyCardParam(card=card6)])
    op, match, gs, *_ = _shop_host(monkeypatch, strategy)
    # 店面换 6 槽 payload(槽号-点表不一致 = 越界受阻形态的可达构造)
    gs.write_logic(gs.shop, ShopPayload(cards=cards, refresh_probs={}),
                   produced_by='test', sig=_LOGIC_SIG)
    reasons: list[tuple[str, str]] = []

    def _capture(gs_, *, op, reason='', screen='', actor='', extra=None):
        reasons.append((op, reason))

    monkeypatch.setattr(gs_mod, 'note_action_receipt', _capture)
    assert op.observe().is_success

    with pytest.raises(AssertionError) as ei:
        op.act()

    assert '槽号-点表不一致' in str(ei.value), '守卫断言消息透传'
    assert reasons == [], '异常终止的分派不产行(回执零写)'


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
    assert 'shop_skipped_unobserved' in rows, '留痕分键暴露'


# ============================================================
# 段 2:执行端口接入调用(纯执行层,零策略判据)
# ============================================================

_LEVEL_BTN_PT = Point(123, 456)   # 购买经验按钮识别标志(观察 node area 桩值)
_BENCH_PTS = [Point(500 + i * 125, 910) for i in range(9)]   # 商店画面档备战栏桩
_SELL_PT = Point(75, 840)        # 商店画面档出售区桩


def _exec_port_host(monkeypatch: pytest.MonkeyPatch, strategy,
                    bench_entries: list) -> tuple:
    """端口连通测试共用离线宿主(沿本文件两 node 形态段 _shop_host 同式):
    入口读/决策帧/点位锚定/关店执行位全桩化;卖出拖拽的坐标解析走真
    实链(row_area_centers/sell_point/DragCwChar.drag_char 逐层捕获参数)。
    返回 (op, match, gs, 拖拽记录, 行读记录, 出售区读记录, 回执 op 名表)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_gs

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
    # 拖拽原语逐层桩化记录(校验「执行参数直达机械层 + 域坐标权威画面」)。
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

    def _note_action_receipt(gs_, *, op, reason='', screen='',
                             actor='', extra=None):
        receipt_ops.append(op)

    monkeypatch.setattr(gs_mod, 'note_action_receipt', _note_action_receipt)

    op = CwScreenShop(_Op.ctx)
    return op, match, gs, drags, row_reads, sell_reads, receipt_ops


def test_shop_sell_bench_executes_via_port(monkeypatch):
    """商店域发射 CwActionSellBenchParam:端口连通执行落地——拖拽两端
    按商店画面档解析(screen_name 绑定),状态容器槽位置空,访问账计数,
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
    assert _slots[0].kind == 'empty', '状态容器上报对账:卖出槽位置空'
    assert 'CwActionSellBenchParam' in receipt_ops, '商店动作回执簿已登记'

    assert op.act().is_success, '后续关店终结照常'


def test_shop_sell_guard_name_mismatch_still_loud(monkeypatch):
    """守卫链照常:SellBench 名-槽不一致在商店域同辖响亮暴露
    (guard_proposal_vs_expected 先于执行端口,端口接入调用不改守卫辖面)。"""
    from test.sr_od.application.currency_war._cw_helpers import cw4_bc

    strategy = _ScriptedStrategy([
        CwActionSellBenchParam(bench_idx=0, expect='别人'),
    ])
    op, match, gs, _drags, _row_reads, _sell_reads, _receipt_ops = \
        _exec_port_host(monkeypatch, strategy, bench_entries=[cw4_bc('灵砂')])
    assert op.observe().is_success

    with pytest.raises(AssertionError, match='名-槽不一致'):
        op.act()


# ============================================================
# 段 3:关店机械口 payload 清场(T-40 并入面;病理 run_20260918_063249)
# 现役修法 = 关店执行位并入 CwActionCloseShopOp 执行体:帧上找
# 「按钮-收起」miss = 店已关(幂等)/ 命中 = 点击 + 固定等待,两出口
# 同调清场上报(report_action_close_shop_param 的 leave_screen 离屏写)。
# ============================================================


def _card(name: str, slot: int = 1) -> ShopCard:
    return ShopCard(x=slot, slot=slot, name=name, faction='?', cost=3,
                    star=1)


def _payload(names: list[str]) -> ShopPayload:
    """5 槽定长 payload:names 依序填 content 槽,余槽 empty。"""
    cards = [ShopSlot(kind='content', card=_card(n, i + 1))
             for i, n in enumerate(names)]
    cards += [ShopSlot(kind='empty') for _ in range(5 - len(cards))]
    return ShopPayload(cards=cards, refresh_probs={})


class _CloseFakeCtx:
    """动作 op 构造所需最小 ctx 面(cw_match = 状态容器 session 宿主)。"""

    def __init__(self, session: StrategySession) -> None:
        self.cw_match = SimpleNamespace(session=session)
        self.run_context = None


def _close_op(session: StrategySession, click_found: bool,
              monkeypatch: pytest.MonkeyPatch) -> CwActionCloseShopOp:
    """真类实例 + 点击判定桩化:「按钮-收起」按剧本命中/缺席;
    关店动画等待走模块 time 桩。"""
    op = CwActionCloseShopOp(_CloseFakeCtx(session), CwActionCloseShopParam(),
                             env=SimpleNamespace())
    monkeypatch.setattr(op, 'screenshot', lambda: None)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda frame, s, a: Area(click_found))
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s_: None)
    return op


def _session_with_shop(names: list[str], gold: int | None = 30):
    """带在屏 payload 的状态容器 session(payload/gold 经 logic 直写喂入)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.shop, _payload(names), produced_by='test',
                   sig=_LOGIC_SIG)
    if gold is not None:
        gs.write_logic(gs.gold, gold, produced_by='test', sig=_LOGIC_SIG)
    return session, gs


def test_close_shop_click_clears_stale_buy_payload(monkeypatch):
    """点击已发出口:买投影后 payload 在屏 → 关店动作执行体点击发出 →
    payload 置 None(evidence=left_screen 校验清场写端身份);回执
    reason=''(已正常发出,真实 kernel 写路径)。"""
    session, gs = _session_with_shop(['希儿', '花火', '黑塔', '丹恒', '停云'])
    report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿')), _LOGIC_SIG,
        executed=ShopActionExecuted(bought_count=1))
    assert gs.shop.value is not None, '前置:买后 payload 在屏(当轮事实)'
    assert len(shop_payload_content_cards(gs.shop.value)) == 4, \
        '前置:买走 1 张余 4 content(槽空置换语义)'

    rr = _close_op(session, click_found=True, monkeypatch=monkeypatch).run()

    assert rr.is_success, '终结动作两出口均 round_success(机械交回)'
    assert gs.shop.value is None, '关店点击后 payload 离屏置 None(跨轮残留根除)'
    assert gs.shop.source == 'observation'
    assert gs.shop.evidence == 'left_screen', '清场写端身份 = leave_screen 口'
    assert gs.receipts.value == [{'op': 'CwActionCloseShopOp', 'reason': '',
                                  'screen': SHOP_SCREEN_NAME}], \
        '已发出出口回执零受阻码(纯动作事实 shape)'


def test_close_shop_idempotent_exit_clears_stale_payload(monkeypatch):
    """幂等已关出口:「收起」不在(店已关)+ 残留 payload 同样清——
    幂等修复回归(已关残留同样陈旧);round_success 维持(良性簿记事实
    不进 fail 防线)+ 回执 reason=定位缺失(按钮-收起)(零观察 op 报
    机械事实不报业务态,真实 kernel 写路径)。"""
    session, gs = _session_with_shop(['黑塔'])
    assert gs.shop.value is not None

    rr = _close_op(session, click_found=False, monkeypatch=monkeypatch).run()

    assert rr.is_success, '幂等已关 = 无动作可发,回执后终结交回'
    assert gs.shop.value is None, '已关出口同样清残留(幂等修复)'
    assert gs.receipts.value == [
        {'op': 'CwActionCloseShopOp', 'reason': '定位缺失(按钮-收起)',
         'screen': SHOP_SCREEN_NAME}], \
        '定位缺失出口回执受阻码(每动作 op 恰一条回执行)'


def test_reopen_reshuffle_adopts_new_wave_without_mismatch(monkeypatch):
    """重开重洗采新:上半对照 = 残留 logic payload 遇新波观察 → 失配
    路由命中(capture 替身,病理形态入测试);下半 = 清场后同观察零失配、
    采新波。"""
    calls: list[dict] = []

    def _capture(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(gs_mod, '_route_logic_mismatch', _capture)
    fresh = _payload(['卡A', '卡B', '卡C', '卡D', '卡E'])

    # 上半(病理对照):上轮残影 payload + 新波观察 → 失配路由命中
    session, gs = _session_with_shop(['黑塔'])
    gs.observe(gs.shop, fresh, evidence='shop_new_wave', sig=_OBS_SIG)
    assert len(calls) == 1 and calls[0]['field_name'] == 'shop', \
        '对照:残留 logic payload 遇新波实读路由失配(安灯停局病理形态)'

    # 下半(修法):同残影起点 → 关店清场 → 新波观察零失配采新
    calls.clear()
    session2, gs2 = _session_with_shop(['黑塔'])
    _close_op(session2, click_found=True, monkeypatch=monkeypatch).run()
    gs2.observe(gs2.shop, fresh, evidence='shop_new_wave', sig=_OBS_SIG)
    assert calls == [], '清场后新波观察零失配(修法移除病理形态)'
    assert gs2.shop.value == fresh and gs2.shop.source == 'observation', \
        '开店帧新波采新(payload = 实读,source=observation)'


def test_buy_projection_regression_within_visit(monkeypatch):
    """当轮买投影回归:买投影语义逐位不变(买走槽空置换+gold −单价+
    写端身份),清场只随关店动作发生,买后 close 前 payload 在屏。"""
    session, gs = _session_with_shop(['希儿', '花火', '黑塔', '丹恒', '停云'])

    report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿')), _LOGIC_SIG,
        executed=ShopActionExecuted(bought_count=1))

    assert gs.gold.value == 27, 'gold: 30 −单价 3 = 27(买投影照常)'
    assert gs.shop.value is not None, \
        '当轮买后 payload 在屏(清场未提前触发,决策循环在屏前置保持)'
    assert len(shop_payload_content_cards(gs.shop.value)) == 4, \
        '买走槽空置换(5 槽定长,余 4 content)'
    assert gs.shop.evidence == 'proj_buy_payload', '买投影写端身份保持'

    _close_op(session, click_found=True, monkeypatch=monkeypatch).run()
    assert gs.shop.value is None, '关店动作时点才清场'


# ============================================================
# 段 4:防御建核漏斗 + 段首锚定门(返工批)
# ============================================================


def _run_observe_node(ctx: SimpleNamespace):
    """观察 node 直驱(薄壳退役承接):构造真类实例跑观察 node,返回
    轮次结果(防御路径测试只辖观察 node 段,决策循环不入测试面)。"""
    op = buy_mod.CwScreenShop(ctx)
    return op.observe()


def _defense_host(monkeypatch: pytest.MonkeyPatch, *,
                  strategy_seed: int | None) -> SimpleNamespace:
    """替身函数的接缝(stub seam) = 观察 node 顶部消费面:config 工厂(seed 可参)/
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
    播种;局状态容器建立点以遥测 current_run_id 为 provider 触发 journal
    装配;策略器/状态同源接入调用与漏斗同款。"""
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
    # 状态同源接入调用(漏斗 §2.6 过渡桥同款):session 键位状态 = 策略器状态
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
    状态容器再新建(discard+establish 同款衔接),session 全量重建非复用——
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


# ---- A 层段首锚定门(设计稿 buy_cards §2.2-A:牌位点表全 5 槽判据,
# 与升级钮/刷新钮缺失检查同款纪律;定长 5 槽结构无合法缺槽形态)----


def _anchor_host(monkeypatch: pytest.MonkeyPatch, *, click_pts: list,
                 area_centers: dict | None = None) -> SimpleNamespace:
    """A 层段首锚定门宿主:点表可参(静默缩短形态可演),area_center
    按 area 名替身(缺省恒缺);其余沿 _defense_host(防御建核触发,
    ctx.cw_match 缺席)。"""
    centers = dict(area_centers or {})

    def _area_center(_ctx, name, *a, **k):
        return centers.get(name)

    monkeypatch.setattr(
        buy_mod, 'CurrencyWarConfig',
        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                    strategy_seed=None))
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: click_pts)
    monkeypatch.setattr(buy_mod, 'area_center', _area_center)

    class _Ctl:
        """截图/停车替身(op 框架经 ctx.controller 触达;沿本文件 _Ctl)。"""

        def screenshot(self, *a, **k):
            return (0.0, b'')

        def park_cursor(self, *a, **k) -> None:
            pass

    return SimpleNamespace(
        current_instance_idx=1, cw_match=None, controller=_Ctl(),
        cw_selected_difficulty=None,
        currency_war_strategy_plugin_dirs=[])


def test_segment_head_short_card_points_fail_with_area_names(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A 层·牌位臂:点表静默缩短(缺 商店牌-2/-5)→ 访问不开始
    round_fail,逐槽复查收缺失 area 名——部分缺失按位取点 = 错槽,
    禁兜底(判据 = 全 5 槽在,非「非空」)。"""
    centers = {f'商店牌-{i}': Point(50, 50) for i in (1, 3, 4)}
    rr = _run_observe_node(_anchor_host(
        monkeypatch, click_pts=[Point(50, 50)] * 3, area_centers=centers))

    assert rr is not None and rr.is_success is False, \
        '全 5 槽判据:缺失即访问不开始'
    status = rr.status or ''
    assert '商店牌-2' in status and '商店牌-5' in status, \
        '逐槽复查缺失 area 名进 fail 信息'
    assert 'area 缺失' in status, '形态与升级钮/刷新钮行一致'


def test_segment_head_level_button_missing_fails(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A 层·升级钮臂:全 5 槽在而升级钮缺失 → round_fail 带钮名
    (存量纪律回归基准)。"""
    centers = {f'商店牌-{i}': Point(50, 50) for i in range(1, 6)}
    rr = _run_observe_node(_anchor_host(
        monkeypatch, click_pts=[Point(50, 50)] * 5, area_centers=centers))

    assert rr is not None and rr.is_success is False
    assert buy_mod.BUY_EXP_AREA in (rr.status or ''), '信息带升级钮 area 名'


def test_segment_head_refresh_button_missing_fails(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A 层·刷新钮臂:牌位/升级钮在而刷新钮缺失 → round_fail 带钮名。"""
    centers = {f'商店牌-{i}': Point(50, 50) for i in range(1, 6)}
    centers[buy_mod.BUY_EXP_AREA] = Point(60, 60)
    rr = _run_observe_node(_anchor_host(
        monkeypatch, click_pts=[Point(50, 50)] * 5, area_centers=centers))

    assert rr is not None and rr.is_success is False
    assert '按钮-刷新' in (rr.status or ''), '信息带刷新钮 area 名'


def test_segment_head_all_five_slots_proceed_to_access(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A 层·通过臂:全 5 槽 ∧ 升级钮 ∧ 刷新钮齐备 → 越过段首门正常
    进入访问(入口观察恰一次读,观察 node round_success)。"""
    centers = {f'商店牌-{i}': Point(50, 50) for i in range(1, 6)}
    centers[buy_mod.BUY_EXP_AREA] = Point(60, 60)
    centers['按钮-刷新'] = Point(70, 70)
    ctx = _anchor_host(monkeypatch, click_pts=[Point(50, 50)] * 5,
                       area_centers=centers)
    # 入口读链/决策帧/预算披露桩化(全桩沿本文件 _shop_host 同式;
    # 真实状态容器由防御建核漏斗建立)。
    reads: list = []

    def _entry_receipt(*a, **k):
        reads.append(1)
        from sr_od.application.currency_war.obs.cw_observation import (
            GameStateReadReceipt,
        )
        return GameStateReadReceipt(gold=30, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=3, plane=1, round_num=2)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod.CwScreenShop, 'park_cursor',
                        lambda self, **k: None)
    monkeypatch.setattr(gs_mod, 'ensure_journal_assembly', lambda _p: None)
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    rr = _run_observe_node(ctx)

    assert rr is not None and rr.is_success, '三识别标志齐备 = 访问正常开始'
    assert reads == [1], '入口观察恰一次读'


# ============================================================
# 段 5:费用徽章 → (费用, 星级) 解析(银狼LV.999 升费后基准费 ≠
# 注册表起始费形态;银狼升星记账批设计件。倍数体系 = 3^(星级−1):
# 1★×1 / 2★×3 / 3★×9,cw_observation._SHOP_COST_MULT_TO_STAR)
# ============================================================


def test_lv999_tier_badge_resolves():
    """升费形态:档=4 时 badge=4 → 1★/4费、badge=12 → 2★/12费。

    修复前除数 = 注册表起始费 3:badge=4/12 均非 3 的 1/3/9 倍 →
    roster_fallback 系统性误记 3费1★(设计 §1.2 症状 4)。"""
    assert resolve_cost_star(4, 4) == (4, 1, 'badge')
    assert resolve_cost_star(12, 4) == (12, 2, 'badge')


def test_plain_char_multiplier_regression():
    """普通角色回归:起始费 3 的 1/2★ 徽章 = 3/9(除数换语义后零行为差)。"""
    assert resolve_cost_star(3, 3) == (3, 1, 'badge')
    assert resolve_cost_star(9, 3) == (9, 2, 'badge')


def test_missing_and_nonintegral_fallback():
    """缺读/疑误读 → 基准费兜底记 1★(roster_fallback 留证语义不变)。"""
    assert resolve_cost_star(None, 4) == (4, 1, COST_SOURCE_ROSTER_FALLBACK)
    assert resolve_cost_star(8, 4) == (4, 1, COST_SOURCE_ROSTER_FALLBACK)


# ============================================================
# 段 6:刷价 Field 读口(2026-09-15 04:37 实机停局事故;ADR-0456
# 实付恒基价的记账口径不变)
# ============================================================


class _FeeController:
    def click(self, pos) -> None:
        pass


class _FeeCtx:
    def __init__(self) -> None:
        self.controller = _FeeController()
        self.cw_match = None
        self.run_context = None
        self.screen_loader = None


class _FeeOp:
    """execute 所需最小 op 面(零截图桩:动作 op 零读屏,若回归出读屏
    调用即在缺属性处响亮失败)。"""

    def __init__(self) -> None:
        self.ctx = _FeeCtx()


def _fee_env(state, ledger: ShopVisitLedger) -> ShopExecEnv:
    return ShopExecEnv(
        op=_FeeOp(), match=None, config=None, click_pts=[],
        level_btn=Point(0, 0), refresh_btn=Point(1603, 479),
        ledger=ledger, state=state)


def test_refresh_fee_unobserved_field_falls_back_to_base(monkeypatch):
    """事故本形:刷价 Field 未观察(None)→ 记基价,不再 TypeError。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)   # 新状态容器:shop_refresh_cost 未观察
    ledger = ShopVisitLedger()

    _env_ = _fee_env(state, ledger)
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == REFRESH_COST_BASE
    assert ledger.total_refresh == 1


def test_refresh_fee_observed_value_is_used(monkeypatch):
    """刷价 Field 现值在场 → 记现值(读现值意图不因修法丢失)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)
    state.observe(state.shop_refresh_cost, 3,
                  sig=ChannelSig(family='obs', actor='cw_observation'))
    ledger = ShopVisitLedger()

    _env_ = _fee_env(state, ledger)
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == 3


def test_refresh_fee_ledger_equals_gold_deduction(monkeypatch):
    """T-21 分支 3 锁 10 等值断言:上报已进的帧内,op 花销账累加值 ≡ 金账
    扣减值——两侧同式同源(状态容器刷价 ``or`` 基价 + 同一 free_refresh_left
    谓词),镜像漂移在本断言暴露(spend 3 ≡ 30−27)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)
    state.observe(state.gold, 30, sig=_OBS_SIG)
    state.observe(state.shop_refresh_cost, 3, sig=_OBS_SIG)
    ledger = ShopVisitLedger()

    _env_ = _fee_env(state, ledger)
    _env_.op.ctx.cw_match = SimpleNamespace(session=session)   # 接通上报
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == 3, '花销账累加状态容器刷价'
    assert state.gold.value == 27, '金账扣同值(上报函数状态容器直读)'
    assert 30 - state.gold.value == ledger.spend_executed, '等值不变式'


def test_refresh_free_frame_zero_both_sides(monkeypatch):
    """T-21 分支 3 锁 11 op 半边:免费帧(free_refresh_left > 0)花销账
    累加 0 且金账零扣——两侧同谓词恒等,无例外(修复免费帧花销虚记
    既有缺陷:旧形态无条件累加状态容器价,免费刷实扣 0)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)
    state.observe(state.gold, 30, sig=_OBS_SIG)
    state.observe(state.shop_refresh_cost, 2, sig=_OBS_SIG)
    state.write_logic(state.free_refresh_left, 1, produced_by='test-seed',
                      sig=_LOGIC_SIG)
    ledger = ShopVisitLedger()

    _env_ = _fee_env(state, ledger)
    _env_.op.ctx.cw_match = SimpleNamespace(session=session)   # 接通上报
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == 0, '免费帧花销账累加 0'
    assert state.gold.value == 30, '免费帧金账零扣'
    assert state.free_refresh_left.value == 0, '免费分支扣减照常(1→0)'
