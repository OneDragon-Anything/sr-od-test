"""CwToggleShopPanel 三画面参数面与收店控件分支(fixture harness 剧本)。

锁的设计约定(被测单一源 = cw_toggle_shop_panel;设计出处 =
docs/develop/sr_od/application/currency_war/changes/2026-11-18-cw-fix1-smallfixes/design.md §2.1):

- 参数面三值:备战 / 开商店(固定面板开关,静态矩形中心直点,存量行为零漂移)/
  开拓商店(左缘浮动徽记,带内模板命中位直点);
- 开拓商店命中分支:点击恰好一次、坐标 = 徽记命中位而非带中心(徽记 y 随
  羁绊面板布局浮动,带中心会点空)。**期望坐标 = fixture 真值标注**:
  ``商店展开.webp`` 徽记中心 = (267, 262)——离线探针(与画面档 area 同构的
  crop_and_match_template,阈值 0.7)读出 score 0.974 后人工看图复核金菱形
  徽记居中;测试内禁用与被测同源的模板匹配实现现算期望(复刻被测逻辑禁项);
- 开拓商店 miss 分支:徽记不在场帧 → 显式 fail 带可操作提示,点击零发生,
  零引擎重试(单次执行即 fail;框架 round 系 miss 是 round_retry + 通用
  status,自定义提示只有 miss 即 fail 写法能透出);
- MCP 反射面:describe_operation 透出三值口径与 miss 出口描述(部署 agent
  看 describe 是它了解 op 的唯一来源)。
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
from sr_od.application.currency_war.kernel.cw_obs_core import (
    PIONEER_SHOP_SCREEN_NAME,
    SCREEN_NAME,
    SHOP_SCREEN_NAME,
)
from sr_od.application.currency_war.operations.actions.cw_toggle_shop_panel import (
    CwToggleShopPanel,
)

#: 开拓商店展开帧(fixture 真值标注见模块 docstring)。
_PIONEER_FRAME: tuple[str, str] = ('货币战争-备战-开拓商店', '商店展开')
#: 徽记不在场帧(开拓银轨 <2,带内无 ≥0.7 命中)。
_BADGE_ABSENT_FRAME: tuple[str, str] = ('货币战争-备战', 'rail_badge_absent_r2')
#: 备战收起态帧(固定开关回归)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'shop_closed')
#: 开商店展开态帧(固定开关回归)。
_SHOP_OPEN_FRAME: tuple[str, str] = ('货币战争-备战-开商店', 'shop_open')

#: 模块 docstring 标注的徽记中心 fixture 真值(带中心 = (270, 400),两值可区分)。
_BADGE_TRUTH_XY: tuple[int, int] = (267, 262)

_FULL_OP_ID: str = ('sr_od.application.currency_war.operations.actions.'
                    'cw_toggle_shop_panel.CwToggleShopPanel')


class _WatchedToggleShopPanel(WatchdogOperationMixin, CwToggleShopPanel):
    """带看门狗的 op(流程测试防无限轮)。"""


class _CountingFixtureController(FixtureController):
    """计数框架截图(= 框架轮数):miss 分支零引擎重试的判据。

    框架每轮经 ``controller.screenshot()``(两元组变体)取帧,节点内兜底
    ``get_screenshot()`` 一并计数。
    """

    def __init__(self, ctx: SrTestContext) -> None:
        FixtureController.__init__(self, ctx)
        self.screenshot_calls: int = 0

    def screenshot(self, independent: bool = False):
        self.screenshot_calls += 1
        return FixtureController.screenshot(self, independent)

    def get_screenshot(self, independent: bool = False):
        self.screenshot_calls += 1
        return FixtureController.get_screenshot(self, independent)


def _run_op(test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
            screen_name: str,
            phases: list[dict]) -> tuple[_CountingFixtureController, OperationResult]:
    """装假控制器 + 跑完整 execute(),返回(控制器, 结果)供断言。"""
    ctrl = _CountingFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases(phases)
    op = _WatchedToggleShopPanel(test_context, screen_name=screen_name)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result


def _require_screens(test_context: SrTestContext,
                     frames: list[tuple[str, str]]) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in frames:
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_pioneer_screen_name_accepted(
        test_context: SrTestContext) -> None:
    """参数面:开拓商店画面值构造成功(收店能力缺口修复的直接锁面)。"""
    op = CwToggleShopPanel(test_context, screen_name=PIONEER_SHOP_SCREEN_NAME)
    assert op.screen_name == PIONEER_SHOP_SCREEN_NAME


def test_invalid_screen_name_rejected_with_available_list(
        test_context: SrTestContext) -> None:
    """非法画面值构造期 ValueError,可用值列表含开拓商店(调用方要能自纠)。"""
    with pytest.raises(ValueError) as exc_info:
        CwToggleShopPanel(test_context, screen_name='货币战争-不存在的画面')
    assert PIONEER_SHOP_SCREEN_NAME in str(exc_info.value)


@pytest.mark.parametrize('screen_name,frame', [
    (SCREEN_NAME, _PREP_FRAME),
    (SHOP_SCREEN_NAME, _SHOP_OPEN_FRAME),
])
def test_fixed_toggle_static_center_click_unchanged(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        screen_name: str, frame: tuple[str, str]) -> None:
    """备战 / 开商店回归:仍是「按钮-商店开关」静态矩形中心直点,存量行为
    零漂移(期望坐标 = 建档 rect 中心同源现算,既有先例口径)。"""
    _require_screens(test_context, [frame])
    ctrl, result = _run_op(test_context, monkeypatch, screen_name,
                           [{'frame': frame}])

    area = test_context.screen_loader.get_area(screen_name, '按钮-商店开关')
    assert area is not None and area.pc_rect is not None, \
        f'{screen_name} 缺 按钮-商店开关 area'
    rect = area.pc_rect
    expected = ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)
    assert result.success, f'固定开关分支应 success:{result.status}'
    assert len(ctrl.recorded_clicks) == 1
    assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == expected


def test_pioneer_badge_hit_clicks_matched_center(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """开拓商店命中分支:徽记在场帧 → 点击恰好一次,坐标 = 徽记命中位
    (fixture 真值 (267,262),非带中心 (270,400))。"""
    _require_screens(test_context, [_PIONEER_FRAME])
    ctrl, result = _run_op(test_context, monkeypatch,
                           PIONEER_SHOP_SCREEN_NAME,
                           [{'frame': _PIONEER_FRAME}])

    assert result.success, f'徽记命中应 success:{result.status}'
    assert len(ctrl.recorded_clicks) == 1, \
        f'应恰好一次点击:{ctrl.recorded_clicks}'
    assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == _BADGE_TRUTH_XY


def test_pioneer_badge_miss_fails_explicitly_without_retry(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """开拓商店 miss 分支:徽记不在场帧 → 显式 fail 带可操作提示,点击零
    发生,零引擎重试(单轮即 fail:轮数计数 = 截图次数 = 1;若误改回
    round_retry 会烧满重试预算,此处先红)。"""
    _require_screens(test_context, [_BADGE_ABSENT_FRAME])
    ctrl, result = _run_op(test_context, monkeypatch,
                           PIONEER_SHOP_SCREEN_NAME,
                           [{'frame': _BADGE_ABSENT_FRAME}])

    assert not result.success, f'徽记 miss 应 fail,实际 {result.status}'
    assert '徽记未识别' in (result.status or ''), \
        f'fail status 应带可操作提示:{result.status}'
    assert ctrl.recorded_clicks == []
    assert ctrl.screenshot_calls == 1, \
        f'miss 应单轮显式 fail(零引擎重试),实际 {ctrl.screenshot_calls} 轮'


def test_describe_surfaces_three_values_and_miss_exit() -> None:
    """MCP 反射面:describe_operation 透出三值口径、各画面控件语义与 miss
    出口描述(远程部署 agent 看 describe 是它了解 op 的唯一来源)。"""
    from sr_od.backend.operation_registry import describe_operation

    info = describe_operation(None, _FULL_OP_ID)
    doc = info['docstring'] or ''
    assert PIONEER_SHOP_SCREEN_NAME in doc, 'describe 未透出开拓商店画面值'
    assert '徽记' in doc and '面板开关' in doc, 'describe 未透出各画面控件语义'
    assert '未命中' in doc, 'describe 未透出 miss 出口描述'
    assert any(p['name'] == 'screen_name' for p in info['params'])
