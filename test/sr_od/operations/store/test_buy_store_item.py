"""BuyStoreItem 流程测试(fixture 剧本,不连真游戏)。

锁设计约定(见 src op 模块与 docs/game/screens/store.md §8):
- 可购买链:弹窗点「拉满」(模板钮) → 点确认 → 「获得物品」弹窗点「点击空白处关闭」;
- 售罄链(周常已购的常态分支):弹窗状态横条「已售罄」→ 点取消退出,全程不触确认按钮。

画面事实出处:购买数量弹窗与兑换弹窗为同一游戏组件,共用档案「商店-兑换弹窗」,
素材 = screens/商店-兑换弹窗/ 与 screens/获得物品/ 下实拍 webp。列表页商品卡定位
(模板匹配)无星尘之礼帧,经 get_item_pos 桩直通弹窗阶段,不在本测试锁面内。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.geometry.point import Point
from sr_od.operations.store.buy_store_item import BuyStoreItem
from sr_od.operations.store.store_const import StoreItemEnum

_POPUP = '商店-兑换弹窗'
_LIST_FRAME = ('商店', '余烬兑换-首屏通票')
"""仅作首尾帧(商品卡定位已桩掉,帧内容不参与断言)"""
_POPUP_PURCHASABLE = (_POPUP, '星轨专票-可购买')
_POPUP_SOLD_OUT = (_POPUP, '气态流体-已售罄')
"""售罄帧取本 op 实际目标商品(气态流体)的实拍"""
_REWARD_FRAME = ('获得物品', '余烬兑换领取后')
"""购买确认后的「获得物品」弹窗帧(底部「点击空白处关闭」提示)"""


class _WatchedBuy(WatchdogOperationMixin, BuyStoreItem):
    """带看门狗 + 关闭游戏窗口前置(MockController 环境无真实窗口)。"""

    watchdog_max_rounds: int = 40

    def __init__(self, ctx, item, buy_num: int) -> None:
        BuyStoreItem.__init__(self, ctx, item, buy_num)
        self.need_check_game_win = False


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


def _make_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> _WatchedBuy:
    monkeypatch.setattr(BuyStoreItem, 'get_item_pos',
                        lambda self, screen: Point(400, 300))
    return _WatchedBuy(test_context, StoreItemEnum.GASEOUS_LIQUID.value, buy_num=0)


def _run_execute(test_context: SrTestContext, op: object) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def test_buy_clicks_max_confirm_then_closes(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """可购买链:点拉满 → 点确认 → 获得物品弹窗点「点击空白处关闭」收尾。"""
    frames = [_LIST_FRAME, _POPUP_PURCHASABLE, _REWARD_FRAME]
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')
    fixture_controller.set_phases([
        # 列表页:choose_item 点击不带坐标(点当前光标位),harness 无法按落点推进,
        # 用截图轮数推进到弹窗帧
        {'frame': _LIST_FRAME, 'exit': ('on_polls', 1)},
        {'frame': _POPUP_PURCHASABLE,
         'exit': ('on_click_in', _POPUP, '按钮-拉满')},
        {'frame': _POPUP_PURCHASABLE,
         'exit': ('on_click_in', _POPUP, '按钮-确认')},
        {'frame': _REWARD_FRAME,
         'exit': ('on_click_in', _POPUP, '点击空白处关闭')},
        {'frame': _LIST_FRAME},
    ])
    result = _run_execute(test_context, _make_op(test_context, monkeypatch))

    assert result.success, (
        f'可购买链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area(_POPUP, '按钮-拉满'), '拉满按钮点击缺失'
    assert fixture_controller.click_hit_area(_POPUP, '按钮-确认'), '确认按钮点击缺失'
    assert fixture_controller.click_hit_area(_POPUP, '点击空白处关闭'), \
        '购买后未点「点击空白处关闭」关闭获得物品弹窗'


def test_sold_out_bar_cancels_without_confirm(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """售罄链:横条「已售罄」→ 点取消正常退出,不触确认按钮(消耗红线)。"""
    frames = [_LIST_FRAME, _POPUP_SOLD_OUT]
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')
    fixture_controller.set_phases([
        {'frame': _LIST_FRAME, 'exit': ('on_polls', 1)},
        {'frame': _POPUP_SOLD_OUT,
         'exit': ('on_click_in', _POPUP, '按钮-取消')},
        {'frame': _LIST_FRAME},
    ])
    result = _run_execute(test_context, _make_op(test_context, monkeypatch))

    assert result.success, (
        f'售罄分支应点取消正常结束:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area(_POPUP, '按钮-取消'), '售罄应点取消关闭弹窗'
    assert not fixture_controller.click_hit_area(_POPUP, '按钮-确认'), \
        '售罄弹窗不得触碰确认按钮'
