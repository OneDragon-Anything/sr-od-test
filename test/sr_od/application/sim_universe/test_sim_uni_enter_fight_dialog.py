"""SimUniEnterFight.enter_fight 提示弹窗分支测试(节点级,mock 一帧 + 调节点 + 断言)。

覆盖(2026-08-30 实证):
- 差分宇宙系入口(饰品提取等)首次开战弹「当前不存在任何存档,是否直接开始战斗?」
  确认框,画面压暗后落进未知态 → enter_fight 无限等待(卡死 20+ 分钟,两次实跑复现)。
- 修复 = enter_fight 顶部先检测 挑战副本/提示弹框-标题 → 点 提示弹框-确认 继续。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.sim_universe.operations.sim_uni_enter_fight import SimUniEnterFight
from sr_od.context.sr_context import SrContext
from sr_od.screen_state import common_screen_state


def _make_op() -> SimUniEnterFight:
    ctx = MagicMock(spec=SrContext)
    ctx.sim_uni_challenge_config = None
    op = SimUniEnterFight(ctx, no_attack=True)
    op.last_screenshot = object()
    op.current_state = ''  # handle_init 正常初始化;节点单测不跑 handle_init 需手供
    op.first_screen_check = True
    return op


def test_dialog_branch_confirms_and_waits() -> None:
    """提示弹窗在场 → 点确认 → round_wait(等战斗画面出现),不落未知态。"""
    op = _make_op()
    click_result = MagicMock()
    click_result.is_success = True
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)) as find_area, \
         patch.object(op, 'round_by_find_and_click_area', return_value=click_result) as click_area, \
         patch.object(op, 'round_wait', return_value='WAIT') as round_wait:
        result = op.enter_fight()
    assert result == 'WAIT'
    find_area.assert_called_once()
    click_area.assert_called_once()


def test_dialog_branch_click_fail_propagates() -> None:
    """弹窗在但确认点击没落地 → 返回点击结果(retry 语义),不继续状态分类。"""
    op = _make_op()
    click_result = MagicMock()
    click_result.is_success = False
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=True)) as find_area, \
         patch.object(op, 'round_by_find_and_click_area', return_value=click_result) as click_area:
        result = op.enter_fight()
    assert result is click_result
    find_area.assert_called_once()
    click_area.assert_called_once()


def test_no_dialog_falls_through_to_state_branch() -> None:
    """无弹窗 → 不点任何东西,走原状态分类(no_attack+大世界 → 直接成功)。"""
    op = _make_op()
    with patch.object(op, 'round_by_find_area', return_value=MagicMock(is_success=False)) as find_area, \
         patch.object(op, 'round_by_find_and_click_area') as click_area, \
         patch('sr_od.application.sim_universe.sim_uni_screen_state.get_sim_uni_screen_state',
               return_value=common_screen_state.ScreenState.NORMAL_IN_WORLD.value), \
         patch.object(op, 'round_success', return_value='SUCCESS') as round_success:
        result = op.enter_fight()
    assert result == 'SUCCESS'
    find_area.assert_called_once()
    click_area.assert_not_called()
    round_success.assert_called_once()
