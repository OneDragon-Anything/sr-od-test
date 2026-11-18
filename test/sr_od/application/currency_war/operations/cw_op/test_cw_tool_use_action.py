"""CwActionToolUseOp 坐标参数化执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(工具原子参数面迁移形态;被测单一源 = cw_tool_use_action):
- 守卫断言清单(target_kind 非法 / equip 缺目标坐标 / 源目标同格 / row
  非法 / back_slot_count 域外 / slot 越界)= AssertionError 响亮暴露
  零拖拽(禁兜底坐标);
- 拖点静态解析:equip 模式拖拽双端 = 显式坐标(tool_cx/tool_cy →
  tgt_cx/tgt_cy);char 模式终点 = screen_info 真档案 rect 中心 x +
  y1+21(D-36 校准权威派生式,期望值从同源 yml 现算非手抄);后排
  slot > 6 新行为 = 按档位 area 表解析(7/8/9 槽档,旧守卫表长只匹配
  基线 6 的潜在 bug 已消灭);
- env 缺省 None 全链(机械半自持,零 env 消费);
- round detail 组装形态:记账拒单帧 detail 带「记账拒单:<码>(拖拽已
  发生,账未落)」段,正常记账帧不带;
- sim 形态(port 关闭)机械零调用,自上报照走(占位坐标反查记账)。
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
    CwActionFurnaceUseParam,
    CwActionPrivilegeCardUseParam,
    CwActionWrenchUseParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_tool_use_action import (
    CwActionToolUseOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _ToolTestController(FixtureController):
    """补工具 op 触达面的记录 stub:mouse_move 记录 + drag_to 双端记录。"""

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
def tool_ctx(test_context, monkeypatch):
    """共享 ctx 的工具测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx)。"""
    controller = _ToolTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(tool_ctx, param) -> tuple[CwActionToolUseOp, _ToolTestController]:
    controller = tool_ctx.controller
    assert isinstance(controller, _ToolTestController)
    return CwActionToolUseOp(tool_ctx, param), controller   # env 缺省 None


def _attach_match_gs(tool_ctx, monkeypatch, xy: dict | None,
                     owned: list[str]) -> GameState:
    """挂假局(懒建 gs)并种子伴随域/名单/上阵视图,供自上报反查走通
    (与观察链同写入口 gs.observe;cw_match 经 monkeypatch 还原)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(tool_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    gs.observe(gs.equips, list(owned), sig=_OBS)
    gs.observe(gs.deployed,
               DeployedView(front_slots=[None,
                                         Unit(char_id='罗刹', star=2,
                                              equips=[]),
                                         None, None],
                            back_slots=[None] * 6),
               sig=_OBS)
    return gs


def test_guard_assertions(tool_ctx) -> None:
    """守卫断言清单:target_kind 非法 / equip 缺目标坐标 / 源目标同格 /
    row 非法 / slot 越界 / back_slot_count 域外 → AssertionError 零拖拽。"""
    cases = [
        CwActionFurnaceUseParam(target_kind='both', tool_cx=1, tool_cy=2,
                                tgt_cx=3, tgt_cy=4),
        CwActionFurnaceUseParam(target_kind='equip', tool_cx=1, tool_cy=2,
                                tgt_cx=0, tgt_cy=0),
        CwActionFurnaceUseParam(target_kind='equip', tool_cx=5, tool_cy=6,
                                tgt_cx=5, tgt_cy=6),
        CwActionWrenchUseParam(tool_cx=1, tool_cy=2, row='middle', slot=1),
        CwActionWrenchUseParam(tool_cx=1, tool_cy=2, row='front', slot=9),
        CwActionWrenchUseParam(tool_cx=1, tool_cy=2, row='back', slot=1,
                               back_slot_count=5),
    ]
    for param in cases:
        op, controller = _make_op(tool_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_drags == []


def test_live_equip_drag_uses_explicit_coords(tool_ctx) -> None:
    """实机形态(equip 模式):拖拽双端 = 显式坐标,env=None 全链,
    gs 缺席(无局)= 无拒单段。"""
    param = CwActionFurnaceUseParam(
        target_kind='equip', tool_cx=1660, tool_cy=120,
        tgt_cx=1740, tgt_cy=210, item_name='量产型装甲')
    op, controller = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert controller.recorded_mouse_moves == [(1660, 120)]
    assert controller.recorded_drags == [((1660, 120), (1740, 210))]
    assert result.is_success
    assert '记账拒单' not in (result.status or '')


def test_live_char_drag_resolves_archive_point(tool_ctx) -> None:
    """实机形态(char 模式):终点 = 前排-N 档案派生拖点(中心 x + y1+21)。"""
    param = CwActionWrenchUseParam(tool_cx=1620, tool_cy=120, row='front',
                                   slot=2, back_slot_count=6,
                                   char_name='罗刹')
    op, controller = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected = _expected_drag_point(tool_ctx, '前排-2')
    assert controller.recorded_mouse_moves == [(1620, 120)]
    assert controller.recorded_drags == [((1620, 120), expected)]
    assert result.is_success


@pytest.mark.parametrize('back_slot_count,slot,area_name', [
    (7, 7, '后排7槽-7'),
    (8, 8, '后排8槽-8'),
    (9, 9, '后排9槽-9'),
])
def test_back_slot_beyond_six_resolves_archive(
        tool_ctx, back_slot_count: int, slot: int, area_name: str) -> None:
    """后排 slot > 6 新行为:7/8/9 槽档 area 表解析(行为修复锁测)。"""
    param = CwActionWrenchUseParam(tool_cx=1620, tool_cy=120, row='back',
                                   slot=slot, back_slot_count=back_slot_count)
    op, controller = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected = _expected_drag_point(tool_ctx, area_name)
    assert controller.recorded_drags == [((1620, 120), expected)]
    assert result.is_success


def test_round_detail_carries_reject_code(tool_ctx, monkeypatch) -> None:
    """拒单帧 round detail:源坐标不在伴随域 → success + 拒单码段
    (特权卡双键反查拒单)。"""
    param = CwActionPrivilegeCardUseParam(
        target_kind='equip', tool_cx=1660, tool_cy=120,
        tgt_cx=1740, tgt_cy=210, item_name='武器大师')
    gs = _attach_match_gs(tool_ctx, monkeypatch,
                          xy={'特权赋予卡': [(1, 1)],
                              '武器大师': [(1740, 210)]},
                          owned=['特权赋予卡', '武器大师'])
    op, controller = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:tool_xy_unresolved' in (result.status or '')
    assert '拖拽已发生,账未落' in (result.status or '')
    assert len(controller.recorded_drags) == 1   # 拖拽照发(机械成功语义不变)
    assert gs.equips.value == ['特权赋予卡', '武器大师']   # 拒单零写


def test_round_detail_clean_on_accounted_frame(tool_ctx, monkeypatch) -> None:
    """正常记账帧 detail 不含拒单段(锁 detail 组装形态)。"""
    param = CwActionPrivilegeCardUseParam(
        target_kind='equip', tool_cx=1660, tool_cy=120,
        tgt_cx=1740, tgt_cy=210, item_name='武器大师')
    gs = _attach_match_gs(tool_ctx, monkeypatch,
                          xy={'特权赋予卡': [(1660, 120)],
                              '武器大师': [(1740, 210)]},
                          owned=['特权赋予卡', '武器大师'])
    op, _ = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert gs.equips.value == ['武器大师·特权']   # 反查记账落账(变换同笔)


def test_sim_shape_mechanical_silent_report_walks(tool_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用,自上报照走(占位反查记账)。
    占位 = 界外哨兵坐标(模拟 sim 占位同步形态),反查命中记账照落。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    param = CwActionPrivilegeCardUseParam(
        target_kind='equip', tool_cx=-1001, tool_cy=-1000,
        tgt_cx=-1002, tgt_cy=-1000, item_name='武器大师')
    gs = _attach_match_gs(tool_ctx, monkeypatch,
                          xy={'特权赋予卡': [(-1001, -1000)],
                              '武器大师': [(-1002, -1000)]},
                          owned=['特权赋予卡', '武器大师'])
    op, controller = _make_op(tool_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_drags == []
    assert controller.recorded_mouse_moves == []
    assert gs.equips.value == ['武器大师·特权']   # 反查命中占位,记账照走
