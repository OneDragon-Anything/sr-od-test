"""CwActionOpenBookcardOp 参数面迁移执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(开书册卡参数面迁移形态;被测单一源 = cw_open_bookcard_action):
- slot 必填守卫(审计 bug 修复锁):slot=None → AssertionError(文案含
  「必填」与废除申报)且零点击——迁移前该形态走 op 内 gs 现算分支
  (机械路径消费 game state + 双出口 AssertionError),迁移后响亮拒绝;
- 越界守卫:slot=0 / 负值 / 越界(≥10)→ AssertionError 零点击(负下标
  回环防锁,下界显式闭合);
- 机械面全自持:点击 = 备战栏-N 建档直查同名 area 中心(裸中心同源锁测,
  期望值从同源 yml 现算非手抄);mouse_move 先于 click(防吞点击口径
  顺序锁测);
- 自上报:正常帧腾位记账(bookcard → empty)+ expert_invite 登记 +
  round data 携 WorldDecl;拒单帧 round detail 带「记账拒单:
  bookcard_slot_missing(点击已发生,账未落)」段零写;gs 缺席帧机械
  已发零上报零声明;
- sim 形态(port 关闭)机械零调用,自上报照走;env=None 全链跑通。
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
    CwActionOpenBookcardParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_op.cw_open_bookcard_action import (
    CwActionOpenBookcardOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _BookcardTestController(FixtureController):
    """补开书册卡 op 触达面的记录 stub:mouse_move 记录 + mouse_move/click
    相对顺序记录(防吞点击口径顺序锁测用)。"""

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
    非手抄)。"""
    area = ctx.screen_loader.get_area(_PREP_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {_PREP_SCREEN}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


@pytest.fixture
def bookcard_ctx(test_context, monkeypatch):
    """共享 ctx 的开书册卡测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx)。"""
    controller = _BookcardTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(bookcard_ctx, param: CwActionOpenBookcardParam,
             ) -> tuple[CwActionOpenBookcardOp, _BookcardTestController]:
    """构造 op(env 缺省 None = 缺省备战档形态,全链跑通锁测形态)。"""
    controller = bookcard_ctx.controller
    assert isinstance(controller, _BookcardTestController)
    return CwActionOpenBookcardOp(bookcard_ctx, param), controller


def _attach_match_gs(bookcard_ctx, monkeypatch,
                     bench_slots: list | None = None):
    """挂假局(懒建 gs)并种子 bench 视图,供自上报走通(与观察链同写入口
    gs.observe;cw_match 经 monkeypatch 还原。session 用 SimpleNamespace =
    可弱引用可挂属性,game_state_of 惰建单例跨调用稳定;bench 全空槽种子
    = 拒单形态)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(bookcard_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.bench,
               BenchView(slots=bench_slots if bench_slots is not None
                         else [BenchSlot()] * 9),
               sig=_OBS)
    return gs


def test_none_slot_guard_rejects(bookcard_ctx) -> None:
    """slot 必填守卫(审计 bug 修复锁):slot=None → AssertionError(文案
    含「必填」与废除申报)且零点击——迁移前该形态走 op 内 gs 现算分支,
    迁移后响亮拒绝(报错点前移至参数面)。"""
    op, controller = _make_op(bookcard_ctx,
                              CwActionOpenBookcardParam(slot=None))
    with pytest.raises(AssertionError) as exc_info, fast_sleep(op):
        op.run()
    assert '必填' in str(exc_info.value)
    assert '废除' in str(exc_info.value)
    assert controller.recorded_events == []
    assert controller.recorded_clicks == []


def test_guard_assertions(bookcard_ctx) -> None:
    """越界守卫:slot=0 / 负值 / 越界(≥10)→ AssertionError 且零点击
    (负下标回环防锁测——下界 1 显式闭合;备战栏建档 9 槽,10/99 越上界)。"""
    cases = [
        CwActionOpenBookcardParam(slot=0),
        CwActionOpenBookcardParam(slot=-1),
        CwActionOpenBookcardParam(slot=-9),
        CwActionOpenBookcardParam(slot=10),
        CwActionOpenBookcardParam(slot=99),
    ]
    for param in cases:
        op, controller = _make_op(bookcard_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_events == []
        assert controller.recorded_clicks == []


def test_click_uses_archive_center_and_order(bookcard_ctx, monkeypatch
                                             ) -> None:
    """实机形态(env=None 全链):mouse_move 先于 click 且两点 = 备战栏-N
    建档直查同名 area 中心(裸中心同源锁测);正常帧 detail 无拒单段 +
    腾位记账 + expert_invite 登记 + round data 携 WorldDecl(纯转移)。"""
    gs = _attach_match_gs(
        bookcard_ctx, monkeypatch,
        [BenchSlot()] * 4 + [BenchSlot(kind='bookcard')] + [BenchSlot()] * 4)
    op, controller = _make_op(bookcard_ctx, CwActionOpenBookcardParam(slot=5))
    with fast_sleep(op):
        result = op.run()
    expected = _expected_center(bookcard_ctx, '备战栏-5')
    assert controller.recorded_events == [('mouse_move', expected),
                                          ('click', expected)]
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert '发出即记账,落地归观察对账' in (result.status or '')
    # 腾位记账锁测:bookcard → empty(槽位表直址写,不移位)
    assert gs.bench.value.slots[4].kind == 'empty'
    # overlay 登记锁测:专家邀请函在场(开件直登族)
    assert [p.kind for p in gs.screen_changes.pending] == ['expert_invite']
    # 转移声明锁测:round data 携纯转移 WorldDecl(无局种子 → 节点屏回退备战档)
    assert isinstance(result.data, WorldDecl)
    assert result.data.next_screen == _PREP_SCREEN
    assert result.data.trigger == ''


def test_round_detail_carries_reject_code(bookcard_ctx, monkeypatch) -> None:
    """拒单帧 round detail:目标槽 kind='empty'(决策陈旧帧模拟)→
    success + bookcard_slot_missing 拒单码段(机械成功语义不变,点击已发;
    禁补点口径);拒单零写。"""
    param = CwActionOpenBookcardParam(slot=5)
    gs = _attach_match_gs(bookcard_ctx, monkeypatch)   # bench 全空槽
    op, controller = _make_op(bookcard_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:bookcard_slot_missing(点击已发生,账未落)' \
        in (result.status or '')
    assert len(controller.recorded_clicks) == 1   # 点击已发生口径
    assert gs.bench.value.slots[4].kind == 'empty'   # 拒单零写
    assert gs.screen_changes.pending == []   # 拒单帧零登记(登记与落地同点)


def test_gs_absent_frame_mechanical_fires_silently(bookcard_ctx) -> None:
    """gs 缺席帧(无局):机械已发 + 零上报零声明零异常(无处记账跳过
    形态锁测)——round data 无声明载体。"""
    op, controller = _make_op(bookcard_ctx, CwActionOpenBookcardParam(slot=3))
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert len(controller.recorded_clicks) == 1
    assert '记账拒单' not in (result.status or '')
    assert result.data is None   # gs 缺席 = 无声明载体


def test_sim_shape_mechanical_silent_report_walks(bookcard_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用(mouse_move/click 零执行,点击 +
    动画等待同 gate 静默跳过),自上报照走(两执行面同源)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    gs = _attach_match_gs(
        bookcard_ctx, monkeypatch,
        [BenchSlot(kind='bookcard')] + [BenchSlot()] * 8)
    op, controller = _make_op(bookcard_ctx, CwActionOpenBookcardParam(slot=1))
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_mouse_moves == []
    assert controller.recorded_clicks == []
    assert controller.recorded_events == []
    assert gs.bench.value.slots[0].kind == 'empty'   # 自上报照走
