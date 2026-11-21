"""GotoTreasuresLightward 入口导航 op 流程测试(fixture 剧本,不连真游戏)。

锁设计约定(见 src/sr_od/application/treasures_lightward/operations/goto_treasures_lightward.py 模块 docstring):
- 前置链共用:判定节点分流;大世界起走全链(大世界→手机菜单→指南→分类页→选关);
- 已在分类页(含面板选中态与目标不符)→ 显式点目标分类后进入;
- 已在选关(混沌回忆视图干净态)→ 零点击直成功;
- 末日幻影全链:分类页选中→传送→开场介绍页(已更新+前往挑战双锚,点前往挑战)→选关成功。

OFF_PATH 分支(委托 BackToNormalWorldPlus)内部分支依赖多画面 area,fixture
剧本难覆盖,由实机 run_operation 验证(编队屏起跑即命中该分支),本文件不测。
"""

from __future__ import annotations

import pytest

from sr_od.application.treasures_lightward.operations.goto_treasures_lightward import GotoTreasuresLightward, TLMode
from sr_od.operations.sr_operation import SrOperation
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_WORLD_FRAME = ('大世界', '普通')
_MENU_FRAME = ('菜单', '菜单-无邮件红点')
_GUIDE_FRAME = ('星际和平指南', '每日实训')
_CATEGORY_FH_FRAME = ('指南-逐光捡金', '分类页-忘却之庭总览')
_CATEGORY_AA_FRAME = ('指南-逐光捡金', '分类页-异相仲裁选中')
_CATEGORY_AS_FRAME = ('指南-逐光捡金', '分类页-末日幻影选中')
_SELECT_FRAME = ('逐光捡金', '忘却之庭选关')
_AS_INTRO_FRAME = ('末日幻影-开场', '新期介绍')
_AS_SELECT_FRAME = ('末日幻影-选关', '默认')


class _WatchedGoto(WatchdogOperationMixin, GotoTreasuresLightward):
    """带看门狗 + 跳过游戏窗口前置节点(MockController 无 game_win)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx, mode) -> None:
        # 直接走 SrOperation 构造跳过基类的 need_check_game_win 默认;
        # mode 赋值需自带(跳过了 GotoTreasuresLightward.__init__)。
        self.mode = mode if isinstance(mode, TLMode) else TLMode(mode)
        SrOperation.__init__(self, ctx, op_name='测试-前往逐光捡金', need_check_game_win=False)


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
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


def _run_execute(test_context: SrTestContext, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _require_screens(test_context: SrTestContext, frames: list[tuple[str, str]]) -> None:
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')


def test_fh_from_world(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """大世界起走全链:手机菜单→指南→分类页(点目标分类)→传送→选关干净态收尾成功。"""
    frames = [_WORLD_FRAME, _MENU_FRAME, _GUIDE_FRAME, _CATEGORY_FH_FRAME, _SELECT_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _WORLD_FRAME, 'exit': ('on_click_in', '大世界-普通', '左上图标-菜单')},
        {'frame': _MENU_FRAME, 'exit': ('on_click_in', '菜单', '入口-指南')},
        {'frame': _GUIDE_FRAME, 'exit': ('on_click_in', '星际和平指南', 'TAB-逐光捡金')},
        {'frame': _CATEGORY_FH_FRAME, 'exit': ('on_click_in', '指南-逐光捡金', '按钮-传送-卡片式')},
        {'frame': _SELECT_FRAME},
    ])
    op = _WatchedGoto(test_context, TLMode.FORGOTTEN_HALL)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'全链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 4, (
        f'应推进到选关帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area('大世界-普通', '左上图标-菜单'), \
        f'菜单图标点击缺失:{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area('菜单', '入口-指南'), \
        '菜单指南入口点击缺失'
    assert fixture_controller.click_hit_area('星际和平指南', 'TAB-逐光捡金'), \
        'tab 点击缺失'
    assert fixture_controller.click_hit_area('指南-逐光捡金', '分类-忘却之庭'), \
        '目标分类点击缺失(显式选分类,不依赖默认态)'
    assert fixture_controller.click_hit_area('指南-逐光捡金', '按钮-传送-卡片式'), \
        '卡片式传送点击缺失'


def test_fh_from_category_wrong_panel(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """分类页起跑且当前面板非目标(异相仲裁选中):显式点忘却之庭→面板切换→传送→选关。"""
    frames = [_CATEGORY_AA_FRAME, _CATEGORY_FH_FRAME, _SELECT_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _CATEGORY_AA_FRAME, 'exit': ('on_click_in', '指南-逐光捡金', '分类-忘却之庭')},
        {'frame': _CATEGORY_FH_FRAME, 'exit': ('on_click_in', '指南-逐光捡金', '按钮-传送-卡片式')},
        {'frame': _SELECT_FRAME},
    ])
    op = _WatchedGoto(test_context, TLMode.FORGOTTEN_HALL)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'分类页起跑未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 2, (
        f'应推进到选关帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area('指南-逐光捡金', '分类-忘却之庭'), \
        '目标分类点击缺失'
    assert fixture_controller.click_hit_area('指南-逐光捡金', '按钮-传送-卡片式'), \
        '卡片式传送点击缺失'


def test_already_at_select_zero_click(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """已在选关混沌回忆视图干净态:零点击直成功(判定→收尾即成功)。"""
    _require_screens(test_context, [_SELECT_FRAME])
    fixture_controller.set_phases([{'frame': _SELECT_FRAME}])
    op = _WatchedGoto(test_context, TLMode.FORGOTTEN_HALL)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, f'应直成功:status={result.status!r}'
    assert fixture_controller.phase_idx == 0, '不应有帧推进'
    assert not fixture_controller.recorded_clicks, (
        f'已在目标态应零点击:{fixture_controller.recorded_clicks}')


def test_as_from_category_success(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """末日幻影全链(分类页起):选中→传送→开场介绍页双锚(已更新+前往挑战)→
    点前往挑战→选关双锚(标题+难度)成功。

    开场页双锚是防误点关键:开场页整屏无标题文本(纯美术字),选关页有前往
    挑战按钮但无已更新标签——单前往挑战锚会把选关误判成开场页无限点空按钮。"""
    frames = [_CATEGORY_AS_FRAME, _AS_INTRO_FRAME, _AS_SELECT_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _CATEGORY_AS_FRAME, 'exit': ('on_click_in', '指南-逐光捡金', '按钮-传送-卡片式')},
        {'frame': _AS_INTRO_FRAME, 'exit': ('on_click_in', '末日幻影-开场', '按钮-前往挑战')},
        {'frame': _AS_SELECT_FRAME},
    ])
    op = _WatchedGoto(test_context, TLMode.APOCALYPTIC_SHADOW)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'末日幻影全链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 2, (
        f'应推进到选关帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area('指南-逐光捡金', '分类-末日幻影'), \
        '目标分类点击缺失(显式选分类,不依赖默认态)'
    assert fixture_controller.click_hit_area('指南-逐光捡金', '按钮-传送-卡片式'), \
        '卡片式传送点击缺失'
    assert fixture_controller.click_hit_area('末日幻影-开场', '按钮-前往挑战'), \
        '开场页前往挑战点击缺失'
