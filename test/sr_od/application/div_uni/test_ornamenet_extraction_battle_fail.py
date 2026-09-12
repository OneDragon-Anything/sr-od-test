"""ChallengeOrnamentExtraction.after_battle_result 战败分支测试(节点级 mock)。

覆盖(2026-08-30 实证):饰品提取战败结算 = 「大世界-战斗失败」屏,没有
再来一次/退出关卡 按钮 → 原 logic 找不到按钮直接 FAIL。修复 = 战败屏在场
先点「点击空白区域继续」,按已退出路由交 wait_back(等不到大世界由外层
开拓力计划重试语义兜底,失败有界)。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.div_uni.operations.ornamenet_extraction import ChallengeOrnamentExtraction
from sr_od.context.sr_context import SrContext
from sr_od.interastral_peace_guide.guide_def import GuideMission


def _make_op() -> ChallengeOrnamentExtraction:
    ctx = MagicMock(spec=SrContext)
    mission = MagicMock(spec=GuideMission)
    op = ChallengeOrnamentExtraction(ctx, mission=mission, run_times=1, diff=0,
                                     file_num=0, team_name='', support_character='')
    op.last_screenshot = object()
    # handle_init 正常初始化;节点单测不跑 handle_init 需手供
    op.battle_fail_times = 0
    op.battle_success_times = 0
    op.choose_times = 1
    return op


def test_fail_screen_clicks_empty_and_routes_exit() -> None:
    """战败屏在场 → 点空白继续 → 按退出路由 success(交 wait_back)。"""
    op = _make_op()
    click_result = MagicMock()
    click_result.is_success = True
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)) as find_area, \
         patch.object(op, 'round_by_find_and_click_area', return_value=click_result) as click_area, \
         patch.object(op, 'round_success', return_value='EXIT') as round_success:
        result = op.after_battle_result()
    assert result == 'EXIT'
    round_success.assert_called_once_with('退出关卡按钮')
    # 战败屏分支只点一次(空白继续),不再找 战斗画面 按钮
    click_area.assert_called_once()
    find_area.assert_called_once()


def test_fail_screen_click_miss_propagates() -> None:
    """空白点击没落地 → 透传点击结果(retry 语义)。"""
    op = _make_op()
    click_result = MagicMock()
    click_result.is_success = False
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)), \
         patch.object(op, 'round_by_find_and_click_area', return_value=click_result):
        result = op.after_battle_result()
    assert result is click_result


def test_win_screen_falls_through_to_button_logic() -> None:
    """非战败屏(胜利结算) → 不进战败分支,走 再来一次/退出 按钮逻辑。"""
    op = _make_op()
    button_result = MagicMock()
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=False)) as find_area, \
         patch.object(op, 'round_by_find_and_click_area', return_value=button_result) as click_area:
        result = op.after_battle_result()
    assert result is button_result
    find_area.assert_called_once()
    # 胜利且未超次数 → 找 再来一次按钮
    click_area.assert_called_once()
