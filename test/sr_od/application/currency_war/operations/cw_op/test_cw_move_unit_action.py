"""CwActionMoveUnitOp 坐标参数面迁移执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(统一拖动参数面迁移形态;被测单一源 = cw_move_unit_action):
- 守卫断言(domain 非法 / slot 越界三域含负下标 / back_slot_count 域外)
  = AssertionError 响亮暴露零拖拽(禁兜底坐标);
- 拖点静态解析:实机形态拖拽双端 = row_area_centers 裸中心(角色拖动族
  权威派生式,期望值从同源 yml 现算非手抄);后排扩格槽按 back_slot_count
  档位表解析(旧守卫表长只匹配基线 6 的潜在 bug 已消灭);
- round detail 组装形态:记账拒单帧 detail 带「记账拒单:<reason>(拖拽已
  发生,账未落)」段,正常记账帧与 gs 缺席帧不带;
- sim 形态(port 关闭)机械零调用,自上报照走。
"""

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_move_unit_action import (
    CwActionMoveUnitOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _MoveTestController(FixtureController):
    """补统一拖动 op 触达面的记录 stub:mouse_move 记录 + drag_to 双端记录。"""

    def __init__(self, ctx) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_drags: list[tuple[tuple[int, int],
                                        tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        self.recorded_mouse_moves.append((int(pos.x), int(pos.y)))

    def drag_to(self, end, start=None, duration: float = 0.5,
                hold_time: float = 0.0) -> None:
        start_pt = ((int(start.x), int(start.y)) if start is not None
                    else None)
        self.recorded_drags.append((start_pt, (int(end.x), int(end.y))))


def _expected_center(ctx, area_name: str) -> tuple[int, int]:
    """期望拖点从同源 screen_info 档案现算(rect 中心;角色拖动族裸中心
    权威派生式,非 +21)。"""
    area = ctx.screen_loader.get_area(_PREP_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {_PREP_SCREEN}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


@pytest.fixture
def move_ctx(test_context, monkeypatch):
    """共享 ctx 的统一拖动测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx)。"""
    controller = _MoveTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(move_ctx, param: CwActionMoveUnitParam,
             ) -> tuple[CwActionMoveUnitOp, _MoveTestController]:
    controller = move_ctx.controller
    assert isinstance(controller, _MoveTestController)
    return CwActionMoveUnitOp(move_ctx, param), controller


def _unit(char_id: str, star: int = 2) -> Unit:
    return Unit(char_id=char_id, star=star, equips=[])


def _attach_match_gs(move_ctx, monkeypatch, bench_slots: list,
                     front_slots: list | None = None) -> GameState:
    """挂假局(懒建 gs)并种子 bench/deployed 视图,供自上报走通(与观察链
    同写入口 gs.observe;cw_match 经 monkeypatch 还原。session 用
    SimpleNamespace = 可弱引用可挂属性,game_state_of 惰建单例跨调用稳定)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(move_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.bench, BenchView(slots=bench_slots,
                                   capacity=BENCH_CAPACITY_DEFAULT),
               sig=_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=front_slots
                            if front_slots is not None else [None] * 4,
                            back_slots=[None] * 6),
               sig=_OBS)
    return gs


def test_guard_assertions(move_ctx) -> None:
    """守卫断言:domain 非法 / slot 越界(三域 + 负下标)/ back_slot_count
    域外 → AssertionError 且零拖拽。"""
    cases = [
        CwActionMoveUnitParam(src_domain='mid', src_slot=1,
                              dst_domain='front', dst_slot=1),
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='stage', dst_slot=1),
        CwActionMoveUnitParam(src_domain='bench', src_slot=9,
                              dst_domain='front', dst_slot=1),
        CwActionMoveUnitParam(src_domain='bench', src_slot=-1,
                              dst_domain='front', dst_slot=1),
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='front', dst_slot=0),
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='front', dst_slot=5),
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='back', dst_slot=7),
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='back', dst_slot=1,
                              back_slot_count=5),
    ]
    for param in cases:
        op, controller = _make_op(move_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_drags == []


def test_live_drag_bench_to_front(move_ctx) -> None:
    """实机形态:拖拽双端 = 备战栏/前排 area 裸中心(角色拖动族权威式)。"""
    param = CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                  dst_domain='front', dst_slot=2,
                                  reason='deploy_diff_place')
    op, controller = _make_op(move_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(move_ctx, '备战栏-1')
    expected_end = _expected_center(move_ctx, '前排-2')
    assert controller.recorded_mouse_moves[0] == expected_start
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success
    # gs 缺席(无局)= 无 outcome,detail 不带拒单段(锁 detail 组装形态)
    assert '记账拒单' not in (result.status or '')


def test_back_expanded_slot_resolves_archive(move_ctx) -> None:
    """后排扩格槽新行为:back_slot_count=7 → 后排7槽档 area 表解析
    (行为修复锁测——旧点表只匹配基线 6 槽形态下 slot 7 必拒)。"""
    param = CwActionMoveUnitParam(src_domain='bench', src_slot=1,
                                  dst_domain='back', dst_slot=7,
                                  back_slot_count=7)
    op, controller = _make_op(move_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(move_ctx, '备战栏-2')
    expected_end = _expected_center(move_ctx, '后排7槽-7')
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success


def test_round_detail_carries_reject_code(move_ctx, monkeypatch) -> None:
    """拒单帧 round detail:源槽空 → success + 拒单码段(机械成功语义
    不变,拖拽照发)。"""
    param = CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                  dst_domain='front', dst_slot=1)
    gs = _attach_match_gs(
        move_ctx, monkeypatch,
        bench_slots=[BenchSlot(kind='empty')] * 9)
    op, controller = _make_op(move_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:src_empty' in (result.status or '')
    assert '拖拽已发生,账未落' in (result.status or '')
    assert len(controller.recorded_drags) == 1
    # 拒单零写:bench 原值保持
    assert gs.bench.value.slots[0].kind == 'empty'


def test_round_detail_clean_on_accounted_frame(move_ctx, monkeypatch) -> None:
    """正常记账帧 detail 不含拒单段;推演矩阵直落分支落账(bench 摘件 +
    deployed 直落)。"""
    param = CwActionMoveUnitParam(src_domain='bench', src_slot=2,
                                  dst_domain='front', dst_slot=1)
    gs = _attach_match_gs(
        move_ctx, monkeypatch,
        bench_slots=[BenchSlot(kind='empty'), BenchSlot(kind='empty'),
                     BenchSlot(kind='unit', unit=_unit('银狼'))]
        + [BenchSlot(kind='empty')] * 6)
    op, _ = _make_op(move_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert gs.deployed.value.front_slots[0] is not None
    assert gs.deployed.value.front_slots[0].char_id == '银狼'
    assert gs.bench.value.slots[2].kind == 'empty'


def test_sim_shape_mechanical_silent_report_walks(move_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用,自上报照走(两执行面同源)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    param = CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                  dst_domain='front', dst_slot=1)
    gs = _attach_match_gs(
        move_ctx, monkeypatch,
        bench_slots=[BenchSlot(kind='unit', unit=_unit('刃', star=3))]
        + [BenchSlot(kind='empty')] * 8)
    op, controller = _make_op(move_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_drags == []
    assert controller.recorded_mouse_moves == []
    assert gs.deployed.value.front_slots[0] is not None
    assert gs.bench.value.slots[0].kind == 'empty'
