"""CwScreenEnemyInfo 敌人信息浮层 op 行为测试(harness 剧本)。

锁设计约定(1+N 无策略段弹窗 op:观察 id_mark 门 → 占位上报 → 点关闭
落地复查 → 交回;标志语义先例 = CwScreenNoFrontHint):

- 标识门 miss = round_fail 交编排壳,零点击(防误分发帧上盲点关闭);
- 门 hit = 点「按钮-关闭」;关闭未落地(浮层仍在)= 落地复查重做关闭
  (重做轮走 round_wait 循环,不烧节点重试预算);
- 落地复查标志:关闭已发重入时识别标志不在 = 浮层已关 = success 交回
  主循环(零验证形态:动作层不验效果,判效归下一帧观察)。

浮层帧 = 测试仓 screens/货币战争-敌人信息浮层/(详情页形态 webp,
左上「敌方信息」标识与右上关闭钮同位);非浮层帧 = 同玩法备战画面。
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
from sr_od.application.currency_war.operations.cw_screen.cw_screen_enemy_info import (
    CwScreenEnemyInfo,
)

#: 浮层帧存档(screen_name, state)。
_OVERLAY_FRAME: tuple[str, str] = (
    '货币战争-敌人信息浮层', '敌方信息-逐光捡金物竞天择其十')
#: 非浮层帧存档(门 miss 用 / 落地复查后的交回帧):同玩法另一画面,
#: 与「标识-敌方信息」区域零共命中。
_OTHER_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


class _WatchedEnemyInfo(WatchdogOperationMixin, CwScreenEnemyInfo):
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
    op = _WatchedEnemyInfo(test_context)
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
    for screen_name, state in (_OVERLAY_FRAME, _OTHER_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_gate_miss_fails_back(test_context: SrTestContext,
                              monkeypatch: pytest.MonkeyPatch) -> None:
    """标识门 miss:非本屏帧 → fail 交回编排壳,零点击。"""
    _require_screens(test_context)
    phases = [{'frame': _OTHER_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert not result.success, f'门 miss 应 fail 交回,实际 {result.status}'
    assert result.status == '非敌人信息浮层'
    assert ctrl.recorded_clicks == [], f'门 miss 不应有点击:{ctrl.recorded_clicks}'


def test_gate_hit_closes_and_verifies(test_context: SrTestContext,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """门 hit → 点关闭;关闭未落地(浮层仍在)= 落地复查重做关闭。

    剧本:浮层帧(点关闭推进)→ 浮层帧(重做点击推进)→ 非浮层帧
    (落地复查判已关,success 收尾)。"""
    _require_screens(test_context)
    overlay = {'frame': _OVERLAY_FRAME,
               'exit': ('on_click_in', _OVERLAY_FRAME[0], '按钮-关闭')}
    phases = [overlay, dict(overlay), {'frame': _OTHER_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'关闭链未成功交回:status={result.status};phase_idx={ctrl.phase_idx};'
        f'clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 2, (
        f'应恰好两次关闭点击(首发 + 未落地重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_OVERLAY_FRAME[0], '按钮-关闭')
    assert ctrl.phase_idx == 2, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'


def test_close_pending_reentry_success(test_context: SrTestContext,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """落地复查标志:关闭已发重入,识别标志不在 = 浮层已关 → success 交回。

    剧本:浮层帧(点关闭推进)→ 非浮层帧(重入落地复查,success 收尾)。"""
    _require_screens(test_context)
    phases = [
        {'frame': _OVERLAY_FRAME,
         'exit': ('on_click_in', _OVERLAY_FRAME[0], '按钮-关闭')},
        {'frame': _OTHER_FRAME},
    ]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'重入落地复查未 success 交回:status={result.status};'
        f'phase_idx={ctrl.phase_idx};clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 1, (
        f'应恰好一次关闭点击(浮层已关不重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_OVERLAY_FRAME[0], '按钮-关闭')
    assert ctrl.phase_idx == 1, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'
