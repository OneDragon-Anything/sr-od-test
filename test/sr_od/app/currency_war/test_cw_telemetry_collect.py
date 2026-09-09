"""test_cw_telemetry_collect 主题锁(L3 观测/遥测面硬砍批后残存锁)。

残存判据(用户裁定硬砍批:默认砍,三保留条=①读取正确性喂决策 ②事故耦合
③schema/注册表守卫):结算读链(parse_settlement_round/ recovered 残卷门/
monotonic gate)、补给 detour 失败安全(防备战屏盲点卡身)、位面情报接管链
(obs→session 写入正确性)、观测异常不阻塞对局。

砍除面墓碑(锁面→砍因,一次性记录不展开):
- recorder 字段 roundtrip 群(supply_pick/source/choice/sell_income 落盘形
  + enabled/no_run_id 门控)→ JSON 逐字段形状锁,纯遥测写端零决策面;
- 接线在场烟雾群(handler_wiring_in_source×7/single_helper_no_copy/
  shop_sell_branch/supply_branch/takeover 注册表在场)→ 源码含某串;
- query_economy 卖回格 4 测 → L3 读视图输出格式锁;
- detour happy-path/once-per-node/miss-abort 3 测 → 遥测采集面行为,
  失败安全语义由残存 2 测辖定;
- 屏面真值 gate 等值支/败局指纹去重/非败局门/recovered 反向 3 支 →
  语料卫生补支,失守不产生行为分叉;
- supply 合成行 2 测 → 遥测行数据质量;
- w414 金币明细全段 14 测 → parse_settlement_gold_detail 生产端零消费
  (全仓 grep 证实,仅本文件引用),锁对象为死函数。
"""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.obs.cw_settlement_obs import parse_settlement_round
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.telemetry import recorder, state
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


# ==================== 补给 detour 失败安全(残存 2 测) ====================
# (墓碑:detour happy-path 快照/once-per-node/返回 miss 静默放弃 3 测砍于
#  硬砍批——采集成功面是纯遥测;残存 2 测辖「失败不卡身/不假完成」。)


class _NoSleepTime:
    """time 替身:sleep 只记账不真睡,其余属性透传真 time 模块。

    detour 的等待常量(TO_PREP_SETTLE_S 等)是为真机画面过渡设计的;离线桩里
    mock 画面点击后瞬间就位,这些 sleep 纯属空等(两用例曾各烧 10.5s)。
    同 test harness fast_sleep 的思路,但 run_supply_node 模块自持
    ``import time``,fast_sleep 替换的是 operation.py 的 time,覆盖不到这里。
    """

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        """记录被跳过的等待时长(诊断用),不真正睡眠。"""
        self.skipped.append(seconds)

    def __getattr__(self, name: str):
        return getattr(time, name)


def _make_supply_op(monkeypatch):
    """构 CwScreenSupplyNode 桩(__new__ 绕过 op __init__;只喂 detour 依赖面)。

    返回 (op, decision_captured)。round_by_find_and_click_area 全成功;
    截图恒为同一伪帧(离线桩);read_game_state 桩出确定值。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as m,
    )

    # 离线桩空等消除:模块自持 import time,换 no-sleep 替身(类 docstring 详因)
    monkeypatch.setattr(m, 'time', _NoSleepTime())

    decision_captured: list[dict] = []

    monkeypatch.setattr(recorder, 'record_decision',
                        lambda state, target_comp='', candidate_scores=None,
                        eval_breakdown=None, actions=None, gold_point=True,
                        extra=None: decision_captured.append(
                            {'target_comp': target_comp,
                             'actions': list(actions or []),
                             'gold_point': gold_point,
                             'extra': dict(extra or {})}))
    monkeypatch.setattr(m, 'read_game_state',
                        lambda ctx, screen, **kw: GameState(hp=88, gold=66,
                                                            plane=1,
                                                            round_num=5))
    op = m.CwScreenSupplyNode.__new__(m.CwScreenSupplyNode)
    fake_screen = object()
    match = SimpleNamespace(session=SimpleNamespace(target_comp=None,
                                                    last_state=None))
    op.ctx = SimpleNamespace(cw_match=match, current_instance_idx=1)
    op.screenshot = lambda: fake_screen   # noqa: ANN001  实例属性遮蔽方法
    click_log: list[tuple] = []
    op._click_log = click_log
    op.round_by_find_and_click_area = (
        lambda screen, sn, an, **kw: (click_log.append((sn, an)) or
                                      SimpleNamespace(is_success=True)))
    # 重进后 overlay 判定(_in_node 内部用):桩成命中(离线无画面)
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=True))
    # OCR 文本兜底枪(重进序列末位):桩离线无画面
    op.round_by_ocr_and_click = (
        lambda screen, text, **kw: SimpleNamespace(is_success=False))
    return op, decision_captured


def test_do_action_skips_pick_when_detour_fails(monkeypatch) -> None:
    """重进失败 → 本轮不做任何选择动作(防备战屏盲点卡身),交下轮重试 detour。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node as m,
    )

    op, captured = _make_supply_op(monkeypatch)

    def _fail_reenter(screen, sn, an, **kw):
        # 「返回备战界面」成功;备战侧「按钮-返回补给阶段」恒失败 → 重进不通
        if an == '按钮-返回备战界面':
            return SimpleNamespace(is_success=True)
        return SimpleNamespace(is_success=False)
    op.round_by_find_and_click_area = _fail_reenter
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=False))

    pick_calls: list = []
    monkeypatch.setattr(m, 'read_supply_options',
                        lambda ctx, screen: pick_calls.append(screen) or [])
    monkeypatch.setattr(state, 'consume_last_supply_pick', lambda: None)
    op._do_action(object())
    assert len([r for r in captured
                if r['extra'].get('phase') == 'supply_detour']) == 1
    assert pick_calls == []   # 未进入选择读帧(detour 失败即止)


def test_detour_failure_not_marked_retry_next_round(monkeypatch) -> None:
    """失败不落标记(宁可见 FAIL bail 不带病假完成):session 无 _supply_detour_done,
    下轮 _should_supply_detour 仍 True → 重试整个 detour;OCR 文本兜底点击已尝试。"""

    op, captured = _make_supply_op(monkeypatch)
    ocr_clicks: list[str] = []
    op.round_by_find_and_click_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(
            is_success=(an == '按钮-返回备战界面')))
    op.round_by_find_area = (
        lambda screen, sn, an, **kw: SimpleNamespace(is_success=False))
    op.round_by_ocr_and_click = (
        lambda screen, text, **kw: (ocr_clicks.append(text) or
                                    SimpleNamespace(is_success=False)))
    match = op.ctx.cw_match
    assert op._supply_detour_collect(match) is False
    assert not getattr(match.session, '_supply_detour_done', False), \
        '失败不得落标记(否则下轮跳过 detour 直接在错误画面选择)'
    assert op._should_supply_detour(match) is True   # 下轮重试 detour
    assert ocr_clicks == ['返回补给阶段']   # OCR 文本兜底枪已打(重试序列末位)


# ==================== 结算屏真值 + 败局页 telemetry-only 边界 ====================


class _OcrItem(SimpleNamespace):
    """OCR 结果桩(.data 文本 + .y 坐标,fp 指纹需要)。"""


def _w239_p2r1_loss_outcome_make_loop(monkeypatch, *, ocr_texts: list[str], read_phase: tuple[int, int],
               killed=None, hp_confidence: float = 0.0):
    """构 cw_screen_battle_wait 桩:bypass __init__,喂 _record_round_outcome/_record_loss_page 依赖面。

    (W971 05-battle §1 P4:结算链自 cw_loop 收编 CwScreenBattleWait,本桩随迁。)
    read_phase_round 桩返 ``read_phase``(模拟 last-known 缓存态);read_round_outcome
    桩按入参回显 plane/round 并可控 killed/hp_confidence;cw_telemetry 写端 monkeypatch
    捕获(自动还原);观察半写入面(ADR-0583 拆两半)以真实 StrategySession 承载,
    断言 telemetry-only 面零写入(performance.history/pending 槽均空)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )
    from sr_od.application.currency_war.strategies.impl.cw_strategy import (
        StrategySession,
    )

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '') -> None:
        captured.append({'outcome': outcome, 'source': source})

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(recorder, 'record_exogenous', lambda *a, **k: None)
    monkeypatch.setattr(bwo, 'read_phase_round', lambda ctx, screen: read_phase)

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=0, hp_confidence=hp_confidence,
                            killed=killed)

    monkeypatch.setattr(bwo, 'read_round_outcome', _fake_read_outcome)

    class _Op(bwo.CwScreenBattleWait):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = bwo.SettlementState(
                run_start_ts=time.monotonic() - 9999.0,   # 超宽限:非残留
                is_new_match=True,
                battle_ts=object())   # 哨兵值:断言 telemetry-only 不清它
            self._unknown_streak = 0
            # 观察半直写面(ADR-0583):真实 StrategySession 承载
            #(performance/pending_round_outcomes 等字段齐备,零桩面特判)
            _sess = StrategySession()
            _sess.last_state = GameState()
            state_of(_sess)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=_sess,
                    strategy=SimpleNamespace(),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None, color_range=None,
                    crop_first=False: [
                        _OcrItem(data=t, y=i * 20) for i, t in enumerate(ocr_texts)]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Op(), captured


# ===== 屏面真值单调门(事故耦合:replay 实锤错归属 run_20260825_145641) =====


def test_win_settlement_screen_truth_overrides_stale_p1_cache(monkeypatch) -> None:
    """P1→P2 过场后首结算:缓存停在 (1,9),屏面「2-1」→ 行落 plane=2/r1。

    即 replay 实锤的错归属形态(run_20260825_145641:node_type=普通战斗 落在 (1,9),
    P1r9 恒为 boss 不可能)——屏面真值在读时点,不依赖过场后是否有帧读到「2-1」。
    """
    op, captured = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 9),
        ocr_texts=['挑战成功', '2-1', '战斗', '小队生命值78i', '继续挑战'],
        hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].plane == 2
    assert captured[0]['outcome'].round_num == 1


def test_screen_truth_behind_cache_rejected(monkeypatch) -> None:
    """屏面解析落后 last-known(OCR 假阳形态,如把 '1-4' 误读在 (1,6) 帧)→ 拒,保缓存。

    单调门镜像 read_phase_round 的单调守卫;位面前进 (1,9)→(2,1) 合法不受影响
    (t 序 (2-1)*9+1=10 > 9,见 test_win_settlement_screen_truth_overrides_stale_p1_cache)。
    """
    op, captured = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(1, 6),
        ocr_texts=['挑战成功', '1-4', '战斗'], hp_confidence=1.0)
    op._record_round_outcome(screen=None)
    assert captured[0]['outcome'].round_num == 6


# ===== 败局页 telemetry-only 补录(ADR-0583 拆两半边界) =====


def test_loss_page_records_row_telemetry_only(monkeypatch) -> None:
    """败局页(killed=False)→ 落一行 source='loss_page';零策略/循环状态面。

    断言面(ADR-0583 拆两半语义重推):telemetry-only 不写观察半
    (performance.history 空/last_streak 不动/last_hp 不写)也不写策略半
    (pending 槽空)→ prep 行为面零变更;_battle_ts 不清(ADR-0250 战斗
    窗口维持 1f 原语义)、_last_outcome_t 不写(killed 兜底对比链不受新
    路径扰动)。
    """
    op, captured = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1),
        ocr_texts=['挑战结束', '2-1', '战斗', '-22', '挑战进度', '前往结算'],
        killed=False)
    _battle_ts_sentinel = op._st.battle_ts
    op._record_loss_page(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'loss_page'
    o = captured[0]['outcome']
    assert o.plane == 2 and o.round_num == 1
    assert o.killed is False
    _sess = op.ctx.cw_match.session
    assert len(_sess.performance.history) == 0         # 观察半零写入
    assert _sess.last_streak == 0                      # streak 不动(缺省)
    assert _sess.last_hp is None
    assert _sess.pending_round_outcomes == []          # 策略半不入槽
    assert op._st.battle_ts is _battle_ts_sentinel     # ADR-0250 窗口语义不变
    assert op._st.last_outcome_t is None               # killed 对比链不扰动
    assert op._st.last_outcome_hp is None              # summary 真值链不扰动


def test_loss_page_failures_do_not_raise(monkeypatch) -> None:
    """OCR 服务抛错 → 补录吞异常不阻塞对局(观测为辅)。"""
    op, captured = _w239_p2r1_loss_outcome_make_loop(
        monkeypatch, read_phase=(2, 1), ocr_texts=[], killed=False)
    def _boom(**kw):
        raise RuntimeError('ocr down')
    op.ctx.ocr_service.get_ocr_result_list = _boom
    op._record_loss_page(screen=None)   # 不抛
    assert captured == []


# ==================== parse_settlement_round 读链 + recovered 残卷门 ====================
# (墓碑:recovered 门反向 3 支(第二结算不标/新局不标/超宽限不标)与 source 字段
#  roundtrip 砍于硬砍批——反向支=语料标记卫生,失守不改变 bot 行为;
#  残卷正向门(事故耦合)+ 屏面解析不可用时的兜底行为由下方 2 测辖定。)


def test_parse_round_from_header_window() -> None:
    """头部后 5 token 窗口内的「X-Y」→ (plane, round)(W23 实录 token 形态)。"""
    texts = ['挑战结束', '1-6', '战斗', '小队生命值78i', '继续挑战']
    assert parse_settlement_round(texts) == (1, 6)


def test_parse_round_glued_and_noise_forms() -> None:
    """粘连噪声形态('1-3X点' 实锤)可解析;boss 屏 '1-9首领' 同理。"""
    assert parse_settlement_round(['挑战成功', '1-3X点', '战斗']) == (1, 3)
    assert parse_settlement_round(['挑战结束', '1-9首领']) == (1, 9)


def test_parse_round_rejects_out_of_range_and_far_digits() -> None:
    """值域外(plane>3/round=0)与窗口外数字对 → None(不冒认)。"""
    assert parse_settlement_round(['挑战成功', '4-2']) is None
    assert parse_settlement_round(['挑战成功', '1-0']) is None
    # 窗口外(头部后 >5 token)的数字对不取
    assert parse_settlement_round(
        ['挑战成功'] + ['x'] * 6 + ['1-6']) is None
    # 无头部词 → None(非结算屏帧不解析)
    assert parse_settlement_round(['1-6', '战斗']) is None
    # 紧邻数字的粘连('11-6')不取子串
    assert parse_settlement_round(['挑战成功', '11-6']) is None


class _w28_outcome_write_defects_OcrItem(SimpleNamespace):
    """OCR 结果桩(只需 .data)。"""


def _w28_outcome_write_defects_make_loop(monkeypatch, *, new_match: bool, elapsed_s: float,
               ocr_texts: list[str], first_seen: bool = False):
    """构 cw_screen_battle_wait 桩:bypass __init__,只喂 _record_round_outcome 依赖面。

    (W971 05-battle §1 P4:结算链收编 CwScreenBattleWait,本桩随迁。)
    read_phase_round 桩返 (1,1)(模拟 relaunch 后缓存已 reset 的兜底值);
    read_round_outcome 桩返高置信 RoundOutcome(hp 真值来自结算屏);
    recorder.record_outcome / record_exogenous monkeypatch 捕获(自动还原,
    不写真实 .debug)。
    """
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )

    captured: list[dict] = []

    def _fake_record_outcome(outcome, source: str = '', supply_pick=None) -> None:
        captured.append({'outcome': outcome, 'source': source,
                         'supply_pick': supply_pick})

    monkeypatch.setattr(recorder, 'record_outcome', _fake_record_outcome)
    monkeypatch.setattr(recorder, 'record_exogenous',
                        lambda *a, **k: None)
    monkeypatch.setattr(bwo, 'read_phase_round', lambda ctx, screen: (1, 1))

    def _fake_read_outcome(ctx, screen, *, plane, round_num, comp_tag,
                           node_type='普通战斗'):
        return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                            comp_tag=comp_tag, hp_after=78, hp_confidence=1.0)

    monkeypatch.setattr(bwo, 'read_round_outcome', _fake_read_outcome)

    class _Op(bwo.CwScreenBattleWait):
        def __init__(self):  # noqa: D107  桩:bypass SrOperation.__init__
            self._st = bwo.SettlementState(
                run_start_ts=time.monotonic() - elapsed_s,
                is_new_match=new_match,
                first_settlement_seen=first_seen)
            self._unknown_streak = 0
            # 观察半直写面(ADR-0583):真实 StrategySession 承载(字段齐备)
            from sr_od.application.currency_war.strategies.impl.cw_strategy import (
                StrategySession as _SS,
            )
            _sess = _SS()
            _sess.last_state = GameState()
            state_of(_sess)
            self.ctx = SimpleNamespace(
                cw_match=SimpleNamespace(
                    session=_sess,
                    strategy=SimpleNamespace(),
                ),
                ocr_service=SimpleNamespace(
                    get_ocr_result_list=lambda image, rect=None, color_range=None,
                    crop_first=False: [_w28_outcome_write_defects_OcrItem(data=t) for t in ocr_texts]),
            )
            self._cw_config = None

        def round_by_ocr(self, screen, word, **kw):
            return SimpleNamespace(is_success=False)

        def round_by_find_area(self, screen, screen_name, area_name, **kw):
            return SimpleNamespace(is_success=False)   # T#103:boss 判定改 area(标识-首领)

    return _Op(), captured


def test_relaunch_residual_tagged_recovered_and_round_fixed(monkeypatch) -> None:
    """启动宽限内首见结算屏:source='recovered' + round 按屏面「1-6」校正。"""
    op, captured = _w28_outcome_write_defects_make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战结束', '1-6', '战斗', '小队生命值78i', '继续挑战'])
    op._record_round_outcome(screen=None)
    assert len(captured) == 1
    assert captured[0]['source'] == 'recovered'
    assert captured[0]['outcome'].round_num == 6
    assert captured[0]['outcome'].plane == 1


def test_residual_unparseable_still_tagged(monkeypatch) -> None:
    """屏面「X-Y」解析不出(OCR 噪声)→ round 保底不抛,但 recovered 标记仍在
    (修法 b 兜底:脏行可识别,训练侧可剔)。"""
    op, captured = _w28_outcome_write_defects_make_loop(
        monkeypatch, new_match=True, elapsed_s=1.0,
        ocr_texts=['挑战结束', '??', '战斗'])
    op._record_round_outcome(screen=None)
    assert captured[0]['source'] == 'recovered'
    assert captured[0]['outcome'].round_num == 1


# ==================== 位面情报接管链(obs→session 写入正确性) ====================
# (墓碑:test_takeover_op_discoverable_by_registry 砍于硬砍批——单点注册表在场,
#  非键集守卫;op 行为面由下方 harness 锁辖定。)

def _make_op(test_context: SrTestContext, monkeypatch, phases: list[dict]):
    """构造被测 op(fixture 控制器注入 + 看门狗),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    class _Watched(WatchdogOperationMixin, CwEntryPlaneIntel):
        pass

    fc = FixtureController(test_context)
    fc.set_phases(phases)
    # fixture 控制器注入 ctx(is_game_window_ready=True 绕过开游戏前置链)
    monkeypatch.setattr(test_context, 'controller', fc)
    return _Watched(test_context), fc


def _exec(op) -> OperationResult:
    with fast_sleep():
        return op.execute()


def test_gate_fail_fast_on_lobby_frame(test_context: SrTestContext, monkeypatch) -> None:
    """锁②:大厅帧 → 快速 fail 并存证,零点击、不碰 session。"""
    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(session=SimpleNamespace(briefing_bosses=[], briefing_affixes=[])),
        raising=False)
    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-大厅', 'lobby')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert not res.success, f'大厅帧应 fail,得成功:{res.status}'
    assert fc.recorded_clicks == [], '入口门 fail 不应产生任何点击'
    sess = test_context.cw_match.session
    assert sess.briefing_bosses == [], 'fail 路径不得改写 session'


def test_skip_when_session_has_truth(test_context: SrTestContext, monkeypatch) -> None:
    """锁③:briefing_bosses 非空 → 直通 success,CwScreenPlaneIntel 不被实例化。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as cpi_mod,
    )

    truth = ['巨鹿', None, '绘师']

    def _must_not_run(*a, **k):
        raise AssertionError('session 已有真值时不应委派实采子 op')

    monkeypatch.setattr(cpi_mod, 'CwScreenPlaneIntel', _must_not_run)
    sess = SimpleNamespace(briefing_bosses=list(truth), briefing_affixes=['已有'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', ['残留'], raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)
    assert res.success, f'跳过路径应 success,得 {res.status!r}'
    assert fc.recorded_clicks == [], '跳过路径应为零点击'
    assert sess.briefing_bosses == truth, '跳过路径不得改写已有真值'
    assert getattr(test_context, 'cw_plane_bosses', None) is None, (
        '真值保护路径应清残留中转池(防跨局判空泄漏)'
    )
    # 跳过分支池空且 session 有真值 → 清残留也属消费收尾,但跳过节点不改池:
    # 本锁只钉「session 真值未被触碰」,池语义由写回节点测试覆盖。


class _FakeIntel:
    """CwScreenPlaneIntel 替身:直接产中转池结果(壳层测试不重跑 SIFT 链)。"""

    produced_bosses: list | None = ['巨鹿', None, '绘师']
    produced_affixes: list | None = ['财富造物主', '敌人难度108']

    def __init__(self, ctx, start_plane: int = 0) -> None:
        self.ctx = ctx
        self.start_plane = start_plane   # 接管链接线参数(时序修正批,透传即可)

    def execute(self) -> OperationResult:
        self.ctx.cw_plane_bosses = list(self.produced_bosses)
        self.ctx.cw_plane_affixes = list(self.produced_affixes)
        return OperationResult(success=True, status='位面情报采集')


def test_success_writes_session_and_clears_pools(test_context: SrTestContext, monkeypatch) -> None:
    """锁④主链:保位 3 槽落 session、affixes 仅空时写、消费后清池。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CwScreenPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success, f'成功链应 success,得 {res.status!r}'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师'], (
        f'bosses 应保位写 3 槽(None 原样占槽),得 {sess.briefing_bosses}'
    )
    assert sess.briefing_affixes == ['财富造物主', '敌人难度108'], (
        f'affixes 仅空时应写入,得 {sess.briefing_affixes}'
    )
    assert test_context.cw_plane_bosses is None, '消费后 boss 中转池应清空'
    assert test_context.cw_plane_affixes is None, '消费后词缀中转池应清空'


def test_success_does_not_overwrite_existing_affixes(test_context: SrTestContext, monkeypatch) -> None:
    """锁④伴生:session.briefing_affixes 已有值时随采词缀**不覆写**(与
    cw_loop 内联块「仅简报未供时」口径一致)。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CwScreenPlaneIntel', _FakeIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=['简报先到'])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_affixes', None, raising=False)

    op, _fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert res.success
    assert sess.briefing_affixes == ['简报先到'], '已有词缀不得被随采覆写'
    assert sess.briefing_bosses == ['巨鹿', None, '绘师']


class _EmptyIntel(_FakeIntel):
    """成功但不产出的异常替身(中转池保持 None)。"""

    def execute(self) -> OperationResult:
        return OperationResult(success=True, status='位面情报采集(空)')


def test_no_output_leaves_session_untouched(test_context: SrTestContext, monkeypatch) -> None:
    """锁⑤:子 op 称成功但中转池空 → fail,session 保持空表不被覆写成假成功。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_plane_intel as cpi_mod,
    )

    monkeypatch.setattr(cpi_mod, 'CwScreenPlaneIntel', _EmptyIntel)
    sess = SimpleNamespace(briefing_bosses=[], briefing_affixes=[])
    monkeypatch.setattr(
        test_context, 'cw_match', SimpleNamespace(session=sess), raising=False)
    monkeypatch.setattr(test_context, 'cw_plane_bosses', None, raising=False)

    op, fc = _make_op(test_context, monkeypatch, [{'frame': ('货币战争-备战', '攻略已应用')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert not res.success, f'无产出应 fail,得 {res.status!r}'
    assert sess.briefing_bosses == [], '无产出不得写 session'


# ---------------------------------------------------------------------------
# fixture 真帧锚:存档引用帧仍是组装画面单一源(id_mark 在屏可判)
# ---------------------------------------------------------------------------


def test_w277_reference_frame_ids_plane_detail(test_context: SrTestContext) -> None:
    """锁⑦:存档引用帧(screens png 存档)上「标识-位面详情标题」id_mark
    必命中——组装画面锚漂移即本 op 入口判定失效的前置信号。"""
    import cv2
    import numpy as np

    p = (Path(__file__).parents[4] / 'screens' / '货币战争-位面详情'
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB

    from sr_od.application.currency_war.operations.cw_entry.cw_entry_plane_intel import (
        CwEntryPlaneIntel,
    )

    op = CwEntryPlaneIntel(test_context)
    res = op.round_by_find_area(img_rgb, '货币战争-位面详情', '标识-位面详情标题',
                                crop_first=False)
    assert res.is_success, 'W277 引用帧上位面详情 id_mark 应命中(真实 OCR)'
