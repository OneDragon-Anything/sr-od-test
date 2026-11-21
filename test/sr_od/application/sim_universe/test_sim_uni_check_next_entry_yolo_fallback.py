"""SimUniRunRouteBaseV2.check_next_entry 的 YOLO 兜底测试(节点级 mock)。

覆盖(2026-09-26 一条龙实证):事件层处理完事件后贴墙,激活的战斗入口传送门
在视野内,但入口小图标 SIFT 特征匹配不到 → 转圈 24 次全空判「识别不到任何
内容」整层失败。修复 = SIFT 匹配不到时用 YOLO 检测「模拟宇宙下层入口」
传送门本体,检测到按方向返回 WITH_ENTRY(交由 MoveToNextLevelV3 精确定位)。
"""
from unittest.mock import MagicMock, patch

from sr_od.application.sim_universe.operations.move_v2.sim_uni_run_combat_route_v2 import (
    SimUniRunCombatRouteV2,
)
from sr_od.application.sim_universe.sim_uni_data import SimUniLevelTypeEnum
from sr_od.context.sr_context import SrContext


def _make_op() -> SimUniRunCombatRouteV2:
    # 不用 spec=SrContext:yolo_detector 为运行时挂载属性,spec 会拒绝访问
    ctx = MagicMock()
    op = SimUniRunCombatRouteV2(ctx)
    # check_next_entry 依赖的基类状态
    op.level_type = SimUniLevelTypeEnum.COMBAT.value
    return op


def _detect_result(x1: int, x2: int, category: str = '模拟宇宙下层入口') -> MagicMock:
    result = MagicMock()
    result.x1 = x1
    result.x2 = x2
    result.detect_class.class_category = category
    return result


def _run(op: SimUniRunCombatRouteV2, sift_entries: list, yolo_results: list) -> object:
    """统一环境:跳过 BOSS 出口/视角/截图,SIFT 返回 sift_entries,YOLO 返回 yolo_results。"""
    op._view_up = MagicMock()
    op.screenshot = MagicMock(return_value=object())
    yolo_frame = MagicMock()
    yolo_frame.results = yolo_results
    op.ctx.yolo_detector.sim_uni_yolo.run.return_value = yolo_frame
    with patch('sr_od.application.sim_universe.operations.move_v2.sim_uni_run_route_base_v2.'
               'sim_uni_screen_state.match_next_level_entry', return_value=sift_entries):
        return op.check_next_entry()


def test_sift_miss_yolo_hit_returns_with_entry() -> None:
    """SIFT 匹配不到 + YOLO 检测到入口(画面右侧) → WITH_ENTRY 且方向向右,
    计数清零。修复前此场景返回 NO_ENTRY 直接转圈到放弃。"""
    op = _make_op()
    op.nothing_times = 5
    # 画面中心 960 右侧:delta_angle > 0
    result = _run(op, sift_entries=[], yolo_results=[_detect_result(1200, 1400)])
    assert result.status == '识别到下层入口'
    assert op.next_entry_direction == 1
    assert op.nothing_times == 0


def test_sift_miss_yolo_left_entry_direction_left() -> None:
    """YOLO 入口在画面左侧 → 方向向左。"""
    op = _make_op()
    result = _run(op, sift_entries=[], yolo_results=[_detect_result(300, 500)])
    assert result.status == '识别到下层入口'
    assert op.next_entry_direction == -1


def test_sift_miss_yolo_miss_returns_no_entry() -> None:
    """SIFT 与 YOLO 都没检到入口 → NO_ENTRY(维持原语义,交由转圈)。"""
    op = _make_op()
    result = _run(op, sift_entries=[], yolo_results=[_detect_result(1200, 1400, category='普通怪')])
    assert result.status == '识别不到下层入口'


def test_sift_hit_skips_yolo() -> None:
    """SIFT 命中时保持原逻辑,不调用 YOLO。"""
    op = _make_op()
    sift_entry = MagicMock()
    sift_entry.center.x = 500  # 画面中心左侧
    result = _run(op, sift_entries=[sift_entry], yolo_results=[])
    assert result.status == '识别到下层入口'
    assert op.next_entry_direction == -1
    op.ctx.yolo_detector.sim_uni_yolo.run.assert_not_called()
