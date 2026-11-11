"""结算域行为测试(确认动作流程 / 观测覆盖度守卫 / 真值收尾 / 金面板解析 / hp 直读)。

五部分(结算屏一个域的各承担面):

- **确认动作 op 流程测试**(``CwOpSettleConfirm``;正本已退役 判据面,
  去证据门形态 2026-09-21 用户裁定)。判据 ↔ 测试对照:
  结算帧 → op → 点击即上报(logic 态恰一档)→ 按钮离场交回宿主 →
  ``test_click_reports_once_and_returns``;死点击(结算屏恒在)→ 重复
  点击重复上报被观察态门挡(零推进)+ M39 长按兜底(M39 迁入测试)→
  ``test_dead_click_gate_blocks_and_long_press_retry``;战败分支不进本 op
  (终局路径回归不变)→ ``test_defeat_branch_never_enters_settle_confirm``。
  驱动 = 真帧 fixture + 真 OCR 识别链(FixtureController 剧本推进),状态容器
  = cw4_session 旁表 + observe_node_anchor 预锚定 observation 态。
- **观测覆盖度守卫测试**(T-23;2026-09-15 局深检 §8-1 形态根治。病理:
  长战斗形态整窗零「结算观测」行实锤(run_20260915_054718 深检:488s
  主战 hp 3→0 扣血链零观测,复盘断节不可知)。修 = 战斗链收尾守卫面
  (cw_loop ``_on_battle_wait`` 出口归一点)计数留证:窗口单元 success 出口
  + 出战开窗在 + 本窗零结算观测行 → 缺陷台账 L1 行(只计数不停机))。
  校验三面:守卫判定真值表 / 结算观测行写点刷新窗标记 + 真值传导 /
  cw_loop 战斗分支接入调用消费守卫。
- **真值收尾测试**(settle_truth):金币战后真值无条件入账。背景(2026-09-18
  回滚批):节点收入由游戏侧在结算屏展示前入账,bot 无逻辑写端,账本与
  结算真值的差 = 预期边界收入而非推算 bug——经 observe 失配链则每场战斗
  必停局(全夜停局病态),吸收窗方案已回滚。现行 = 结算点无条件收尾 +
  差值台账行留证(测试依据 = GameState.settle_truth docstring)。
- **金面板解析回归测试**(T-42 读端加固批。病理:2026-09-18 两实机局
  journal+停局截图定论,胜局结算页金面板「存量 <N>」OCR 读失败率连续
  两局 100%;加固 = 识别标志词与数值分离 token 兜底;识别标志词缺失不猜)。
  定点读数(read_settle_gold_opt)= 真值入口主路径:当前版本结算布局
  无「存量」token,战后金真值挂右上角货币计数;校验其「不猜」契约与
  稳定门取末帧语义。
- **hp 直读测试**(decision_hp):标记退役后 decision_hp = gs.hp 直读——
  结算覆盖写端写入 → 读口立即反映;旧标记字段不再影响读口;可信位语义
  (observation/carried 可信,prior/logic fail-closed)。

纪律:零真实副作用;真帧 fixture 缺失 pytest.skip;纯状态容器/桩直驱部分
零识别零点击零真实 IO。
"""
from __future__ import annotations

import importlib
import time
from types import SimpleNamespace

import numpy as np
import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.application.currency_war._cw_helpers import (
    Area as _Area,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)
from test.sr_od.application.currency_war._cw_helpers import (
    run_node as _run_node,
)

import sr_od.application.currency_war.kernel.cw_game_state as gsm
import sr_od.application.currency_war.obs.cw_settlement_obs as settle_mod
from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    game_state_of,
    observe_node_anchor,
)
from sr_od.application.currency_war.kernel.cw_hp_policy import (
    decision_hp,
    hp_decision_trusted_of,
)
from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_telemetry_exit import (
    SEVERITY_L1_ALERT,
)
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_assets,
    read_settle_gold_opt,
)
from sr_od.application.currency_war.operations import cw_loop as cw_loop_mod
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm import (
    CwOpSettleConfirm,
)
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_battle_wait as bw_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
    count_settlement_obs_coverage_miss,
)
from sr_od.application.currency_war.telemetry import defects as _defects_mod

settle_confirm_mod = importlib.import_module(
    'sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm')

_FRAME = object()   # 稳定帧哨兵(桩只验判定流,不断言内容)

# ==================== 确认动作 op 流程测试 ====================

_SETTLE_FRAME = ('货币战争-结算', 'win')
_BOARD_FRAME = ('货币战争-备战', 'deployed_2star')
_SETTLE_SCREEN = '货币战争-结算'
_SETTLE_BTN = '按钮-继续挑战'


class _WatchedConfirm(WatchdogOperationMixin, CwOpSettleConfirm):
    pass


@pytest.fixture()
def fixture_controller(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def _anchored_session(test_context, monkeypatch,
                      pos: tuple[int, int] = (1, 1)):
    """锚定状态容器态:session 旁表 + node_pos 预锚定 observation(新路径
    可测前提;共存期生产会被观察态门挡,测试直接构造锚定态)。"""
    session = cw4_session()
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    gs = game_state_of(session)
    observe_node_anchor(gs, pos, trigger_screen='货币战争-备战',
                        actor='TestHost')
    return gs


def _run_execute(test_context, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def test_click_reports_once_and_returns(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """主链路测试:结算帧 → 点「继续挑战」落位 → **点击即上报**恰一档
    (logic 态)→ 按钮离场(流转落地)→ op 交回宿主。重入已流转帧:
    按钮不在场零点击零上报,直 success 交回(出口判定归宿主白名单)。"""
    if not test_context.has_screen(*_SETTLE_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_SETTLE_FRAME[0]}/{_SETTLE_FRAME[1]}.webp')
    if not test_context.has_screen(*_BOARD_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_BOARD_FRAME[0]}/{_BOARD_FRAME[1]}.webp')
    gs = _anchored_session(test_context, monkeypatch, pos=(1, 1))

    fixture_controller.set_phases([
        {
            'frame': _SETTLE_FRAME,
            'exit': ('on_click_in', _SETTLE_SCREEN, _SETTLE_BTN),
        },
        {'frame': _BOARD_FRAME},   # terminal:流转落地(按钮离场)
    ])
    op = _WatchedConfirm(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'结算确认未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 1, (
        f'点击应推进到流转落地帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area(_SETTLE_SCREEN, _SETTLE_BTN), (
        f'「继续挑战」点击落位缺失:{fixture_controller.recorded_clicks}')
    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'logic', (
        '点击即上报恰一档(logic 推进未确认态;无证据等待)')

    # 重入已流转帧:按钮不在场 → 零点击零上报,直 success 交回宿主
    fixture_controller.set_phases([{'frame': _BOARD_FRAME}])
    _clicks_before = len(fixture_controller.recorded_clicks)
    op2 = _WatchedConfirm(test_context)
    op2._init_watchdog()
    result2 = _run_execute(test_context, op2)
    assert result2.success
    assert len(fixture_controller.recorded_clicks) == _clicks_before, \
        '已流转帧不点击(按钮离场即交回)'
    assert gs.node_pos.value == (1, 2), '重复上报零推进(观察态门挡)'


def test_dead_click_gate_blocks_and_long_press_retry(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """死点击测试:结算屏恒在(点击不生效)→ 每轮重试点击 + 重复上报被
    观察态门挡(推进恰一档后零推进)+ 第 3 轮停留长按 (960,898)
    press_time=0.5(M39 迁入测试;去证据门后死点击自愈链靠宿主重分派)。"""
    if not test_context.has_screen(*_SETTLE_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_SETTLE_FRAME[0]}/{_SETTLE_FRAME[1]}.webp')
    gs = _anchored_session(test_context, monkeypatch, pos=(1, 1))

    # 长按兜底 press_time 断言面:包一层记录 kwargs(不改变推进判定)
    _press_recorder: list[tuple[float, float]] = []
    _orig_click = fixture_controller.click

    def _click_recorder(pos=None, press_time: float = 0, **kw):
        if pos is not None:
            _press_recorder.append((float(pos.x), float(press_time)))
        return _orig_click(pos, press_time=press_time, **kw)

    monkeypatch.setattr(fixture_controller, 'click', _click_recorder)

    fixture_controller.set_phases([
        {'frame': _SETTLE_FRAME},   # 无 exit:结算屏恒在(死点击形态)
    ])
    op = _WatchedConfirm(test_context)
    op.watchdog_max_rounds = 8   # 有界驱动:长按触发后即可停
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert not result.success, '死点击形态驻留不收工(看门狗截停)'
    assert gs.node_pos.value == (1, 2) and gs.node_pos.source == 'logic', (
        '首报推进恰一档后,重复上报被观察态门挡(零推进,结构挡)')
    assert fixture_controller.click_hit_area(_SETTLE_SCREEN, _SETTLE_BTN), (
        '长按兜底前先有正常「继续挑战」点击(重试现行为)')
    long_presses = [(x, pt) for x, pt in _press_recorder
                    if (x, pt) == (960.0, 0.5)]
    assert long_presses, (
        f'M39 第 3 轮停留应长按 (960,898) press_time=0.5:{_press_recorder}')


def test_defeat_branch_never_enters_settle_confirm(
    test_context, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """战败分支回归测试:失败结算页(1f 分支)不进结算确认 op、不推进
    (终局流转,节点序止于终局;战败路径回归不变)。"""
    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )

    gs = _anchored_session(test_context, monkeypatch, pos=(1, 1))

    calls: list = []

    class _OpRecorder:
        def __init__(self, ctx):
            calls.append(ctx)

    monkeypatch.setattr(settle_confirm_mod, 'CwOpSettleConfirm', _OpRecorder)

    st = SettlementState(run_start_ts=time.monotonic(), is_new_match=True)
    op = CwScreenBattleWait(test_context, st, CurrencyWarConfig(
        test_context.current_instance_idx))
    monkeypatch.setattr(op, 'last_screenshot', None, raising=False)
    monkeypatch.setattr(op, 'screenshot', lambda: None)
    _1f_marks = {('货币战争-结算-失败', '标识-挑战进度'),
                 ('货币战争-结算-失败', '标识-挑战结束')}
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area((s, a) in _1f_marks))
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_ocr_and_click',
                        lambda *a, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_ocr',
                        lambda scr, text, **k: _Area(text == '前往结算'))
    monkeypatch.setattr(op, 'save_screenshot', lambda prefix=None: '')
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(
        test_context, 'ocr_service',
        SimpleNamespace(get_ocr_result_list=lambda **kw: []),
        raising=False)

    rs = op.wait()

    assert calls == [], '战败分支(1f)不得进入结算确认 op'
    assert gs.node_pos.value == (1, 1), '战败终局不推进节点序'
    assert not rs.is_success and rs.result is not None, (
        f'战败页按 1f 分支流转(翻页/点空白 round_wait):{rs!r}')


# ==================== 观测覆盖度守卫测试 ====================


def test_guard_truth_table(monkeypatch) -> None:
    """测试1 守卫真值表:两 success 出口 + 窗标记失配 → L1 行;bail/已观测/
    无窗开标记(battle_ts=None)三静默臂不落行。"""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(_defects_mod, 'record_defect',
                        lambda *a, **k: calls.append((a, k)))
    # 触发臂①:白名单出口,本窗(出战开窗 100)零观测行(标记 = None)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=None),
        'back_to_loop') is True
    # 触发臂②:终局出口,标记滞留上一窗(150 ≠ 当前 200)= 本窗未写过
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=200.0, settled_battle_ts=150.0),
        'terminal_lobby') is True
    assert len(calls) == 2
    args0, kwargs0 = calls[0]
    assert args0[:2] == ('settlement', 'settle_obs_coverage_miss')
    assert kwargs0.get('severity') == SEVERITY_L1_ALERT
    # 静默臂①:本窗已观测(标记 = 窗标记)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=100.0),
        'back_to_loop') is False
    # 静默臂②:bail 出口不在窗口单元出口集(帧标记可重入续同窗,计则假阳)
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=100.0, settled_battle_ts=None),
        '战斗等待连续未识别,bail 交主循环兜底') is False
    # 静默臂③:接管局/残留屏帧标记入窗,无出战开窗标记
    assert count_settlement_obs_coverage_miss(
        SettlementState(battle_ts=None, settled_battle_ts=None),
        'back_to_loop') is False
    assert len(calls) == 2


def test_record_round_outcome_refreshes_window_anchor(
        test_context, monkeypatch) -> None:
    """测试2 结算观测行写点刷新窗标记 + hp_after 传导:结算屏读点经生产链路
    (read_round_outcome → performance.record → apply_settlement_cover)
    后,窗标记 = 当前 battle_ts、gs.hp = 结算真值。"""
    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    monkeypatch.setattr(test_context, 'ocr_service',
                        SimpleNamespace(get_ocr_result_list=lambda **k: []),
                        raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(bw_mod, 'read_phase_round',
                        lambda ctx, scr, round_caps=None: (1, 1))
    monkeypatch.setattr(
        bw_mod, 'read_round_outcome',
        lambda ctx, scr, **k: RoundOutcome(
            round_num=1, plane=1, node_type='普通战斗', comp_tag='c',
            hp_after=3, hp_confidence=1.0, killed=False))
    op._record_round_outcome(_FRAME)
    assert st.settled_battle_ts == 1234.0, \
        '结算观测行写点必须刷新窗标记(缺失 = 覆盖度守卫永久静默)'
    assert st.saw_settlement is True
    assert game_state_of(session).hp.value == 3, \
        '结算观测 hp_after 经结算覆盖写端直入 gs(观察赢唯一真值入口)'


class _BattleWaitStub:
    """battle_wait 替身:execute 返回 back_to_loop(窗口单元 success 出口)。"""

    journal = ''

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self):
        return SimpleNamespace(success=True, status='back_to_loop')


def _make_coverage_loop(test_context, monkeypatch,
                        settle: SettlementState) -> CwLoop:
    """CwLoop 裸装配 + 全桩面,战斗窗驻留一次性标志位置位(先例 = boss 帧排除测试)。"""
    op = CwLoop.__new__(CwLoop)
    op.ctx = test_context
    op._iter = 3                # 3+1=4:跳过 iter1 预检/焦点检查/首读分支
    op._stop_at_prep = False
    op._max_rounds = None
    op._battle_wait_active = True   # 战斗窗驻留一次性标志位(出战成功形态)
    op._battle_ts = 1234.0
    op._cw_resume_candidate = False
    op._cw_locked_resume = False
    op._settle = settle
    op._battle_wait = _BattleWaitStub(test_context)
    monkeypatch.setattr(op, 'last_screenshot', _FRAME, raising=False)
    monkeypatch.setattr(op, 'round_by_ocr',
                        lambda scr, text, **k: _Area(False))
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda scr, s, a, **k: _Area(False))
    monkeypatch.setattr(cw_loop_mod, 'get_match_screen_name',
                        lambda ctx, scr, screen_name_list=None: None)
    monkeypatch.setattr(cw_loop_mod, 'save_decision_frame',
                        lambda *a, **k: None)
    monkeypatch.setattr(cw_loop_mod, '_log_cw_op',
                        lambda *a, **k: None)
    return op


def test_battle_branch_exit_consumes_coverage_guard(
        test_context, monkeypatch) -> None:
    """测试3 收尾接入调用:战斗分支 op 返回 back_to_loop → 守卫被消费,零观测窗
    落 L1 行;已观测窗(标记匹配)不落行。"""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(_defects_mod, 'record_defect',
                        lambda *a, **k: calls.append((a, k)))
    # 场景①:出战开窗(battle_ts 注入)且本窗零观测行 → 守卫落行
    op = _make_coverage_loop(test_context, monkeypatch,
                             SettlementState(battle_ts=1234.0,
                                             settled_battle_ts=None))
    with fast_sleep():
        _run_node(test_context, op, op.loop)
    assert len(calls) == 1, f'收尾点应消费覆盖度守卫并落行:{calls}'
    args0, kwargs0 = calls[0]
    assert args0[:2] == ('settlement', 'settle_obs_coverage_miss')
    assert kwargs0.get('severity') == SEVERITY_L1_ALERT
    # 场景②:本窗已观测(标记 = 窗标记)→ 零行
    calls.clear()
    op2 = _make_coverage_loop(test_context, monkeypatch,
                              SettlementState(battle_ts=1234.0,
                                              settled_battle_ts=1234.0))
    with fast_sleep():
        _run_node(test_context, op2, op2.loop)
    assert calls == [], '已观测窗 exit 不落覆盖度行'


# ==================== 真值收尾测试(settle_truth)====================


def _sig():
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _spy_defects(monkeypatch) -> list[str]:
    """桩掉缺陷台账发射口,记录 kind 供断言(同 tracked_slot_star 模式)。"""
    kinds: list[str] = []

    def _rec(*args, **kwargs):
        kinds.append(kwargs.get('kind', ''))

    monkeypatch.setattr(gsm, '_emit_defect', _rec)
    return kinds


def test_diff_credits_with_ledger_row(monkeypatch) -> None:
    """逻辑态账本 7 + 结算真值 11 → 差 +4 落 boundary_income_credited 行,
    真值观察赢入账(不进三分流、不安灯)。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 7, sig=_sig())
    gs.write_logic(gs.gold, 9, produced_by='TestProj',
                   sig=ChannelSig(family='logic_action', actor='TestSigWriter',
                                  mode='compute'))
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11 and gs.gold.source == 'observation', \
        '结算真值无条件入账(观察赢)'
    assert kinds == ['boundary_income_credited'], \
        '差值落台账行留证(豁免 ≠ 消失同纪律)'


def test_equal_value_no_row(monkeypatch) -> None:
    """等值收尾(账本与真值一致)→ 零新信息,不落台账行,来源照常翻
    观察态。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 11, sig=_sig())
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11
    assert kinds == [], '等值观察零新信息不产行'


def test_observation_source_adopts_silently(monkeypatch) -> None:
    """账本在观察态(无逻辑失配可比)→ 静默采新,不落差值行。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 7, sig=_sig())
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11 and gs.gold.source == 'observation'
    assert kinds == [], '观察→观察采新无失配语义'


# ==================== 金面板解析回归测试 ====================


def test_same_token_form_regression() -> None:
    """存量与数值同 token(原形态回归):'存量：52' / '存量52' 两形都读。"""
    assert parse_settlement_assets(
        ['挑战成功', '存量：52', 'Lv.3'])['gold'] == 52
    assert parse_settlement_assets(
        ['挑战成功', '存量 47', 'Lv.3'])['gold'] == 47


def test_missing_anchor_stays_none() -> None:
    """识别标志词缺失(面板不在场/OCR 整段漏)→ None,不冒认(负例回归)。

    当前版本结算布局无「存量」token(2026-09-18 结算帧亲读实证),本
    负例即生产常态——真值入口主路径 = read_settle_gold_opt 定点读数。"""
    assert parse_settlement_assets(
        ['挑战成功', '小队生命值71', '连胜×0'])['gold'] is None
    assert parse_settlement_assets([])['gold'] is None


def _stub_ctx(ocr_values: list, controller=None) -> SimpleNamespace:
    """最小 ctx 桩:ocr_service 依次弹出 ocr_values;controller 缺省 None
    (无稳定门,单帧读即全部能力——与生产离线/单测分支同形)。"""
    calls = {'n': 0}

    def _ocr(**k):
        v = ocr_values[min(calls['n'], len(ocr_values) - 1)]
        calls['n'] += 1
        return [SimpleNamespace(data=v)]

    return SimpleNamespace(ocr_service=SimpleNamespace(
        get_ocr_result_list=_ocr), controller=controller)


def test_settle_gold_reader_basics(monkeypatch) -> None:
    """「不猜」契约四态:area 缺失 / OCR 越界 / 帧不可下标 → None;
    正常读数 → int。"""
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    # area 缺失(screen_info 无该 area)→ None,连 OCR 都不碰。
    monkeypatch.setattr(settle_mod, '_area_rect', lambda *a, **k: None)
    assert read_settle_gold_opt(_stub_ctx(['11']), frame) is None
    # area 在场 + 读数越界(>GOLD_MAX)→ None 不冒认。
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    assert read_settle_gold_opt(_stub_ctx(['9999']), frame) is None
    # 正常读数。
    assert read_settle_gold_opt(_stub_ctx(['11']), frame) == 11
    # 帧不可下标(观测面异常,如 battle_wait 测试的帧哨兵)→ None 不毒化。
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    assert read_settle_gold_opt(_stub_ctx(['11']), object()) is None


def test_settle_gold_reader_gate_takes_last(monkeypatch) -> None:
    """稳定门:帧间不一致(计数器入账滚动中)取末帧 = 入账后真值;
    帧间一致即采信(零额外成本)。"""
    monkeypatch.setattr(settle_mod, 'SETTLE_GOLD_INTERVAL_S', 0)
    monkeypatch.setattr(settle_mod, '_area_rect',
                        lambda *a, **k: Rect(0, 0, 100, 40))
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    ctl = SimpleNamespace(screenshot=lambda: frame)
    # 9 → 13 不一致:采末帧 13(165656 局实证形态:结算展示期仍在入账)。
    assert read_settle_gold_opt(_stub_ctx(['9', '13'], ctl), frame) == 13
    # 9 → 9 一致:即采信,不耗满补采。
    assert read_settle_gold_opt(_stub_ctx(['9', '9'], ctl), frame) == 9


# ==================== hp 直读测试(decision_hp)====================


def test_hp_direct_read_after_anchor_retirement():
    """hp 直读对照(正本已退役 判据:门简化为 gs.hp 直读,结算覆盖写端
    在场场景)。标记退役后 decision_hp = gs.hp 直读——
    ①结算覆盖写端写入 → 读口立即反映(「结算即写」时序保持);
    ②标记字段不再影响读口(旧标记在场与否零差异 = 单一源成立);
    ③可信位语义不变(observation/carried 可信,prior/logic fail-closed)。"""
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    sess = StrategySession()
    sess.last_hp = 77          # 旧标记残留(已无写端,模拟迁移期残值)
    sess.last_hp_t = 9
    gs = GameState(schema_version=1)
    _hp_sig = ChannelSig(family='obs', actor='cw_observation',
                         screen='货币战争-结算', mode='read')
    # 结算覆盖写端(§3.5.1 语义:观察直写)→ 读口反映现值,旧标记零影响
    gs.observe(gs.hp, 80, sig=_hp_sig)
    assert decision_hp(gs, sess) == 80
    assert hp_decision_trusted_of(gs) is True
    # carried 语义(失读沿用)= 可信位 True,读口同值
    gs.carry(gs.hp, frame=1, sig=ChannelSig(family='obs', actor='cw_observation',
                                            screen='货币战争-备战', mode='carried'))
    assert decision_hp(gs, sess) == 80
    assert hp_decision_trusted_of(gs) is True
    # 标记字段在场不产生任何覆盖(旧门行为已退役:标记不再回写读口)
    assert decision_hp(gs, sess) == 80
