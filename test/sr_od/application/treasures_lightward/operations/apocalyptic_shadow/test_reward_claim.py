"""TlRewardClaimOp 奖励领取流程测试(fixture 剧本,不连真游戏)。

锁设计约定(见 src/sr_od/application/treasures_lightward/operations/apocalyptic_shadow/reward_claim.py 模块 docstring 与
docs/game/screens/末日幻影-祭礼奖励.md 建档):
- 全链:选关屏点礼物盒入口 → 永劫祭礼点「领取」→ 获得物品覆盖页点空白关闭
  → 永劫无可领 → 切终局祭礼(列表「难度」行锚验证)→ 终局无可领 → 关闭X 回选关;
- 一键全领语义:每个 tab 全程只点一次「领取」,领取后经覆盖页复查无可领即收口;
- 已领完态(无可领)直接推进不误点;
- 不在选关屏/弹窗 → 显式失败,不盲点。

终局 tab 可领态未归档(当前账号终局无可领):终局领取与永劫领取共用
_claim_round 逻辑,由全链用例的永劫可领段覆盖,不重复造帧。
"""

from __future__ import annotations

import pytest

from sr_od.operations.sr_operation import SrOperation
from sr_od.application.treasures_lightward.operations.apocalyptic_shadow.reward_claim import TlRewardClaimOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_SELECT_FRAME = ('末日幻影-选关', '默认')
_CLAIMABLE_FRAME = ('末日幻影-祭礼奖励', '永劫祭礼-可领')
_OBTAINED_FRAME = ('获得物品', '祭礼领取后')
_CLAIMED_FRAME = ('末日幻影-祭礼奖励', '永劫祭礼-已领取')
_FINAL_FRAME = ('末日幻影-祭礼奖励', '终局祭礼')
_GIFT_SCREEN = '末日幻影-祭礼奖励'


class _WatchedClaim(WatchdogOperationMixin, TlRewardClaimOp):
    """带看门狗 + 跳过游戏窗口前置节点(MockController 无 game_win)。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx) -> None:
        # 跳过 TlRewardClaimOp.__init__(其基类默认 need_check_game_win=True),
        # 手动补齐它初始化的领取预算字段(两处初始化必须同步)。
        SrOperation.__init__(self, ctx, op_name='测试-领取奖励', need_check_game_win=False)
        self._claim_clicks: int = 0


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


def test_full_claim_chain(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """全链:选关→礼物盒→永劫领取→获得物品关闭→切终局→关闭X回选关。"""
    frames = [_SELECT_FRAME, _CLAIMABLE_FRAME, _OBTAINED_FRAME,
              _CLAIMED_FRAME, _FINAL_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        # 选关屏:点礼物盒入口 → 弹窗可领帧
        {'frame': _SELECT_FRAME,
         'exit': ('on_click_in', '末日幻影-选关', '入口-祭礼奖励')},
        # 永劫可领:点「领取」(按钮列 rect 内) → 获得物品页
        {'frame': _CLAIMABLE_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, '按钮-领取')},
        # 获得物品覆盖页:点空白处关闭 → 回弹窗已领取态
        {'frame': _OBTAINED_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, '按钮-点击空白处关闭')},
        # 永劫已领取(无可领):点终局 tab → 终局帧
        {'frame': _CLAIMED_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, 'tab-终局祭礼')},
        # 终局(无可领):点关闭X → 选关屏
        {'frame': _FINAL_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, '按钮-关闭X')},
        {'frame': _SELECT_FRAME},
    ])
    op = _WatchedClaim(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'全链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 5, (
        f'应推进到选关帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area(_SELECT_FRAME[0], '入口-祭礼奖励'), \
        f'礼物盒入口点击缺失:{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, '按钮-领取'), \
        '永劫「领取」点击缺失'
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, '按钮-点击空白处关闭'), \
        '获得物品页空白关闭点击缺失'
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, 'tab-终局祭礼'), \
        '终局 tab 切换点击缺失'
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, '按钮-关闭X'), \
        '关闭X 点击缺失'


def test_already_claimed_passes_through(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """已在弹窗且无可领:零领取点击,切终局确认后关闭返回。"""
    frames = [_CLAIMED_FRAME, _FINAL_FRAME, _SELECT_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        # 永劫已领取(无可领):点终局 tab
        {'frame': _CLAIMED_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, 'tab-终局祭礼')},
        # 终局(无可领):点关闭X
        {'frame': _FINAL_FRAME,
         'exit': ('on_click_in', _GIFT_SCREEN, '按钮-关闭X')},
        {'frame': _SELECT_FRAME},
    ])
    op = _WatchedClaim(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'无可领态应直接收口成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.phase_idx == 2, (
        f'应推进到选关帧:phase_idx={fixture_controller.phase_idx}')
    assert not fixture_controller.click_hit_area(_GIFT_SCREEN, '按钮-领取'), (
        f'无可领态不应点「领取」:{fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, 'tab-终局祭礼'), \
        '终局 tab 仍应切换确认(两 tab 分别核对)'
    assert fixture_controller.click_hit_area(_GIFT_SCREEN, '按钮-关闭X'), \
        '关闭X 点击缺失'


def test_wrong_screen_fails(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """不在选关屏/弹窗:显式失败,零点击(不盲点、不自行导航)。"""
    _require_screens(test_context, [('大世界', '普通')])
    fixture_controller.set_phases([{'frame': ('大世界', '普通')}])
    op = _WatchedClaim(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert not result.success, '错屏应显式失败而非假装成功'
    assert not fixture_controller.recorded_clicks, (
        f'错屏不应有任何点击:{fixture_controller.recorded_clicks}')
