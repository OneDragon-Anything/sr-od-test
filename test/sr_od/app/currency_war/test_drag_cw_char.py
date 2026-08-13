"""DragCwChar op 单元测试(槽位拖角色,开发/测试用 + 统一拖拽原语 drag_char)。

验**纯逻辑**:_src_changed 像素 diff 验 + _slot_center 槽中心解析(含 back_centers 覆盖,财富宝钻>6)。
drag_char / drag 节点的 retry/交互(mouse_move/drag_to/中心拖+hold0)经 run_operation live 实测
(bench→bench ✓,commit),此处不重复(交互不便单测);仅锁纯函数回归。
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.operations.dev.drag_cw_char import DragCwChar


def test_src_changed_detects_pixel_diff() -> None:
    """_src_changed:drag 前后源槽像素均值 diff > 阈 → True(角色离开/swap 换人);不变 → False。"""
    src = Point(30, 30)   # 中心在数组内(40×40 crop [10:50] 不越界)
    before = np.zeros((60, 60, 3), np.uint8)
    after_same = before.copy()
    after_diff = np.full((60, 60, 3), 200, np.uint8)   # 均值 diff 200 >> 阈 8
    assert DragCwChar._src_changed(before, after_diff, src) is True
    assert DragCwChar._src_changed(before, after_same, src) is False


def test_src_changed_empty_crop_safe() -> None:
    """_src_changed:crop 越界(空)→ 不崩,返 False。"""
    src = Point(0, 0)   # 中心 0,0 → crop [-20:20,...] 部分越界
    before = np.zeros((50, 50, 3), np.uint8)
    after = np.full((50, 50, 3), 200, np.uint8)
    # 不应崩(越界切片→空或部分,diff 计算安全)
    DragCwChar._src_changed(before, after, src)


def _mock_area(name: str, cx: int, cy: int) -> SimpleNamespace:
    return SimpleNamespace(area_name=name, pc_rect=SimpleNamespace(center=Point(cx, cy)))


def test_slot_center_reads_screen_info() -> None:
    """_slot_center:从 screen_info area_list 读 ``{前排/后排/备战栏}-{idx}`` 中心。"""
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = SimpleNamespace(area_list=[
        _mock_area('前排-1', 743, 398), _mock_area('后排-6', 1315, 669), _mock_area('备战栏-9', 1436, 912),
    ])
    op = DragCwChar(ctx, 'front', 1, 'bench', 9)
    assert (op._slot_center('front', 1).x, op._slot_center('front', 1).y) == (743, 398)
    assert (op._slot_center('back', 6).x, op._slot_center('back', 6).y) == (1315, 669)
    assert (op._slot_center('bench', 9).x, op._slot_center('bench', 9).y) == (1436, 912)
    # 缺该 area / 非法 row → None(不崩;后排>6 见 op TODO)
    assert op._slot_center('front', 2) is None
    assert op._slot_center('xx', 1) is None


def test_slot_center_none_when_no_screen_info() -> None:
    """_slot_center:screen_info 未加载(None)→ None(op 起手 guard,round_fail BAD_SLOT)。"""
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = None
    op = DragCwChar(ctx, 'front', 1, 'front', 2)
    assert op._slot_center('front', 1) is None


def test_slot_center_back_centers_override() -> None:
    """_slot_center:``back_centers`` 覆盖 screen_info(财富宝钻致后排 >6 时调用方传实际后排槽)。

    screen_info「后排-1..6」基准不够 → 调用方传 7 槽的 back_centers → 后排-7 可解析;front/bench 不受影响。
    """
    ctx = MagicMock()
    ctx.screen_loader.get_screen.return_value = SimpleNamespace(area_list=[
        _mock_area('后排-1', 604, 670), _mock_area('后排-6', 1316, 670),   # 基准 6(无后排-7)
    ])
    back_centers = [Point(604 + i * 142, 670) for i in range(7)]   # 7 槽(财富宝钻 +1,等距 142px)
    op = DragCwChar(ctx, 'bench', 1, 'back', 7, back_centers=back_centers)
    # back 走 back_centers:后排-7 = 第 7 个(0-based idx 6)= (1456, 670)
    p7 = op._slot_center('back', 7)
    assert p7 is not None
    assert (p7.x, p7.y) == (604 + 6 * 142, 670)
    # 越界 → None
    assert op._slot_center('back', 8) is None
    # front/bench 仍走 screen_info(不受 back_centers 影响);mock 无 前排-1 → None
    assert op._slot_center('front', 1) is None
