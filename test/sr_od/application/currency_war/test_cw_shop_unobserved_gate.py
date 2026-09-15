"""T-268 tracked 观察状态行为锁(用户裁定「字段取值域增加未观察态值」)。

设计:tracked_bench_chars / tracked_deployed 的取值域 = 槽位表(list,
已观察;**空表 = 已观察下的合法值**,备战席真空真值)| ``UnobservedTracked``
哨兵(未观察,值不可消费)——两者类型可分,T-251 用空账推断未观察的
混同根因被类型层封死。接管/重置/账失效写哨兵(cw_loop 接管检测确认点);
备战环 heavy 观察(observe_full → reconcile_tracking)屏幕真值写回替换
哨兵完成锚定。商店开遇未观察 → 策略门(flow.decide_shop_action)返回恒
可用终结 CloseShop → 编排壳收店 → 外循环重判落回备战节点锚定 → 再进店,
店内零原地重建(原 T-251 读屏重建出口/单向阀门与 T-230 恢复路由随守卫
退役同批移除;守卫本体 guard_expected_vs_tracked 亦退役:对账唯一合法
时点 = 观察边界 kernel cw_reconcile,规则文本 = flow/screen_op.md §2.3/§4)。

锁的八件事:
1. 未观察门:哨兵在场 → decide_shop_action 返回 CloseShop,决策核不可达
   (零咨询,_tracking_view 的 snapshot 回退同被短路在核路径之后);
2. 类型可分(T-251 根因锁):缺省/显式空表 = 已观察合法值,门放行决策
   核;同形空账 + 哨兵 = 未观察,门拦——「空」推断不可信被锁死;
3. 锚定替换:reconcile_tracking 屏幕真值写回成功 → 哨兵被实读值替换
   (两账真值);失败形态(deployed-only 写回/双空读守卫)不替换哨兵;
4. 接管写哨兵:cw_loop._mark_session_resumed → 两账字段 = 哨兵;
5. 未观察访问跳过留痕:run_buy_waves 收到策略关店 → 缺陷台账分键
   shop_skipped_unobserved 显影 + 连续计数 +1,visit 以 (None, ledger)
   正常收工(跳过非失败,交回外循环重判);
6. 连续跳过熔断:计数达 SHOP_UNOBSERVED_SKIP_LIMIT → (round_fail, None)
   显式停(锚定失败出口,禁无限静默重试);
7. 观察态(含空账)正常访问段顶复位计数、零跳过感知;
8. _tracking_view:未观察 → 不回退 snapshot、产空视图(禁粗读冒充席面);
   已观察(含空)现行为不变(空账照走 snapshot 回退)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import (
    UNOBSERVED_TRACKED,
    BenchChar,
    exec_state_of,
    tracked_unobserved,
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


def _mark_unobserved(session) -> None:
    """两账字段写「未观察」哨兵(生产同形 = 接管检测写点)。"""
    ex = exec_state_of(session)
    ex.tracked_bench_chars = UNOBSERVED_TRACKED
    ex.tracked_deployed = UNOBSERVED_TRACKED


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
    """锁1 未观察门:哨兵在场 → 返回 CloseShop,决策核不可达(零咨询)。"""
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

    act = _mandate_strategy(monkeypatch).decide_shop_action(
        session, SimpleNamespace())

    assert isinstance(act, CloseShop)


def test_observed_empty_and_nonempty_pass_gate_to_core(monkeypatch):
    """锁2 类型可分(T-251 根因锁):缺省空表 = 已观察合法值,门放行;
    同形「空」在哨兵态被拦——两者不可混同。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        shop as mandate_shop,
    )
    _sentinel = SimpleNamespace(marker='core-consulted')

    def _core(bs, sess, config, registry=None):
        return _sentinel

    monkeypatch.setattr(mandate_shop, 'decide_shop_action', _core)

    # 缺省 = 空表 = 已观察下的合法值(真空真值)→ 门放行决策核。
    s_observed_empty = StrategySession()
    assert exec_state_of(s_observed_empty).tracked_bench_chars == []
    assert not tracked_unobserved(s_observed_empty)
    _write_shop_payload(s_observed_empty)
    act = _mandate_strategy(monkeypatch).decide_shop_action(
        s_observed_empty, SimpleNamespace())
    assert act is _sentinel

    # 同形「空」+ 未观察哨兵 → 门拦(空账形态不能冒充已观察)。
    s_unobserved = StrategySession()
    _mark_unobserved(s_unobserved)
    _write_shop_payload(s_unobserved)
    act = _mandate_strategy(monkeypatch).decide_shop_action(
        s_unobserved, SimpleNamespace())
    assert isinstance(act, CloseShop)


# ===== 锁3 锚定替换(kernel reconcile_tracking 写回点)=====

def test_reconcile_writeback_replaces_unobserved_sentinel():
    """屏幕真值写回成功 → 哨兵被实读值替换(观察态退出唯一通道)。"""
    session = StrategySession()
    _mark_unobserved(session)
    assert tracked_unobserved(session)

    ok = _reconcile(session, [BenchChar(slot=1, char_id='花火', star=1)], [])

    assert ok is True
    assert not tracked_unobserved(session)
    assert [(b.char_id, b.star) for b in
            exec_state_of(session).tracked_bench_chars if b is not None] \
        == [('花火', 1)]


def test_reconcile_failed_anchor_keeps_sentinel():
    """失败形态不替换哨兵:deployed-only 写回(bench 未读)与双空读守卫
    形态的观察态语义,及真空实读的合法锚定。"""
    # deployed-only(bench=None):函数写回 deployed 返 True,但 bench 侧
    # 零写 = 主账未锚定(bench 面哨兵保留,任一面哨兵即保守为未观察)。
    s1 = StrategySession()
    _mark_unobserved(s1)
    assert _reconcile(s1, None, []) is True
    assert tracked_unobserved(s1)
    # 双空读守卫(双空读 + 前值非空 = 疑过渡帧保旧):返 False 零写。
    s2 = StrategySession()
    _mark_unobserved(s2)
    exec_state_of(s2).tracked_bench_chars = [
        BenchChar(slot=1, char_id='花火', star=1)]
    assert _reconcile(s2, [], []) is False
    # 零写断言:bench 真值原样;deployed 面哨兵从未被替换 → 任一面哨兵
    # 即保守为未观察(单一状态语义,混形态 = 锚定未完成)。
    assert [(b.char_id, b.star) for b in
            exec_state_of(s2).tracked_bench_chars if b is not None] \
        == [('花火', 1)]
    assert tracked_unobserved(s2)
    # 真空实读(bench=[] deployed=[])+ 哨兵旧账:守卫不触发(哨兵按无旧
    # 账读),空表写回替换哨兵 = 已观察下的合法真空。
    s3 = StrategySession()
    _mark_unobserved(s3)
    assert _reconcile(s3, [], []) is True
    assert not tracked_unobserved(s3)
    assert exec_state_of(s3).tracked_bench_chars == [None] * 9


def _reconcile(session, bench, deployed) -> bool:
    from sr_od.application.currency_war.kernel.cw_reconcile import (
        reconcile_tracking,
    )
    return reconcile_tracking(session, bench, deployed, screen=None,
                              source='test')


# ===== 锁4 接管写哨兵(cw_loop 恢复检测确认点)=====

def test_takeover_marks_tracked_unobserved():
    """接管检测确认点 → 两账字段 = 未观察哨兵(原 cw_resume_seed_anchor
    待办旗标的取值域态值承接面)。"""
    session = StrategySession()
    assert not tracked_unobserved(session)
    _stub_self = SimpleNamespace(ctx=SimpleNamespace(cw_match=SimpleNamespace(
        session=session)))

    CwLoop._mark_session_resumed(_stub_self)

    assert exec_state_of(session).cw_resumed_match is True
    assert tracked_unobserved(session)
    ex = exec_state_of(session)
    assert ex.tracked_bench_chars is UNOBSERVED_TRACKED
    assert ex.tracked_deployed is UNOBSERVED_TRACKED


# ===== 锁5/锁6/锁7 访问级流锁(run_buy_waves CloseShop 出口)=====

def _run_buy_waves_unobserved_host(monkeypatch, tmp_path, counters, *,
                                   unobserved: bool):
    """未观察跳过流锁的离线宿主(替身面沿 T-230 恢复锁宿主同式)。

    构造 = 容器在屏空牌面 + 两账观察态按参;策略 = 生产 MandateV1Strategy
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

    if unobserved:
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strategy = MandateV1Strategy()   # 真实门:未观察 → CloseShop
    else:
        class _IdleStrategy:
            """观察态正常关店替身:门放行后的决策核返回 CloseShop。"""

            def decide_shop_action(self, session, config):
                return CloseShop()
        strategy = _IdleStrategy()

    match = CurrencyWarMatch(strategy, StrategySession())
    match.session.strategy_state = SimpleNamespace(
        cw4_counters=counters, cw4_segment_serial=0)
    if unobserved:
        _mark_unobserved(match.session)
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
        monkeypatch, tmp_path, counters, unobserved=True)

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
        monkeypatch, tmp_path, counters, unobserved=True)

    assert rr is not None and not rr.is_success   # round_fail 单次停
    assert ledger is None   # 停机支形态
    assert counters['shop_skipped_unobserved_streak'] == 2
    assert any(kind == 'shop_skipped_unobserved_stop'
               for _s, kind, _e, _o in rows)   # 熔断分键显影


def test_observed_visit_resets_streak_and_no_defect(monkeypatch, tmp_path):
    """锁7 观察态正常访问(含空账):段顶复位计数,关店零跳过感知零台账。"""
    rows = _spy_defects(monkeypatch)
    counters: dict = {'shop_skipped_unobserved_streak': 1}   # 前次残留

    (rr, ledger), _session = _run_buy_waves_unobserved_host(
        monkeypatch, tmp_path, counters, unobserved=False)

    assert rr is None and ledger is not None   # 正常收工
    assert counters['shop_skipped_unobserved_streak'] == 0   # 段顶复位
    assert rows == []   # 零台账行(正常关店零感知)


# ===== 锁8 _tracking_view 短路(mandate_v1 assembly)=====

def test_tracking_view_unobserved_no_snapshot_fallback():
    """未观察 → 不回退 snapshot、产空视图(snapshot 粗读禁冒充席面);
    已观察空账 → 现行为不变(snapshot 回退照旧);已观察非空 → 视图来自
    tracked。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
        _tracking_view,
    )
    _snapshot = SimpleNamespace(
        bench=[BenchChar(slot=1, char_id='花火', star=1)],
        deployed=[BenchChar(slot=1, char_id='刃', star=1)])

    # 未观察:空视图(不读 snapshot)。
    s1 = StrategySession()
    _mark_unobserved(s1)
    assert _tracking_view(s1, _snapshot) == ((), ())

    # 已观察空账:现行为不变 —— 回退 snapshot 真读(R2 fresh read 补缺)。
    s2 = StrategySession()
    bench_v, dep_v = _tracking_view(s2, _snapshot)
    assert bench_v == tuple(_snapshot.bench)
    assert dep_v == tuple(d for d in _snapshot.deployed if d is not None)

    # 已观察非空:视图来自 tracked(非 snapshot)。
    s3 = StrategySession()
    ex = exec_state_of(s3)
    ex.tracked_bench_chars = [BenchChar(slot=2, char_id='艾丝妲', star=2)]
    ex.tracked_deployed = []
    bench_v, _dep = _tracking_view(s3, _snapshot)
    assert [(b.char_id, b.star) for b in bench_v] == [('艾丝妲', 2)]
