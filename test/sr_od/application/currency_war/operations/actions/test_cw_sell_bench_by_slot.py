"""CwSellBenchBySlot 浮层守卫安装点测试(harness 剧本 + 真建档派生)。

锁的设计约定(被测单一源 = cw_sell_bench_by_slot):
- 浮层守卫安装口径与现役安装点同构(DragCwChar.drag 等):合成确认浮层
  在场帧 → drag_sell round_fail(未执行:浮层在场前缀 + 家族指引),
  拖拽零发出(执行前输入契约拒绝);受阻码命中登记行
  (_PREP_RECEIPT_BLOCK_CODES);
- 干净备战帧 → 拖拽照常发出(起点 = 备战栏-N area rect 裸中心,终点 =
  出售区单一源区域-出售区中心,期望值从同源 screen_info 现算);
- 守卫置于 mechanical_io_allowed() 门内 = sim 零触及:sim 装配下浮层在
  场也不拦(守卫不跑),机械段静默(drag_char_guarded sim 分支),节点
  照常 round_success。
"""

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.operations.actions.cw_sell_bench_by_slot import (
    CwSellBenchBySlot,
)
from sr_od.application.currency_war.sim import cw_sim_ports

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
    自动还原,防污染 session 级共享 ctx);默认剧本 = 干净备战帧——守卫
    放行路径在 last_screenshot 缺席时走 op.screenshot(),无剧本帧会
    IndexError。"""
    controller = _SellBySlotTestController(test_context)
    controller.set_phases([{'frame': (_PREP_SCREEN, 'deployed_2star')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def test_overlay_blocked_round_fail(sell_ctx) -> None:
    """安装点行为:合成确认浮层在场帧 → drag_sell round_fail(未执行:
    浮层在场前缀 + 家族指引),零拖拽(执行前输入契约拒绝);受阻码命中
    登记行(非原文兜底)。"""
    from sr_od.application.currency_war.prep_actions import (
        _prep_receipt_block_code,
        drag_overlay_block_status,
    )
    op = CwSellBenchBySlot(sell_ctx, slot=1)
    op.last_screenshot = sell_ctx.load_screen(
        '货币战争-备战-合成确认', '合成确认浮层')
    with fast_sleep(op):
        result = op.drag_sell()
    assert not result.is_success
    assert (result.status or '').startswith('未执行:浮层在场')
    assert '合成确认浮层' in (result.status or '')
    assert _prep_receipt_block_code(result.status) == \
        '未执行:浮层在场(合成确认/角色详情)'
    assert drag_overlay_block_status('合成确认浮层') == result.status
    assert sell_ctx.controller.recorded_drags == []
    assert sell_ctx.controller.recorded_mouse_moves == []


def test_clean_frame_drag_passes(sell_ctx) -> None:
    """干净备战帧 → 守卫放行,拖拽照常发出:起点 = 备战栏-slot area 裸
    中心,终点 = 出售区单一源(期望双端从真建档现算);节点 round_success。"""
    op = CwSellBenchBySlot(sell_ctx, slot=1)
    with fast_sleep(op):
        result = op.drag_sell()
    assert result.is_success
    expected_start = _expected_center(sell_ctx, _PREP_SCREEN, '备战栏-1')
    expected_end = _expected_center(sell_ctx, _PREP_SCREEN, '区域-出售区')
    assert sell_ctx.controller.recorded_drags == [
        (expected_start, expected_end)]


def test_sim_gate_overlay_untouched(sell_ctx, monkeypatch) -> None:
    """sim 装配 + 浮层帧在场:守卫在 mechanical_io_allowed() 门内零触及
    (不拦不截帧),机械段静默(drag_char_guarded sim 分支),节点照常
    round_success 且零拖拽——守卫若被移出 sim 门,浮层帧在场会 round_fail,
    本测试转红(锁安装口径)。两 port 一起桩:守卫机械门读
    mechanical_io_allowed(直读装配槽),宿主读 sim_backend_installed。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed', lambda: False)
    monkeypatch.setattr(cw_sim_ports, 'sim_backend_installed', lambda: True)
    op = CwSellBenchBySlot(sell_ctx, slot=1)
    op.last_screenshot = sell_ctx.load_screen(
        '货币战争-备战-合成确认', '合成确认浮层')
    with fast_sleep(op):
        result = op.drag_sell()
    assert result.is_success
    assert sell_ctx.controller.recorded_drags == []
    assert sell_ctx.controller.recorded_mouse_moves == []
