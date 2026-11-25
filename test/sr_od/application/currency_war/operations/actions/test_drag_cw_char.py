"""DragCwChar 后排布局档声明守卫 + 守卫宿主迁移测试(harness 剧本 + 真建档派生)。

锁的设计约定(被测单一源 = drag_cw_char):
- 涉 back 声明守卫四态(构造期 fail-closed):零声明(两参数均缺省)→ ValueError
  带指引;仅传 back_slot_count → 键域(6-9)校验,域外 ValueError;仅传
  back_centers → 豁免放行(显式几何覆盖);双传 → 放行且 back_centers 优先;
  不涉 back 全缺省 → 构造成功;
- 后排槽位解析按 back_slot_count 布局档前缀查 screen_info(期望值从同源
  yml 现算非手抄);拖点 = area rect 裸中心(角色拖动族权威派生式,非
  row_drag_points +21 族,锁两族分域不串);
- 机械段走 prep_actions.drag_char_guarded 守卫宿主:窗口失焦先激活再拖;
  焦点正常不激活;sim 装配(后端安装)整段机械静默零拖拽。
"""

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.operations.actions.drag_cw_char import (
    DragCwChar,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'


class _DragTestController(FixtureController):
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


class _FakeGameWinFocus:
    """game_win 焦点替身:is_win_active 可设,active() 记录调用。"""

    def __init__(self, is_win_active: bool) -> None:
        self.is_win_active: bool = is_win_active
        self.win_title: str = '<fixture-fake-game-window>'
        self.active_calls: int = 0

    def active(self) -> None:
        self.active_calls += 1


def _expected_center(ctx, area_name: str) -> tuple[int, int]:
    """期望拖点从同源 screen_info 档案现算(rect 中心;角色拖动族裸中心
    权威派生式,非 +21)。"""
    area = ctx.screen_loader.get_area(_PREP_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {_PREP_SCREEN}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


def _pt_tuple(point) -> tuple[int, int]:
    """Point → int 元组(Point 不与 tuple 判等,断言统一取坐标元组)。"""
    return (int(point.x), int(point.y))


@pytest.fixture
def drag_ctx(test_context, monkeypatch):
    """共享 ctx 的拖拽测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx);默认剧本 = 干净备战帧——浮层守卫
    在 last_screenshot 缺席时走 op.screenshot(),无剧本帧会 IndexError。"""
    controller = _DragTestController(test_context)
    controller.set_phases([{'frame': (_PREP_SCREEN, 'deployed_2star')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


# ---------------------------------------------------------------- 构造期守卫四态

def test_guard_rejects_zero_declaration(drag_ctx) -> None:
    """涉 back 零声明(两参数均缺省)→ 构造期 ValueError,文案带指引
    (零声明静默落基线 = 布局骑界事故形态,响亮拒绝即修法本体)。"""
    with pytest.raises(ValueError) as exc_info:
        DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                   to_row='back', to_idx=2)
    msg = str(exc_info.value)
    assert '零声明' in msg
    assert 'back_slot_count' in msg
    assert 'back_centers' in msg


def test_guard_rejects_slot_count_out_of_domain(drag_ctx) -> None:
    """仅传 back_slot_count → 键域(6-9)校验,域外构造期 ValueError。"""
    for bad in (5, 10):
        with pytest.raises(ValueError) as exc_info:
            DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                       to_row='back', to_idx=2, back_slot_count=bad)
        assert '域外' in str(exc_info.value)


def test_guard_back_centers_alone_is_exempt(drag_ctx) -> None:
    """仅传 back_centers(slot_count 缺省)→ 豁免放行(显式几何覆盖,
    存量直调形态兼容,E2 复现形态保真)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='back', to_idx=2,
                    back_centers=[[100, 600], [200, 600]])
    assert op.back_slot_count is None
    assert op.back_centers is not None


def test_guard_both_declared_passes(drag_ctx) -> None:
    """双传(档 + 实测中心)→ 放行;几何消费 back_centers 优先(覆盖测试
    见 test_back_centers_override_priority)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='back', to_idx=2, back_slot_count=7,
                    back_centers=[[100, 600], [200, 600]])
    assert op.back_slot_count == 7


def test_guard_no_back_row_all_default_ok(drag_ctx) -> None:
    """不涉 back 全缺省 → 构造成功(None 合法,守卫只辖涉 back 拖拽)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=9,
                    to_row='front', to_idx=1)
    assert op.back_slot_count is None
    assert op.back_centers is None


# ---------------------------------------------------------------- 布局档解析

def test_back_slot_count_7_resolves_expanded_archive(drag_ctx) -> None:
    """7 格档解析:back_slot_count=7 → 后排7槽档 area 表(真建档派生断言,
    期望值从 screen_info 现算)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='back', to_idx=2, back_slot_count=7)
    assert _pt_tuple(op._slot_center('back', 2)) == \
        _expected_center(drag_ctx, '后排7槽-2')


def test_back_slot_count_6_resolves_baseline_archive(drag_ctx) -> None:
    """6 格基线回归:back_slot_count=6 → 基线「后排-N」档(防档表错接)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='back', to_idx=2, back_slot_count=6)
    assert _pt_tuple(op._slot_center('back', 2)) == \
        _expected_center(drag_ctx, '后排-2')


def test_drag_points_are_bare_rect_centers(drag_ctx) -> None:
    """拖点权威分域回归:bench→front 拖拽双端 = area rect 裸中心(角色
    拖动族;装备族 +21 派生式在此必不相等,锁分域不被串)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='front', to_idx=2)
    with fast_sleep(op):
        result = op.drag()
    expected_start = _expected_center(drag_ctx, '备战栏-1')
    expected_end = _expected_center(drag_ctx, '前排-2')
    assert op.ctx.controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success


# ---------------------------------------------------------------- back_centers 覆盖优先

def test_back_centers_override_priority(drag_ctx) -> None:
    """覆盖优先序:仅传 / 双传 back_centers 时 back 解析 = 传入实测中心
    (显式几何覆盖压过声明档与基线档)。"""
    centers = [[111, 601], [222, 602], [333, 603], [444, 604]]
    alone = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                       to_row='back', to_idx=2, back_centers=centers)
    both = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                      to_row='back', to_idx=2, back_slot_count=7,
                      back_centers=centers)
    assert _pt_tuple(alone._slot_center('back', 2)) == (222, 602)
    assert _pt_tuple(both._slot_center('back', 2)) == (222, 602)


def test_back_centers_out_of_range_idx_fails_closed(drag_ctx) -> None:
    """back_centers 数组越界 idx → None → STATUS_BAD_SLOT fail(零拖拽)。"""
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='back', to_idx=5,
                    back_centers=[[100, 600], [200, 600]])
    assert op._slot_center('back', 5) is None
    with fast_sleep(op):
        result = op.drag()
    assert not result.is_success
    assert result.status == DragCwChar.STATUS_BAD_SLOT
    assert drag_ctx.controller.recorded_drags == []


# ---------------------------------------------------------------- 守卫宿主迁移(件 2)

def test_focus_guard_activates_on_blur(drag_ctx) -> None:
    """窗口失焦(is_win_active=False)→ 先激活再拖(拖拽仍发出);
    焦点正常(is_win_active=True)→ 不激活。"""
    for is_win_active, expect_activate in ((False, 1), (True, 0)):
        game_win = _FakeGameWinFocus(is_win_active)
        drag_ctx.controller.game_win = game_win
        op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                        to_row='front', to_idx=1)
        drag_ctx.controller.recorded_drags.clear()
        drag_ctx.controller.recorded_mouse_moves.clear()
        with fast_sleep(op):
            result = op.drag()
        assert result.is_success
        assert game_win.active_calls == expect_activate
        expected_start = _expected_center(drag_ctx, '备战栏-1')
        expected_end = _expected_center(drag_ctx, '前排-1')
        assert drag_ctx.controller.recorded_drags == [
            (expected_start, expected_end)]


def test_sim_backend_installed_mechanical_silent(drag_ctx, monkeypatch) -> None:
    """sim 装配态 → 宿主整段静默:拖拽零发出(mouse_move/drag_to 零记录),
    节点照常 round_success(机械静默语义)。两 port 一起桩:守卫机械门读
    mechanical_io_allowed(直读装配槽),宿主/park_cursor 读
    sim_backend_installed。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed', lambda: False)
    monkeypatch.setattr(cw_sim_ports, 'sim_backend_installed', lambda: True)
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='front', to_idx=1)
    with fast_sleep(op):
        result = op.drag()
    assert result.is_success
    assert drag_ctx.controller.recorded_drags == []
    assert drag_ctx.controller.recorded_mouse_moves == []


def test_production_drag_primitive_untouched(drag_ctx) -> None:
    """静态原语 drag_char 直调形态(生产 deploy/sell 消费面)行为不变:
    零守卫零 sim 分支,坐标直拖(宿主迁移只改 op 节点,不动原语本体)。"""
    from one_dragon.base.geometry.point import Point
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='front', to_idx=1)
    DragCwChar.drag_char(op, Point(100, 200), Point(300, 400))
    assert drag_ctx.controller.recorded_drags == [((100, 200), (300, 400))]


def test_production_primitive_docstring_contract() -> None:
    """生产静态原语不涉 back 参数面(构造参数守卫只辖 op 形态,原语消费方
    deploy/sell 传坐标不受守卫波及——drag_char 静态方法签名零变化)。"""
    import inspect
    sig = inspect.signature(DragCwChar.drag_char)
    assert list(sig.parameters) == ['op', 'src', 'dst']


# ---------------------------------------------------------------- 浮层守卫安装点

def test_overlay_blocked_round_fail(drag_ctx) -> None:
    """安装点行为:合成确认浮层在场帧 → drag round_fail(未执行:浮层在场
    前缀 + 家族指引),零拖拽(执行前输入契约拒绝);受阻码命中登记行。"""
    from sr_od.application.currency_war.prep_actions import (
        _prep_receipt_block_code,
        drag_overlay_block_status,
    )
    op = DragCwChar(drag_ctx, from_row='bench', from_idx=1,
                    to_row='front', to_idx=1)
    op.last_screenshot = drag_ctx.load_screen(
        '货币战争-备战-合成确认', '合成确认浮层')
    with fast_sleep(op):
        result = op.drag()
    assert not result.is_success
    assert (result.status or '').startswith(DragCwChar.STATUS_OVERLAY_BLOCKED)
    assert '合成确认浮层' in (result.status or '')
    assert _prep_receipt_block_code(result.status) == \
        '未执行:浮层在场(合成确认/角色详情)'
    assert drag_overlay_block_status('合成确认浮层') == result.status
    assert drag_ctx.controller.recorded_drags == []
