"""CwActionWearEquipOp 坐标参数化执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(穿装参数面迁移形态;被测单一源 = cw_wear_equip_action):
- 守卫断言三形(row 非法 / back_slot_count 域外 / slot 越界)= AssertionError
  响亮暴露零拖拽(禁兜底坐标);
- 拖点静态解析:实机形态 drag 起点 = 显式 src_cx/src_cy,终点 =
  screen_info 真档案 rect 中心 x + y1+21(D-36 校准权威派生式,期望值
  从同源 yml 现算非手抄);后排 slot > 6 新行为 = 按档位 area 表解析
  (旧守卫表长只匹配基线 6 的潜在 bug 已消灭);
- round detail 组装形态:记账拒单帧 detail 带「记账拒单:<码>(拖拽已
  发生,账未落)」段,正常记账帧与 gs 缺席帧不带;
- sim 形态(port 关闭)机械零调用,自上报照走。
"""

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionWearEquipParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action import (
    CwActionWearEquipOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _WearTestController(FixtureController):
    """补穿装 op 触达面的记录 stub:mouse_move 记录 + drag_to 双端记录。"""

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


def _expected_drag_point(ctx, area_name: str) -> tuple[int, int]:
    """期望拖点从同源 screen_info 档案现算(rect 中心 x + y1+21)。"""
    area = ctx.screen_loader.get_area(_PREP_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {_PREP_SCREEN}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, rect.y1 + 21)


@pytest.fixture
def wear_ctx(test_context, monkeypatch):
    """共享 ctx 的穿装测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx);默认剧本 = 干净备战帧——浮层守卫
    在 last_screenshot 缺席时走 op.screenshot(),无剧本帧会 IndexError。"""
    controller = _WearTestController(test_context)
    controller.set_phases([{'frame': (_PREP_SCREEN, 'deployed_2star')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(wear_ctx, param: CwActionWearEquipParam,
             ) -> tuple[CwActionWearEquipOp, _WearTestController]:
    controller = wear_ctx.controller
    assert isinstance(controller, _WearTestController)
    return CwActionWearEquipOp(wear_ctx, param), controller


def _attach_match_gs(wear_ctx, monkeypatch, xy: dict | None) -> GameState:
    """挂假局(懒建 gs)并种子伴随域/名单/上阵视图,供自上报反查走通
    (与观察链同写入口 gs.observe;cw_match 经 monkeypatch 还原。
    session 用 SimpleNamespace = 可弱引用可挂属性,game_state_of 惰建
    单例跨调用稳定)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(wear_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    gs.observe(gs.equips, ['量产型装甲'], sig=_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[None,
                                         Unit(char_id='银狼', star=2,
                                              equips=[]),
                                         None, None],
                            back_slots=[None] * 6),
               sig=_OBS)
    return gs


def test_guard_assertions(wear_ctx) -> None:
    """守卫断言三形:row 非法 / back_slot_count 域外 / slot 越界。"""
    cases = [
        CwActionWearEquipParam(src_cx=1, src_cy=2, row='middle', slot=1),
        CwActionWearEquipParam(src_cx=1, src_cy=2, row='back', slot=1,
                               back_slot_count=5),
        CwActionWearEquipParam(src_cx=1, src_cy=2, row='front', slot=9),
    ]
    for param in cases:
        op, controller = _make_op(wear_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_drags == []


def test_live_drag_start_and_end(wear_ctx) -> None:
    """实机形态:拖拽起点 = 显式坐标,终点 = 前排-N 档案派生拖点。"""
    param = CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                   slot=2, item_name='量产型装甲',
                                   char_name='银狼')
    op, controller = _make_op(wear_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected = _expected_drag_point(wear_ctx, '前排-2')
    assert controller.recorded_mouse_moves == [(1740, 210)]
    assert controller.recorded_drags == [((1740, 210), expected)]
    assert result.is_success
    # gs 缺席(无局)= 无 outcome,detail 不带拒单段(锁 detail 组装形态)
    assert '记账拒单' not in (result.status or '')


def test_back_slot_beyond_six_resolves_archive(wear_ctx) -> None:
    """后排 slot > 6 新行为:7 槽档 area 表解析(行为修复锁测)。"""
    param = CwActionWearEquipParam(src_cx=100, src_cy=200, row='back',
                                   slot=7, back_slot_count=7,
                                   item_name='量产型装甲', char_name='刃')
    op, controller = _make_op(wear_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected = _expected_drag_point(wear_ctx, '后排7槽-7')
    assert controller.recorded_drags == [((100, 200), expected)]
    assert result.is_success


def test_round_detail_carries_reject_code(wear_ctx, monkeypatch) -> None:
    """拒单帧 round detail:坐标不在伴随域 → success + 拒单码段。"""
    param = CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                   slot=2, item_name='量产型装甲',
                                   char_name='银狼')
    gs = _attach_match_gs(wear_ctx, monkeypatch,
                          xy={'量产型装甲': [(1, 1)]})
    op, controller = _make_op(wear_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:wear_item_xy_unresolved' in (result.status or '')
    assert '拖拽已发生,账未落' in (result.status or '')
    assert len(controller.recorded_drags) == 1   # 拖拽照发(机械成功语义不变)
    assert gs.equips.value == ['量产型装甲']   # 拒单零写


def test_round_detail_clean_on_accounted_frame(wear_ctx, monkeypatch) -> None:
    """正常记账帧 detail 不含拒单段(锁 detail 组装形态)。"""
    param = CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                   slot=2, item_name='量产型装甲',
                                   char_name='银狼')
    gs = _attach_match_gs(wear_ctx, monkeypatch,
                          xy={'量产型装甲': [(1740, 210)]})
    op, _ = _make_op(wear_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert gs.equips.value == []   # 记账落账(owned 摘件)


def test_sim_shape_mechanical_silent_report_walks(wear_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用,自上报照走(占位反查记账)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    param = CwActionWearEquipParam(src_cx=-1001, src_cy=-1000, row='front',
                                   slot=2, item_name='量产型装甲',
                                   char_name='银狼')
    gs = _attach_match_gs(wear_ctx, monkeypatch,
                          xy={'量产型装甲': [(-1001, -1000)]})
    op, controller = _make_op(wear_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_drags == []
    assert controller.recorded_mouse_moves == []
    assert gs.equips.value == []   # 反查命中占位,记账照走

