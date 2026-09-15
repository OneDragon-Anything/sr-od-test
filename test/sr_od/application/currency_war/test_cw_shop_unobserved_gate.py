"""T-268 tracked 观察状态行为锁(用户裁定「字段增加观察状态」)。

设计:tracked 主账带观察态(ExecState.tracked_observed)——接管/重置/
账失效置「未观察」,备战环 heavy 观察(observe_full → reconcile_tracking)
bench 侧屏幕真值写回成功置「已观察」;商店开时发现未观察 → 策略门
(flow.decide_shop_action)返回恒可用终结 CloseShop → 编排壳收店 → 外循环
重判自然落回备战节点完成锚定 → 再进店。店内零原地重建(原 T-251 读屏
重建出口/单向阀门与 T-230 恢复路由随守卫退役同批移除,守卫本体 =
guard_expected_vs_tracked 一并退役:对账唯一合法时点 = 观察边界
kernel cw_reconcile,规则文本 = flow/screen_op.md §2.3/§4)。

锁的六件事:
1. 未观察门:tracked_observed=False 时 decide_shop_action 返回 CloseShop,
   mandate 决策核不可达(零咨询);
2. 缺省可信/锚定放行:缺省 True(正常新局空账 = 屏幕真空真值,不经接管
   路径的 sim/离线入口不受误伤);observed=True 时门放行,决策照常咨询;
3. 锚定置位:reconcile_tracking bench 侧屏幕真值写回成功 → True;
   失败形态(deployed-only 写回/双空读守卫)不置位 = 保持未观察;
4. 接管置位:cw_loop._mark_session_resumed → False(接管检测确认点);
5. 未观察访问跳过留痕:run_buy_waves 收到策略关店 → 缺陷台账分键
   shop_skipped_unobserved 显影 + 连续计数 +1,visit 以 (None, ledger)
   正常收工(跳过非失败,交回外循环重判);
6. 连续跳过熔断:计数达 SHOP_UNOBSERVED_SKIP_LIMIT → (round_fail, None)
   显式停(锚定失败出口,禁无限静默重试);观察态正常访问段顶复位计数。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopPayload,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import CloseShop
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.telemetry import defects

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入(测试零真实副作用)+ 留调用记录供显影断言。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _write_shop_payload(session) -> None:
    """容器在屏空牌面(策略门在屏前置 bs.shop.value 非空的满足面)。"""
    bs = board_state_of(session)
    bs.write_logic(bs.shop, ShopPayload(cards=[], refresh_probs={}),
                   produced_by='test', sig=_SIG)


# ===== 锁1/锁2 策略门单元(flow.decide_shop_action)=====

def _mandate_strategy(monkeypatch):
    """生产策略实例(mandate_v1.bridge;decide_shop_action 不被覆写,
    走 flow.py 门)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )
    strategy = MandateV1Strategy()
    # 门后内务(方向帧消费/镜像遥测)与本锁无关,桩成 no-op 保单测面窄。
    monkeypatch.setattr(strategy, '_consume_shop_direction_frame',
                        lambda session: None)
    monkeypatch.setattr(strategy, 'write_shop_mirrors',
                        lambda bs, session: None)
    return strategy


def test_unobserved_gate_returns_close_shop_without_consulting_core(
        monkeypatch):
    """锁1 未观察门:返回 CloseShop,决策核不可达(零咨询)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )

    def _core_should_not_run(*a, **k):
        raise AssertionError('未观察门应先行返回,mandate 决策核不可达')

    monkeypatch.setattr(mandate_shop, 'decide_shop_action',
                        _core_should_not_run)
    session = StrategySession()
    _write_shop_payload(session)
    exec_state_of(session).tracked_observed = False   # 接管/失效后形态

    act = _mandate_strategy(monkeypatch).decide_shop_action(
        session, SimpleNamespace())

    assert isinstance(act, CloseShop)


def test_default_observed_and_gate_passes_through_to_core(monkeypatch):
    """锁2 缺省可信 + 锚定放行:缺省 True;observed=True 门放行决策核。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )
    session = StrategySession()
    assert exec_state_of(session).tracked_observed is True   # 缺省可信
    _write_shop_payload(session)
    _sentinel = SimpleNamespace(marker='core-consulted')

    def _core(bs, sess, config, registry=None):
        return _sentinel

    monkeypatch.setattr(mandate_shop, 'decide_shop_action', _core)

    act = _mandate_strategy(monkeypatch).decide_shop_action(
        session, SimpleNamespace())

    assert act is _sentinel


# ===== 锁3 锚定置位(kernel reconcile_tracking 写回点)=====

def test_reconcile_bench_writeback_marks_observed():
    """bench 侧屏幕真值写回成功 → observed=True(唯一生产置位点)。"""
    session = StrategySession()
    exec_state_of(session).tracked_observed = False   # 接管后未观察

    ok = _reconcile(session, [BenchChar(slot=1, char_id='花火', star=1)], [])

    assert ok is True
    assert exec_state_of(session).tracked_observed is True
    assert [(b.char_id, b.star) for b in
            exec_state_of(session).tracked_bench_chars if b is not None] \
        == [('花火', 1)]


def test_reconcile_failed_anchor_keeps_unobserved():
    """失败形态不置位:deployed-only 写回(bench 未读)与双空读守卫均保持
    未观察——账未锚定,商店访问继续走关店重判链。"""
    # deployed-only(bench=None):函数写回 deployed 返 True,但 bench 侧
    # 零写 = 主账未锚定。
    s1 = StrategySession()
    exec_state_of(s1).tracked_observed = False
    assert _reconcile(s1, None, []) is True
    assert exec_state_of(s1).tracked_observed is False
    # 双空读守卫(双空读 + 前值非空 = 疑过渡帧保旧):返 False 不置位。
    s2 = StrategySession()
    exec_state_of(s2).tracked_observed = False
    exec_state_of(s2).tracked_bench_chars = [
        BenchChar(slot=1, char_id='花火', star=1)]
    assert _reconcile(s2, [], []) is False
    assert exec_state_of(s2).tracked_observed is False


def _reconcile(session, bench, deployed) -> bool:
    from sr_od.application.currency_war.kernel.cw_reconcile import (
        reconcile_tracking,
    )
    return reconcile_tracking(session, bench, deployed, screen=None,
                              source='test')


# ===== 锁4 接管置位(cw_loop 恢复检测确认点)=====

def test_takeover_marks_tracked_unobserved():
    """接管检测确认点 → tracked_observed=False(原 cw_resume_seed_anchor
    待办旗标的观察态承接面)。"""
    session = StrategySession()
    assert exec_state_of(session).tracked_observed is True
    _stub_self = SimpleNamespace(ctx=SimpleNamespace(cw_match=SimpleNamespace(
        session=session)))

    CwLoop._mark_session_resumed(_stub_self)

    assert exec_state_of(session).cw_resumed_match is True
    assert exec_state_of(session).tracked_observed is False


# ===== 锁5/锁6 访问级流锁(run_buy_waves CloseShop 出口)=====

def _run_buy_waves_unobserved_host(monkeypatch, tmp_path, counters, *,
                                   tracked_observed: bool):
    """未观察跳过流锁的离线宿主(替身面沿 T-230 恢复锁宿主同式)。

    构造 = 容器在屏空牌面 + 观察态按参;策略 = 生产 MandateV1Strategy
    (真实门路径:未观察 → CloseShop;观察态用例传 Idle 关店策略)。
    返回 (run_buy_waves 结果元组, session)。
    """
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards as buy_mod
    from sr_od.application.currency_war.obs.cw_observation import (
        GameStateReadReceipt,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        CurrencyWarMatch,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        assembly as assembly_mod,
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

    if tracked_observed:
        class _IdleStrategy:
            """观察态正常关店替身:门放行后的决策核返回 CloseShop。"""

            def decide_shop_action(self, session, config):
                return CloseShop()
        strategy = _IdleStrategy()
    else:
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strategy = MandateV1Strategy()   # 真实门:未观察 → CloseShop

    match = CurrencyWarMatch(strategy, StrategySession())
    match.session.strategy_state = SimpleNamespace(
        cw4_counters=counters, cw4_segment_serial=0)
    exec_state_of(match.session).tracked_observed = tracked_observed
    _write_shop_payload(match.session)

    class _Op:
        """离线宿主替身:run_buy_waves 消费面仅 ctx/screenshot/park_cursor。"""

        ctx = SimpleNamespace(current_instance_idx=1)

        def screenshot(self) -> bytes:
            return b''

        def park_cursor(self, after_wait: float = 0.0) -> None:
            pass

        def save_screenshot(self, prefix: str = '') -> str:
            return ''

        def round_fail(self, status: str = None, data=None, wait: float = None):
            return SimpleNamespace(status=status, is_success=False)

    def _entry_receipt(*a, **k) -> GameStateReadReceipt:
        return GameStateReadReceipt(gold=10, gold_readable=True, hp=100,
                                    hp_readable=True, hp_trusted=True,
                                    level=5, plane=1, round_num=8)

    monkeypatch.setattr(buy_mod, 'read_game_state', _entry_receipt)
    monkeypatch.setattr(buy_mod, 'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(buy_mod, 'shop_card_click_points', lambda ctx: [])
    monkeypatch.setattr(buy_mod, 'area_center', lambda *a, **k: (0, 0))
    monkeypatch.setattr(buy_mod.time, 'sleep', lambda s: None)
    monkeypatch.setattr(buy_mod, 'CurrencyWarConfig',
                        lambda idx: SimpleNamespace(strategy_id='mandate_v1',
                                                    ev_arm=''))
    monkeypatch.setattr(assembly_mod, 'disclose_budget_at_shop_frame',
                        lambda *a, **k: None)

    result = buy_mod.run_buy_waves(_Op(), match)
    return result, match.session


def test_unobserved_visit_skips_with_defect_and_streak(monkeypatch, tmp_path):
    """锁5 未观察访问跳过:策略关店 → 缺陷分键显影 + 连续计数 +1,visit
    以 (None, ledger) 正常收工(交回外循环重判,跳过非失败)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {}

    (rr, ledger), _session = _run_buy_waves_unobserved_host(
        monkeypatch, tmp_path, counters, tracked_observed=False)

    assert rr is None and ledger is not None   # 正常收工交回外循环
    assert counters['shop_skipped_unobserved_streak'] == 1   # 计数落位
    assert any(kind == 'shop_skipped_unobserved'
               for _s, kind, _e, _o in rows)   # 分键显影(防静默)


def test_unobserved_skip_streak_limit_stops(monkeypatch, tmp_path):
    """锁6 连续跳过熔断:计数达上限 → (round_fail, None) 显式停
    (锚定失败出口,禁无限静默重试)。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {'shop_skipped_unobserved_streak': 1}   # 已跳过一次

    (rr, ledger), _session = _run_buy_waves_unobserved_host(
        monkeypatch, tmp_path, counters, tracked_observed=False)

    assert rr is not None and not rr.is_success   # round_fail 单次停
    assert ledger is None   # 停机支形态
    assert counters['shop_skipped_unobserved_streak'] == 2
    assert any(kind == 'shop_skipped_unobserved_stop'
               for _s, kind, _e, _o in rows)   # 熔断分键显影


def test_observed_visit_resets_streak_and_no_defect(monkeypatch, tmp_path):
    """观察态正常访问:段顶复位计数,关店零跳过感知零台账行。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {'shop_skipped_unobserved_streak': 1}   # 前次残留

    (rr, ledger), _session = _run_buy_waves_unobserved_host(
        monkeypatch, tmp_path, counters, tracked_observed=True)

    assert rr is None and ledger is not None   # 正常收工
    assert counters['shop_skipped_unobserved_streak'] == 0   # 段顶复位
    assert rows == []   # 零台账行(正常关店零感知)
