"""tracked 观察状态行为测试(用户裁定「观察状态落 game state 字段,
策略消费只走 game state」)。

设计:状态容器字段 ``GameState.tracked_account_observed``(三态:None=从未写
= 缺省可信,正常新局/sim 不经失效事件零误伤;False=显式失效未观察,值
不可消费;True=备战环 heavy 观察 reconcile 屏幕真值写回成功=已锚定)。
接管(cw_loop 接管检测确认点)写 False;商店开遇未观察 → 策略门
(flow.decide_shop_action,判定单一源 = kernel tracked_unobserved)返回恒
可用终结 CwActionCloseShopParam → 商店画面 op 执行收店 → 外循环重判落回备战节点锚定 → 再进店,
店内零原地重建。mandate_v1._tracking_view(tracking 优先 + snapshot 静默
回退)已随三次修正删除——策略禁读执行侧簿记,消费口只有 game state
(空账混同根因由此类型/架构层封死)。原读屏重建出口/单向
阀门与恢复路由测试随守卫退役同批移除;守卫本体 guard_expected_vs_
tracked 亦退役:对账唯一合法时点 = 观察边界 kernel cw_reconcile,规则
文本 = flow/screen_op.md §2.3/§4。

测试的七件事:
1. 未观察门:状态容器观察态 False → decide_shop_action 返回 CwActionCloseShopParam,决策
   核不可达(零咨询);
2. 缺省可信/已观察放行:字段从未写(None,缺省)与已锚定(True)均放行
   决策核——空表/未写不能冒充未观察(空账混同反向测试);
3. 锚定置位:reconcile_tracking bench 侧屏幕真值写回成功 → True;
   失败形态(deployed-only 写回/双空读守卫)不置位 = 保持未观察;
4. 接管置位:cw_loop._invalidate_tracked_on_takeover → False(接管检测确认点);
5. 未观察访问跳过留痕:商店画面 op 收到策略关店 → 缺陷台账分键
   shop_skipped_unobserved 暴露 + 连续计数 +1,visit 以 (None, ledger)
   正常收工(跳过非失败,交回外循环重判);
6. 连续跳过熔断:计数达 SHOP_UNOBSERVED_SKIP_LIMIT → (round_fail, None)
   显式停(锚定失败出口,禁无限静默重试);
7. 观察态正常访问段顶复位计数、零跳过感知。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    ShopPayload,
    Unit,
    game_state_of,
    tracked_unobserved,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionCloseShopParam
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.telemetry import defects


@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生(3.2):主域种子经 observe 覆盖开局种子(logic_rand 通道)
    会产预期内 logic_rand_outcome 行入进程级缓冲——前后双清,防跨用例
    顺序依赖红。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    consume_defect_sink()
    yield
    consume_defect_sink()

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入(测试零真实副作用)+ 留调用记录供暴露断言。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _write_shop_payload(session) -> None:
    """状态容器在屏空牌面(策略门在屏前置 gs.shop.value 非空的满足面)。"""
    gs = game_state_of(session)
    gs.write_logic(gs.shop, ShopPayload(cards=[], refresh_probs={}),
                   produced_by='test', sig=_SIG)


def _mark_unobserved(session) -> None:
    """状态容器观察态字段写 False(生产同形 = 接管检测写点)。"""
    gs = game_state_of(session)
    gs.write_logic(gs.tracked_account_observed, False,
                   produced_by='test', evidence='takeover_invalidation',
                   sig=_SIG)


# ===== 测试1/测试2 策略门单元(flow.decide_shop_action)=====

def _mandate_strategy(monkeypatch, session):
    """生产策略实例(mandate_v1.bridge;decide_shop_action 不被覆写,
    走 flow.py 门)。gs = 测试 session 状态容器单例(终态零参口:决策输入
    一律 self.gs 自取)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    strategy = MandateV1Strategy(
        game_state_of(session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入
    # 门后内务(方向帧消费/镜像遥测)与本测试无关,桩成 no-op 保单测面窄。
    monkeypatch.setattr(strategy, '_consume_shop_direction_frame',
                        lambda: None)
    monkeypatch.setattr(strategy, 'write_shop_mirrors',
                        lambda gs, session: None)
    return strategy


def test_unobserved_gate_returns_close_shop_without_consulting_core(
        monkeypatch):
    """测试1 未观察门:观察态 False → 返回 CwActionCloseShopParam,决策核不可达。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )

    def _core_should_not_run(*a, **k):
        raise AssertionError('未观察门应先行返回,mandate 决策核不可达')

    monkeypatch.setattr(mandate_shop, 'decide_shop_action',
                        _core_should_not_run)
    session = StrategySession()
    _write_shop_payload(session)
    _mark_unobserved(session)
    assert tracked_unobserved(session)

    act = _mandate_strategy(monkeypatch, session).decide_shop_action()

    assert isinstance(act, CwActionCloseShopParam)


def test_default_and_anchored_states_pass_gate_to_core(monkeypatch):
    """测试2 缺省可信/已锚定放行:字段从未写(None,缺省)与 True 均放行
    决策核——席面观察态不能由「空账形态」推断(混同反向测试)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )
    _sentinel = SimpleNamespace(marker='core-consulted')

    def _core(gs, sess, config, registry=None):
        return _sentinel

    monkeypatch.setattr(mandate_shop, 'decide_shop_action', _core)

    # 缺省(字段从未写)= 缺省可信 → 门放行。
    s_default = StrategySession()
    assert game_state_of(s_default).tracked_account_observed.value is None
    assert not tracked_unobserved(s_default)
    _write_shop_payload(s_default)
    act = _mandate_strategy(monkeypatch, s_default).decide_shop_action()
    assert act is _sentinel

    # 已锚定(True)→ 门放行。
    s_anchored = StrategySession()
    _gs = game_state_of(s_anchored)
    _gs.write_logic(_gs.tracked_account_observed, True,
                    produced_by='test', sig=_SIG)
    assert not tracked_unobserved(s_anchored)
    _write_shop_payload(s_anchored)
    act = _mandate_strategy(monkeypatch, s_anchored).decide_shop_action()
    assert act is _sentinel


# ===== 测试3 锚定置位(kernel reconcile_tracking 对账成功点)=====

def test_reconcile_bench_writeback_marks_observed():
    """bench 侧屏幕真值对账成功 → 状态容器观察锚 True(唯一生产置位点;
    3.2:锚定语义 = 主域已按屏幕真值对账,置位点不变)。
    (载体 = P6 直产 BenchView;断言语义零变。)"""
    session = StrategySession()
    _mark_unobserved(session)
    assert tracked_unobserved(session)

    ok, bench_out, _ = _reconcile(session, _bench_view1('花火', 1), DeployedView())

    assert ok is True
    assert not tracked_unobserved(session)
    assert game_state_of(session).tracked_account_observed.value is True
    # director 消费门后视图(生产环式:reconcile 返回值 observe 落主域)。
    gs = game_state_of(session)
    gs.observe(gs.bench, bench_out,
               sig=ChannelSig(family='obs', actor='t', mode='read'))
    _view = gs.bench.value
    assert [(s.unit.char_id, s.unit.star)
            for s in (_view.slots if _view is not None else [])
            if s.kind == 'unit' and s.unit is not None] == [('花火', 1)]


def test_reconcile_failed_anchor_keeps_unobserved():
    """失败形态不置位:deployed-only 对账(bench 未读)与双空读守卫均
    保持原观察态——账未锚定,商店访问继续走关店重判链。"""
    # deployed-only(bench=None):函数对账 deployed 返 True,但 bench 侧
    # 零读 = 主账未锚定。
    s1 = StrategySession()
    _mark_unobserved(s1)
    assert _reconcile(s1, None, DeployedView())[0] is True
    assert tracked_unobserved(s1)
    assert game_state_of(s1).tracked_account_observed.value is False
    # 双空读守卫(双空读 + 前值非空 = 疑过渡帧保旧):返 False 不置位。
    # 前值非空的构造 = 主域 bench 先观察(3.2:前值基线 = 主域现值)。
    s2 = StrategySession()
    _mark_unobserved(s2)
    _slots = [BenchSlot(kind='unit', unit=Unit(char_id='花火', star=1))] \
        + [BenchSlot(kind='empty')] * 8
    game_state_of(s2).observe(
        game_state_of(s2).bench, BenchView(slots=_slots, capacity=9),
        sig=ChannelSig(family='obs', actor='t', mode='read'))
    assert _reconcile(s2, BenchView(), DeployedView())[0] is False
    assert tracked_unobserved(s2)


def _bench_view1(name: str, star: int) -> BenchView:
    """单占用槽视图(槽 1)构造(P6 直产读载体)。"""
    slots = [BenchSlot(kind='empty')] * 8
    return BenchView(slots=[BenchSlot(
        kind='unit', unit=Unit(char_id=name, star=star))] + slots)


def _reconcile(session, bench, deployed) -> tuple:
    from sr_od.application.currency_war.kernel.cw_reconcile import (
        reconcile_tracking,
    )
    return reconcile_tracking(session, bench, deployed, screen=None,
                              source='test')


# ===== 测试4 接管置位(cw_loop 恢复检测确认点)=====

def test_takeover_marks_tracked_unobserved():
    """接管检测确认点 → 状态容器观察态 False(显式失效事件写点)。恢复局旗标
    resumed_match 原为同口第二写端,已随零消费退役(迭代 T-8),不再断言。"""
    session = StrategySession()
    assert not tracked_unobserved(session)
    _stub_self = SimpleNamespace(ctx=SimpleNamespace(cw_match=SimpleNamespace(
        session=session)))

    CwLoop._invalidate_tracked_on_takeover(_stub_self)

    assert tracked_unobserved(session)
    assert game_state_of(session).tracked_account_observed.value is False


# ===== 测试5/测试6/测试7 访问级流测试(商店画面 op CwActionCloseShopParam 出口)=====

def _run_visit_unobserved_host(monkeypatch, tmp_path, counters, *,
                               unobserved: bool):
    """未观察跳过流测试的离线宿主(替身面沿恢复路由测试宿主同式)。

    构造 = 状态容器在屏空牌面 + 观察态按参;策略 = 生产 MandateV1Strategy
    (真实门路径:未观察 → CwActionCloseShopParam;观察态用例传 Idle 关店策略)。
    关店执行位点击桩化(统一执行路径含 CloseShop 真点击;离线零画面)。
    返回 (访问结果元组, session):正常收工 → (None, ledger),round_fail →
    (round_fail 结果, None)(出参交接契约,详设 §2.2)。驱动 = 真类实例 +
    节点函数直驱(过渡薄壳已随 3.4 退役,先例 =
    test_cw_shop_screen_op)。
    """
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_shop as buy_mod
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
        CwActionCloseShopOp,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        economy_cycle as economy_cycle_mod,
    )
    from sr_od.application.currency_war.telemetry import recorder as rec_mod
    from sr_od.application.currency_war.telemetry import state as tel_state

    # 遥测单例隔离(run 态簇 + 缺陷台账去重键;台账行落 tmp_path)。
    monkeypatch.setattr(tel_state, '_RECORDER',
                        rec_mod.TelemetryRecorder(enabled=True,
                                                  replay_dir=tmp_path))
    monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', 't268host')
    monkeypatch.setattr(tel_state, '_defect_seen', {})
    monkeypatch.setattr(tel_state, '_defect_seen_run', '')

    if unobserved:
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        _m_session = StrategySession()
        strategy = MandateV1Strategy(
        game_state_of(_m_session),
        SimpleNamespace(strategy_seed=None))   # 终态契约:构造注入   # 真实门:未观察 → CwActionCloseShopParam
    else:
        class _IdleStrategy:
            """观察态正常关店替身:门放行后的决策核返回 CwActionCloseShopParam。"""

            def decide_shop_action(self):
                return CwActionCloseShopParam()
        strategy = _IdleStrategy()

    match = CurrencyWarMatch(strategy, StrategySession())
    # 状态容器单例归一:策略 gs = match.session 状态容器(终态零参口决策读 self.gs
    # ——牌面/观察态写在 match.session 的同一状态容器上)。
    strategy.gs = game_state_of(match.session)
    match.session.strategy_state = SimpleNamespace(
        cw4_counters=counters, cw4_segment_serial=0)
    if unobserved:
        _mark_unobserved(match.session)
    _write_shop_payload(match.session)

    class _Ctl:
        """op 框架经 ctx.controller 触达的最小替身(截图/光标停车)。"""

        def screenshot(self, *a, **k):
            return (0.0, b'')

        def park_cursor(self, *a, **k) -> None:
            pass

    class _Op:
        """离线宿主替身:观察节点消费面仅 ctx(controller 截图/停车)+ 熔断
        支 save_screenshot/round_fail。"""

        ctx = SimpleNamespace(current_instance_idx=1, cw_match=match,
                              controller=_Ctl())

        def save_screenshot(self, prefix: str = '') -> str:
            return ''

        def round_fail(self, status: str = None, data=None, wait: float = None):
            return SimpleNamespace(status=status, is_success=False)

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    # 关店执行位点击桩化(「收起」命中 → 点击臂;动画等待经全局 time 桩)。
    monkeypatch.setattr(CwActionCloseShopOp, 'screenshot', lambda self: None)
    monkeypatch.setattr(CwActionCloseShopOp, 'round_by_find_and_click_area',
                        lambda self, *a, **k: SimpleNamespace(is_success=True))
    monkeypatch.setattr('time.sleep', lambda _s: None)
    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points',
                        lambda ctx: [Point(50, 50)] * 5)   # 定长 5 槽(段首全 5 槽门)
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(economy_cycle_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    from one_dragon.base.operation.operation_round_result import (
        OperationRoundResultEnum,
    )
    shell = buy_mod.CwScreenShop(_Op.ctx)
    rr = shell.observe()
    if not rr.is_success:
        return (rr, None), match.session
    while True:
        rr = shell.act()
        if rr.result == OperationRoundResultEnum.SUCCESS:
            return (None, shell.ledger), match.session
        if rr.result == OperationRoundResultEnum.WAIT:
            continue
        return (rr, None), match.session


def test_unobserved_visit_skips_with_defect_and_streak(monkeypatch, tmp_path):
    """测试5 未观察访问跳过:策略关店 → 缺陷分键暴露 + 连续计数 +1,visit
    以 (None, ledger) 正常收工(交回外循环重判,跳过非失败)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {}

    (rr, ledger), _session = _run_visit_unobserved_host(
        monkeypatch, tmp_path, counters, unobserved=True)

    assert rr is None and ledger is not None   # 正常收工交回外循环
    assert counters['shop_skipped_unobserved_streak'] == 1   # 计数落位
    assert any(kind == 'shop_skipped_unobserved'
               for _s, kind, _e, _o in rows)   # 分键暴露(防静默)


def test_unobserved_skip_streak_limit_stops(monkeypatch, tmp_path):
    """测试6 连续跳过熔断:计数达上限 → (round_fail, None) 显式停
    (锚定失败出口,禁无限静默重试)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {'shop_skipped_unobserved_streak': 1}   # 已跳过一次

    (rr, ledger), _session = _run_visit_unobserved_host(
        monkeypatch, tmp_path, counters, unobserved=True)

    assert rr is not None and not rr.is_success   # round_fail 单次停
    assert ledger is None   # 停机支形态
    assert counters['shop_skipped_unobserved_streak'] == 2
    assert any(kind == 'shop_skipped_unobserved_stop'
               for _s, kind, _e, _o in rows)   # 熔断分键暴露


def test_observed_visit_resets_streak_and_no_defect(monkeypatch, tmp_path):
    """测试7 观察态正常访问完整收工:复位连续计数,关店零跳过感知零台账行
    (复位点 = 访问完成出口,K=2 数连续因未观察跳过)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {'shop_skipped_unobserved_streak': 1}   # 前次残留

    (rr, ledger), _session = _run_visit_unobserved_host(
        monkeypatch, tmp_path, counters, unobserved=False)

    assert rr is None and ledger is not None   # 正常收工
    assert counters['shop_skipped_unobserved_streak'] == 0   # 段顶复位
    assert rows == []   # 零台账行(正常关店零感知)
