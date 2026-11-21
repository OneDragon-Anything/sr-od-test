"""CwScreenNoFrontHint 前台无角色提示弹窗 op 行为测试(harness 剧本)。

锁设计约定(弹窗 op 轻形态:观察 id_mark 门 → 占位上报 → 决策动作落地
复查 → 确认 → 交回;标志语义先例 = CwScreenDeployNotFull):

- 标识门 miss = round_fail 交编排壳,零点击(防误分发帧上盲点确认);
- 门 hit = 点「按钮-确认」确认关闭;确认未落地(弹窗仍在)= 落地复查
  重做确认(重做轮走 round_wait 循环,不烧节点重试预算);
- 落地复查标志:确认已发重入时识别标志不在 = 弹窗已关 = success 交回
  主循环(零验证形态:动作层不验效果,判效归下一帧观察)。
"""

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.operations.cw_screen.cw_screen_no_front_hint import (
    CwScreenNoFrontHint,
)

#: 弹窗帧存档(screen_name, state)。
_POPUP_FRAME: tuple[str, str] = ('货币战争-提示-前台无角色', '出战被拒')
#: 非弹窗帧存档(门 miss 用 / 落地复查后的交回帧):同玩法另一画面,
#: 与「标识-无角色提示」区域零共命中。
_OTHER_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


class _WatchedNoFrontHint(WatchdogOperationMixin, CwScreenNoFrontHint):
    """带看门狗的 op(流程测试防无限轮)。"""


def _run_op(test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
            phases: list[dict]) -> tuple[FixtureController, OperationResult]:
    """装假控制器 + 跑完整 execute(),返回(控制器, 结果)供断言。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases(phases)
    op = _WatchedNoFrontHint(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result


def _require_screens(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_POPUP_FRAME, _OTHER_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_gate_miss_fails_back(test_context: SrTestContext,
                              monkeypatch: pytest.MonkeyPatch) -> None:
    """标识门 miss:非本屏帧 → fail 交回编排壳,零点击。"""
    _require_screens(test_context)
    phases = [{'frame': _OTHER_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert not result.success, f'门 miss 应 fail 交回,实际 {result.status}'
    assert result.status == '非前台无角色弹窗'
    assert ctrl.recorded_clicks == [], f'门 miss 不应有点击:{ctrl.recorded_clicks}'


def test_gate_hit_confirms_and_reconfirms(test_context: SrTestContext,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """门 hit → 点确认;确认未落地(弹窗仍在)= 落地复查重做确认。

    剧本:弹窗帧(点确认推进)→ 弹窗帧(重做点击推进)→ 非弹窗帧
    (落地复查判已关,success 收尾)。"""
    _require_screens(test_context)
    popup = {'frame': _POPUP_FRAME,
             'exit': ('on_click_in', _POPUP_FRAME[0], '按钮-确认')}
    phases = [popup, dict(popup), {'frame': _OTHER_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'确认链未成功交回:status={result.status};phase_idx={ctrl.phase_idx};'
        f'clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 2, (
        f'应恰好两次确认点击(首发 + 未落地重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_POPUP_FRAME[0], '按钮-确认')
    assert ctrl.phase_idx == 2, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'


def test_confirm_pending_reentry_success(test_context: SrTestContext,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """落地复查标志:确认已发重入,识别标志不在 = 弹窗已关 → success 交回。

    剧本:弹窗帧(点确认推进)→ 非弹窗帧(重入落地复查,success 收尾)。"""
    _require_screens(test_context)
    phases = [
        {'frame': _POPUP_FRAME,
         'exit': ('on_click_in', _POPUP_FRAME[0], '按钮-确认')},
        {'frame': _OTHER_FRAME},
    ]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'重入落地复查未 success 交回:status={result.status};'
        f'phase_idx={ctrl.phase_idx};clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 1, (
        f'应恰好一次确认点击(弹窗已关不重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_POPUP_FRAME[0], '按钮-确认')
    assert ctrl.phase_idx == 1, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'
