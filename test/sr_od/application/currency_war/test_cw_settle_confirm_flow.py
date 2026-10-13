"""结算确认动作 op 流程锁(
landing §3.2 判据面;去证据门形态 2026-09-21 用户裁定)。

判据 ↔ 测试对照:

- 结算帧 → op → 点击即上报(logic 态恰一档)→ 按钮离场交回宿主 →
  test_click_reports_once_and_returns
- 死点击(结算屏恒在)→ 重复点击重复上报被观察态门挡(零推进)+
  M39 长按兜底(M39 迁入锁)→
  test_dead_click_gate_blocks_and_long_press_retry
- 战败分支不进本 op(终局路径回归不变)→
  test_defeat_branch_never_enters_settle_confirm

驱动 = 真帧 fixture + 真 OCR 识别链(FixtureController 剧本推进),容器
= cw4_session 旁表 + observe_node_anchor 预锚定 observation 态(新路径
全可测,不经共存期观察态门挡)。
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace

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

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
    observe_node_anchor,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm import (
    CwOpSettleConfirm,
)

settle_confirm_mod = importlib.import_module(
    'sr_od.application.currency_war.operations.cw_op.cw_op_settle_confirm')

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
    """锚定容器态:session 旁表 + node_pos 预锚定 observation(新路径
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
    """主链路锁:结算帧 → 点「继续挑战」落位 → **点击即上报**恰一档
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
    """死点击锁:结算屏恒在(点击不生效)→ 每轮重试点击 + 重复上报被
    观察态门挡(推进恰一档后零推进)+ 第 3 轮停留长按 (960,898)
    press_time=0.5(M39 迁入锁;去证据门后死点击自愈链靠宿主重分派)。"""
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
    """战败分支回归锁:失败结算页(1f 分支)不进结算确认 op、不推进
    (终局流转,节点序止于终局;战败路径回归不变)。"""
    import time

    from sr_od.application.currency_war.currency_war_config import (
        CurrencyWarConfig,
    )
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_battle_wait as bwo,
    )

    gs = _anchored_session(test_context, monkeypatch, pos=(1, 1))

    calls: list = []

    class _OpRecorder:
        def __init__(self, ctx):
            calls.append(ctx)

    monkeypatch.setattr(settle_confirm_mod, 'CwOpSettleConfirm', _OpRecorder)

    st = bwo.SettlementState(run_start_ts=time.monotonic(), is_new_match=True)
    op = bwo.CwScreenBattleWait(
        test_context, st,
        CurrencyWarConfig(test_context.current_instance_idx))
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
