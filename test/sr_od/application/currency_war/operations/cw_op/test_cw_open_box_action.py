"""CwActionOpenBoxOp 参数面迁移执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(开简易武装箱参数面迁移形态;被测单一源 = cw_open_box_action):
- slot 必填守卫(审计 bug 修复锁,开件族第三例收官):slot=None →
  AssertionError(文案含「必填」与 kind='supply_box' 双口径指引关键词)
  且零点击——迁移前该形态走 op 内 gs 现算分支(机械路径消费 game state
  + 双出口 AssertionError),迁移后响亮拒绝;
- 越界守卫:slot=0 / 负值 / 越界(≥10)→ AssertionError 零点击(负下标
  回环防锁,下界显式闭合);
- 机械面全自持:点击 = 武装箱开启位-N 建档直查同名 area 中心(裸中心
  同源锁测,期望值从同源 yml 现算非手抄——派生域与 tome/bookcard 不同:
  点击目标是「武装箱开启位-N」开启按钮区,非「备战栏-N」槽位本体);
  mouse_move 先于 click(防吞点击口径顺序锁测);
- 零写锁测(替代 tome/bookcard 的腾位写断言):正常帧 round_success 且
  gs bench 槽位表零变化(零写族反向锁)+ box_card 登记在场(overlay
  登记锁测)+ round data 携 WorldDecl(next_screen = 底层屏推导值、
  trigger='open_box'——有声明形态锁测)+ detail 无拒单段(零写族恒
  applied=True);
- gs 缺席帧(无局种子)机械已发零上报零异常(data=None,无处记账跳过);
- sim 形态(port 关闭)机械零调用,自上报照走(登记与声明照写);
  env=None 全链跑通。
"""

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_op.cw_open_box_action import (
    CwActionOpenBoxOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _OpenBoxTestController(FixtureController):
    """补开简易武装箱 op 触达面的记录 stub:mouse_move 记录 +
    mouse_move/click 相对顺序记录(防吞点击口径顺序锁测用)。"""

    def __init__(self, ctx) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_events: list[tuple[str, tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        pt = (int(pos.x), int(pos.y))
        self.recorded_mouse_moves.append(pt)
        self.recorded_events.append(('mouse_move', pt))

    def click(self, pos=None, press_time: float = 0, pc_alt: bool = False,
              gamepad_key: str | None = None) -> bool:
        if pos is not None:
            self.recorded_events.append(('click', (int(pos.x), int(pos.y))))
        return FixtureController.click(self, pos, press_time=press_time,
                                       pc_alt=pc_alt,
                                       gamepad_key=gamepad_key)


def _expected_center(ctx, area_name: str) -> tuple[int, int]:
    """期望点击点从同源 screen_info 档案现算(rect 中心;裸中心同源派生
    非手抄)。派生域 = 武装箱开启位-N area 族(开启按钮区)。"""
    area = ctx.screen_loader.get_area(_PREP_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {_PREP_SCREEN}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


@pytest.fixture
def open_box_ctx(test_context, monkeypatch):
    """共享 ctx 的开简易武装箱测试夹具:controller 换装记录型 stub
    (monkeypatch 自动还原,防污染 session 级共享 ctx)。"""
    controller = _OpenBoxTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(open_box_ctx, param: CwActionOpenBoxParam,
             ) -> tuple[CwActionOpenBoxOp, _OpenBoxTestController]:
    """构造 op(env 缺省 None = 缺省备战档形态,全链跑通锁测形态)。"""
    controller = open_box_ctx.controller
    assert isinstance(controller, _OpenBoxTestController)
    return CwActionOpenBoxOp(open_box_ctx, param), controller


def _attach_match_gs(open_box_ctx, monkeypatch,
                     bench_slots: list | None = None):
    """挂假局(懒建 gs)并种子 bench 视图,供自上报走通(与观察链同写入口
    gs.observe;cw_match 经 monkeypatch 还原。session 用 SimpleNamespace =
    可弱引用可挂属性,game_state_of 惰建单例跨调用稳定)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(open_box_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.bench,
               BenchView(slots=bench_slots if bench_slots is not None
                         else [BenchSlot()] * 9),
               sig=_OBS)
    return gs


def test_none_slot_guard_rejects(open_box_ctx) -> None:
    """slot 必填守卫(审计 bug 修复锁,第三例收官):slot=None →
    AssertionError(文案含「必填」与 kind='supply_box' 双口径指引关键词)
    且零点击——迁移前该形态走 op 内 gs 现算分支,迁移后响亮拒绝(报错点
    前移至参数面)。"""
    op, controller = _make_op(open_box_ctx,
                              CwActionOpenBoxParam(slot=None))
    with pytest.raises(AssertionError) as exc_info, fast_sleep(op):
        op.run()
    assert '必填' in str(exc_info.value)
    assert 'supply_box' in str(exc_info.value)      # 口径①指引关键词
    assert 'armory_boxes' in str(exc_info.value)    # 口径②指引关键词
    assert controller.recorded_events == []
    assert controller.recorded_clicks == []


def test_guard_assertions(open_box_ctx) -> None:
    """越界守卫:slot=0 / 负值 / 越界(≥10)→ AssertionError 且零点击
    (负下标回环防锁测——下界 1 显式闭合;备战栏建档 9 槽,10/99 越上界)。"""
    cases = [
        CwActionOpenBoxParam(slot=0),
        CwActionOpenBoxParam(slot=-1),
        CwActionOpenBoxParam(slot=-9),
        CwActionOpenBoxParam(slot=10),
        CwActionOpenBoxParam(slot=99),
    ]
    for param in cases:
        op, controller = _make_op(open_box_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_events == []
        assert controller.recorded_clicks == []


def test_click_uses_armory_button_center_and_order(open_box_ctx,
                                                   monkeypatch) -> None:
    """实机形态(env=None 全链):mouse_move 先于 click 且两点 = 武装箱
    开启位-N 建档直查同名 area 中心(裸中心同源锁测;期望值派生源 = 武装
    箱开启位 area,非备战栏-N——本件与 tome/bookcard 同源锁测的派生域
    差异锚);零写锁测四合一:bench 槽位表零变化 + box_card 登记在场 +
    round data 携 WorldDecl(trigger='open_box',next_screen = 底层屏推导
    值)+ detail 无拒单段。"""
    gs = _attach_match_gs(
        open_box_ctx, monkeypatch,
        [BenchSlot()] * 4 + [BenchSlot(kind='supply_box')] + [BenchSlot()] * 4)
    op, controller = _make_op(open_box_ctx, CwActionOpenBoxParam(slot=5))
    with fast_sleep(op):
        result = op.run()
    expected = _expected_center(open_box_ctx, '武装箱开启位-5')
    assert controller.recorded_events == [('mouse_move', expected),
                                          ('click', expected)]
    assert result.is_success
    # 零写锁测:supply_box 槽零变化(零写族反向锁——腾位归下一入口
    # heavy 实读,不在动作时点写 bench 槽位表)
    assert gs.bench.value.slots[4].kind == 'supply_box'
    # overlay 登记锁测:武装箱四选一选卡画面在场(开件直登族)
    assert [p.kind for p in gs.screen_changes.pending] == ['box_card']
    # detail 无拒单段锁测(零写族恒 applied=True,无拒单出口)
    assert '记账拒单' not in (result.status or '')
    assert '发出即上报' in (result.status or '')
    # 有声明形态锁测:round data 携 WorldDecl(无局种子 → 节点屏回退
    # 备战档 = 底层屏;trigger 挂 backend 开箱采样分派)
    assert isinstance(result.data, WorldDecl)
    assert result.data.next_screen == _PREP_SCREEN
    assert result.data.trigger == 'open_box'


def test_gs_absent_frame_mechanical_fires_silently(open_box_ctx) -> None:
    """gs 缺席帧(无局):机械已发 + 零上报零声明零异常(无处记账跳过
    形态锁测)——round data 无声明载体。"""
    op, controller = _make_op(open_box_ctx, CwActionOpenBoxParam(slot=3))
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert len(controller.recorded_clicks) == 1
    assert result.data is None   # gs 缺席 = 无声明载体


def test_sim_shape_mechanical_silent_report_walks(open_box_ctx,
                                                  monkeypatch) -> None:
    """sim 形态:port 关闭 → 机械零调用(mouse_move/click 零执行,点击 +
    动画等待同 gate 静默跳过),自上报照走(两执行面同源;登记与声明照写)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    gs = _attach_match_gs(
        open_box_ctx, monkeypatch,
        [BenchSlot(kind='supply_box')] + [BenchSlot()] * 8)
    op, controller = _make_op(open_box_ctx, CwActionOpenBoxParam(slot=1))
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_mouse_moves == []
    assert controller.recorded_clicks == []
    assert controller.recorded_events == []
    assert gs.bench.value.slots[0].kind == 'supply_box'   # 零写族照零
    assert [p.kind for p in gs.screen_changes.pending] == ['box_card']
    assert isinstance(result.data, WorldDecl)
    assert result.data.trigger == 'open_box'
