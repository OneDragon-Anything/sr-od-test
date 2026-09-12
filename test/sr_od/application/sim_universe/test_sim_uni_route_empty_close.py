"""SimUniRunRouteBaseV2.turn_when_nothing 弹窗分支测试。

覆盖(2026-08-30 实证):事件/战斗结算后「获得奇物」等「点击空白处关闭」弹窗
未关时,检测器识别不到内容 → turn_when_nothing 打转 → 11 次后楼层校验在
暗罩下 OCR 失败 → STATUS_WRONG_LEVEL_TYPE 整层 FAIL。
修复 = turn_when_nothing 开头先点掉弹窗(蜂巢流程合法中间态)再转视角。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.sim_universe.operations.move_v2.sim_uni_run_route_base_v2 import (
    SimUniRunRouteBaseV2,
)


def _make_op() -> SimUniRunRouteBaseV2:
    """绕过 __init__(需世界号/路线等重依赖),手供节点用到的实例属性。"""
    op = object.__new__(SimUniRunRouteBaseV2)
    op.last_screenshot = object()
    op.nothing_times = 0
    op.moved_to_target = True
    op.turn_direction_when_nothing = 1
    op.ctx = MagicMock()  # 无弹窗路径会转视角,需要 controller
    return op


def test_empty_close_dialog_clicks_and_waits() -> None:
    """弹窗在场 → 点掉 → round_wait(不累计 nothing_times,不转视角)。"""
    op = _make_op()
    click_result = MagicMock()
    click_result.is_success = True
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)) as find_area, \
         patch.object(op, 'round_by_click_area', return_value=click_result) as click_area, \
         patch.object(op, 'round_wait', return_value='WAIT') as round_wait, \
         patch('sr_od.application.sim_universe.operations.move_v2.sim_uni_run_route_base_v2.time') as _time:
        result = op.turn_when_nothing()
    assert result == 'WAIT'
    find_area.assert_called_once()
    click_area.assert_called_once()
    round_wait.assert_called_once()
    assert op.nothing_times == 0  # 弹窗轮不累计「无内容」


def test_no_dialog_falls_through_to_turn() -> None:
    """无弹窗 → 走原转视角逻辑(nothing_times 照常累计)。"""
    op = _make_op()
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=False)) as find_area, \
         patch.object(op, 'round_by_click_area') as click_area, \
         patch.object(op, 'round_success', return_value='OK') as round_success, \
         patch('sr_od.application.sim_universe.operations.move_v2.sim_uni_run_route_base_v2.time') as _time:
        result = op.turn_when_nothing()
    assert result == 'OK'
    find_area.assert_called_once()
    click_area.assert_not_called()
    assert op.nothing_times == 1
