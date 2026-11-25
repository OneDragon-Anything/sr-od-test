"""CwSellBenchBySlot 执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(被测单一源 = cw_sell_bench_by_slot):机械拖拽的起终点——
起点 = 备战栏-N area rect 裸中心,终点 = 出售区单一源区域-出售区中心,
期望值从同源 screen_info 现算。本 op 不读屏(动作 op 零读屏),只负责把拖拽
发出去。
"""

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.operations.actions.cw_sell_bench_by_slot import (
    CwSellBenchBySlot,
)

_PREP_SCREEN = '货币战争-备战'


class _SellBySlotTestController(FixtureController):
    """补拖拽 op 触达面的记录 stub:mouse_move / drag_to 双端记录。"""

    def __init__(self, ctx) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_drags: list[tuple[tuple[int, int] | None,
                                        tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        self.recorded_mouse_moves.append((int(pos.x), int(pos.y)))

    def drag_to(self, end, start=None, duration: float = 0.5,
                hold_time: float = 0.0) -> None:
        start_pt = ((int(start.x), int(start.y)) if start is not None
                    else None)
        self.recorded_drags.append((start_pt, (int(end.x), int(end.y))))


def _expected_center(ctx, screen_name: str, area_name: str) -> tuple[int, int]:
    """期望拖点从同源 screen_info 档案现算(rect 裸中心;角色拖动族
    权威派生式,非 row_drag_points +21 族)。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {screen_name}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


@pytest.fixture
def sell_ctx(test_context, monkeypatch):
    """共享 ctx 的卖槽测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx)。"""
    controller = _SellBySlotTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def test_clean_frame_drag_passes(sell_ctx) -> None:
    """拖拽照常发出:起点 = 备战栏-slot area 裸中心,终点 = 出售区单一源
    (期望双端从真建档现算);节点 round_success。夹具不设任何帧——op 全程
    不读屏,读屏即 IndexError,测试通过本身说明零读屏。"""
    op = CwSellBenchBySlot(sell_ctx, slot=1)
    with fast_sleep(op):
        result = op.drag_sell()
    assert result.is_success
    expected_start = _expected_center(sell_ctx, _PREP_SCREEN, '备战栏-1')
    expected_end = _expected_center(sell_ctx, _PREP_SCREEN, '区域-出售区')
    assert sell_ctx.controller.recorded_drags == [
        (expected_start, expected_end)]
