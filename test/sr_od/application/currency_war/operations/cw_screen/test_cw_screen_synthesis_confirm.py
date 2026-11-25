"""CwScreenSynthesisConfirm 合成确认浮层收尾 op 行为测试(harness 剧本)。

锁设计约定(两段式画面 op,先例 = CwScreenRoleDetailOverlay 形态):

- 入口门 miss = round_fail 交回主循环,零点击(防误分发帧上盲点确认);
- 门 hit(双锚其一)→ 点「按钮-合成浮层通过」;点后浮层仍在 = 落地复查
  重做推进(round_wait 循环,不烧节点重试预算);
- 落地复查标志(_advanced_once):推进已发重入时双锚不在 = 浮层已消失 =
  success 交回(零验证形态:动作层不验效果,出口 = 入口观察的合法重判);
- MCP 可运行单元契约:构造签名仅 ctx(协议字段逐字命名,零业务参数)。
"""

import inspect

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
from sr_od.application.currency_war.operations.cw_screen.cw_screen_synthesis_confirm import (
    CwScreenSynthesisConfirm,
)

#: 浮层帧存档(screen_name, state)。
_OVERLAY_FRAME: tuple[str, str] = ('货币战争-备战-合成确认', '合成确认浮层')
#: 非浮层帧存档(门 miss 用 / 推进后的交回帧):同玩法备战画面,
#: 与 ✓/✕ 双锚零共命中(id_mark 测试碰撞半边已锁)。
_GONE_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


class _WatchedSynthesisConfirm(WatchdogOperationMixin, CwScreenSynthesisConfirm):
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
    op = _WatchedSynthesisConfirm(test_context)
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
    for screen_name, state in (_OVERLAY_FRAME, _GONE_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_mcp_runnable_contract() -> None:
    """MCP 可运行单元契约:构造签名仅 ctx(逐字命名,反射按名剔除,
    零业务参数)。"""
    sig = inspect.signature(CwScreenSynthesisConfirm.__init__)
    params = list(sig.parameters)
    assert params == ['self', 'ctx'], f'构造签名应为 (self, ctx):{params}'
    assert CwScreenSynthesisConfirm.__name__ == 'CwScreenSynthesisConfirm'


def test_gate_miss_fails_back(test_context: SrTestContext,
                              monkeypatch: pytest.MonkeyPatch) -> None:
    """入口门 miss:非浮层帧 → fail 交回主循环,零点击。"""
    _require_screens(test_context)
    phases = [{'frame': _GONE_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert not result.success, f'门 miss 应 fail 交回,实际 {result.status}'
    assert '入口识别标志未命中' in (result.status or '')
    assert ctrl.recorded_clicks == [], f'门 miss 不应有点击:{ctrl.recorded_clicks}'


def test_gate_hit_confirms_and_reconfirms(test_context: SrTestContext,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """门 hit → 点 ✓;点后浮层仍在 = 落地复查重做推进(round_wait 循环)。

    剧本:浮层帧(点 ✓ 推进)→ 浮层帧(重做点击推进)→ 非浮层帧
    (落地复查判已消失,success 收尾)。"""
    _require_screens(test_context)
    overlay = {'frame': _OVERLAY_FRAME,
               'exit': ('on_click_in', _OVERLAY_FRAME[0], '按钮-合成浮层通过')}
    phases = [overlay, dict(overlay), {'frame': _GONE_FRAME}]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'推进链未成功交回:status={result.status};phase_idx={ctrl.phase_idx};'
        f'clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 2, (
        f'应恰好两次 ✓ 点击(首发 + 未消失重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_OVERLAY_FRAME[0], '按钮-合成浮层通过')
    assert ctrl.phase_idx == 2, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'


def test_overlay_gone_reentry_success(test_context: SrTestContext,
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """落地复查标志:✓ 已发重入,双锚不在 = 浮层已消失 → success 交回。

    剧本:浮层帧(点 ✓ 推进)→ 非浮层帧(重入落地复查,success 收尾)。"""
    _require_screens(test_context)
    phases = [
        {'frame': _OVERLAY_FRAME,
         'exit': ('on_click_in', _OVERLAY_FRAME[0], '按钮-合成浮层通过')},
        {'frame': _GONE_FRAME},
    ]
    ctrl, result = _run_op(test_context, monkeypatch, phases)

    assert result.success, (
        f'重入落地复查未 success 交回:status={result.status};'
        f'phase_idx={ctrl.phase_idx};clicks={ctrl.recorded_clicks}'
    )
    assert len(ctrl.recorded_clicks) == 1, (
        f'应恰好一次 ✓ 点击(浮层已消失不重做):{ctrl.recorded_clicks}'
    )
    assert ctrl.click_hit_area(_OVERLAY_FRAME[0], '按钮-合成浮层通过')
    assert ctrl.phase_idx == 1, f'应推进到交回帧:phase_idx={ctrl.phase_idx}'
