"""ChallengeOrnamentExtraction.after_battle_result 战败分支测试(节点级 mock)。

覆盖(2026-08-30 实证):饰品提取战败结算 = 「大世界-战斗失败」屏,没有
再来一次/退出关卡 按钮 → 原 logic 找不到按钮直接 FAIL。修复 = 战败屏在场
先点「点击空白区域继续」,按已退出路由交 wait_back(等不到大世界由外层
开拓力计划重试语义兜底,失败有界)。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.div_uni.operations.ornamenet_extraction import (
    ChallengeOrnamentExtraction,
)
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


def test_wait_back_closes_oe_page_before_world_check() -> None:
    """战败点空白落到饰品提取 boss 选择页(全屏 UI 无角色图标) → 先点右上 X 关页
    交 retry 重判,不得误判成「回不到大世界」而 FAIL(2026-08-31 实证卡死形态)。"""
    op = _make_op()
    retry_result = MagicMock()
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)) as find_area, \
         patch.object(op, 'round_by_click_area', return_value=MagicMock()) as click_area, \
         patch.object(op, 'round_retry', return_value=retry_result) as round_retry:
        result = op.wait_back()
    assert result is retry_result
    round_retry.assert_called_once_with('关闭模式页', wait=1)
    click_area.assert_called_once_with('饰品提取', '按钮-关闭')
    # 命中饰品提取页即短路,不再查大世界
    find_area.assert_called_once()


def test_wait_back_fails_bounded_after_five_defeats() -> None:
    """大世界在场且 battle_fail_times≥5 → round_fail('战斗失败过多') 有界退出。
    饰品提取战败不耗体力,无此出口打不过的组合会无限「重进→败→回大世界」。"""
    op = _make_op()
    op.battle_fail_times = 5
    fail_result = MagicMock()
    with patch.object(op, 'round_by_find_area', side_effect=[
        MagicMock(is_success=False),  # 不在饰品提取 boss 选择页
        MagicMock(is_success=True),  # 大世界角色图标在场
    ]), \
         patch.object(op, 'round_fail', return_value=fail_result) as round_fail:
        result = op.wait_back()
    assert result is fail_result
    round_fail.assert_called_once_with('战斗失败过多')


def test_wait_back_routes_retry_when_runs_remain() -> None:
    """大世界在场、失败未超限且次数未完成 → round_success('重新选择次数')
    回传送节点重试(战败路径自行回首页后按现役决策链继续打的核心路由)。"""
    op = _make_op()
    op.run_times = 2
    success_result = MagicMock()
    with patch.object(op, 'round_by_find_area', side_effect=[
        MagicMock(is_success=False),
        MagicMock(is_success=True),
    ]), \
         patch.object(op, 'round_success', return_value=success_result) as round_success:
        result = op.wait_back()
    assert result is success_result
    round_success.assert_called_once_with('重新选择次数')
