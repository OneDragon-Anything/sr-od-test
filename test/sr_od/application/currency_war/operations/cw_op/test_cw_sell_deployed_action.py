"""CwActionSellDeployedOp 参数面迁移执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(卖上阵参数面迁移形态;被测单一源 = cw_sell_deployed_action):
- 守卫断言(deployed_idx 负值 / 越界 / 后排槽 back_slot_count 域外)
  = AssertionError 响亮暴露零拖拽(禁兜底坐标);前排槽 back_slot_count
  域外不拦(域不涉则忽略,MoveUnit 同式锁测);
- 拖点静态解析:实机形态拖拽双端 = row_area_centers 裸中心(角色拖动族
  权威派生式,期望值从同源 yml 现算非手抄)+ 区域-出售区单一源落点;
  后排扩格槽按 back_slot_count 档位表解析(back_slot_count=7 → 后排7槽
  档,旧点表只匹配基线 6 的必拒形态已消灭);
- round detail 组装形态:记账拒单帧 detail 带「记账拒单:<reason>(拖拽已
  发生,账未落)」段,正常记账帧与 gs 缺席帧不带;
- sim 形态(port 关闭)机械零调用,自上报照走。
"""

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    DeployedView,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSellDeployedParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_sell_deployed_action import (
    CwActionSellDeployedOp,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')


class _SellTestController(FixtureController):
    """补卖上阵 op 触达面的记录 stub:mouse_move 记录 + drag_to 双端记录。"""

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
def sell_ctx(test_context, monkeypatch):
    """共享 ctx 的卖上阵测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx);默认剧本 = 干净备战帧(个别
    用例要读屏时用;拖拽本身不读屏)。"""
    controller = _SellTestController(test_context)
    controller.set_phases([{'frame': ('货币战争-备战', 'deployed_2star')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(sell_ctx, param: CwActionSellDeployedParam,
             ) -> tuple[CwActionSellDeployedOp, _SellTestController]:
    controller = sell_ctx.controller
    assert isinstance(controller, _SellTestController)
    # env 缺省(None)全链 = 机械半自持零 env 消费形态锁测。
    return CwActionSellDeployedOp(sell_ctx, param), controller


def _unit(char_id: str, star: int = 2) -> Unit:
    return Unit(char_id=char_id, star=star, equips=[])


def _attach_match_gs(sell_ctx, monkeypatch,
                     front_slots: list | None = None):
    """挂假局(懒建 gs)并种子 deployed 视图,供自上报走通(与观察链
    同写入口 gs.observe;cw_match 经 monkeypatch 还原。session 用
    SimpleNamespace = 可弱引用可挂属性,game_state_of 惰建单例跨调用
    稳定;deployed 全 None 种子 = 上报空槽拒单形态)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(sell_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.deployed,
               DeployedView(front_slots=front_slots
                            if front_slots is not None else [None] * 4,
                            back_slots=[None] * 6),
               sig=_OBS)
    return gs


def test_guard_assertions(sell_ctx) -> None:
    """守卫断言:deployed_idx 负值 / 越界(≥ 前排容量+back_slot_count)/
    后排槽 back_slot_count 域外 → AssertionError 且零拖拽。"""
    cases = [
        CwActionSellDeployedParam(deployed_idx=-1),
        CwActionSellDeployedParam(deployed_idx=10),   # 缺省档 4+6 上界外
        CwActionSellDeployedParam(deployed_idx=4, back_slot_count=5),
        CwActionSellDeployedParam(deployed_idx=11, back_slot_count=7),
        CwActionSellDeployedParam(deployed_idx=99, back_slot_count=9),
    ]
    for param in cases:
        op, controller = _make_op(sell_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_drags == []


def test_front_slot_ignores_back_slot_count_domain(sell_ctx) -> None:
    """前排域 back_slot_count 域外不拦(域不涉则忽略,MoveUnit 同式):
    deployed_idx=1 + 档域外值 → 正常拖前排-2 → 出售区。"""
    param = CwActionSellDeployedParam(deployed_idx=1, back_slot_count=99)
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '前排-2')
    expected_end = _expected_center(sell_ctx, '区域-出售区')
    assert controller.recorded_mouse_moves[0] == expected_start
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success


def test_live_drag_front_slot_to_sell_point(sell_ctx) -> None:
    """实机形态:拖拽双端 = 前排 area 裸中心 → 区域-出售区中心(单一源
    落点);gs 缺席(无局)= 无 outcome,detail 不带拒单段。"""
    param = CwActionSellDeployedParam(deployed_idx=2, reason='evict_replaced')
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '前排-3')
    expected_end = _expected_center(sell_ctx, '区域-出售区')
    assert controller.recorded_mouse_moves[0] == expected_start
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success
    assert '记账拒单' not in (result.status or '')


def test_back_expanded_slot_resolves_archive(sell_ctx) -> None:
    """后排扩格槽新行为:back_slot_count=7 → 后排7槽档 area 表解析
    (deployed_idx=10 = 后排排内槽 7;行为修复锁测——旧点表只匹配基线
    6 槽形态下后排 slot 7 直卖必拒)。"""
    param = CwActionSellDeployedParam(deployed_idx=10, back_slot_count=7)
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '后排7槽-7')
    expected_end = _expected_center(sell_ctx, '区域-出售区')
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success


def test_round_detail_carries_reject_code(sell_ctx, monkeypatch) -> None:
    """拒单帧 round detail:目标槽空 → success + deployed_idx_out_of_range
    拒单码段(机械成功语义不变,拖拽照发;禁补拖口径)。"""
    param = CwActionSellDeployedParam(deployed_idx=1)
    gs = _attach_match_gs(sell_ctx, monkeypatch)   # deployed 全 None = 空槽
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:deployed_idx_out_of_range:1' in (result.status or '')
    assert '拖拽已发生,账未落' in (result.status or '')
    assert len(controller.recorded_drags) == 1
    # 拒单零写:deployed 原值保持
    assert gs.deployed.value.front_slots[1] is None


def test_round_detail_stale_proposal(sell_ctx, monkeypatch) -> None:
    """陈旧提案拒单帧:expect 填名不符槽现任 → success + stale_proposal
    拒单段(代际防线消费,零写)。"""
    param = CwActionSellDeployedParam(deployed_idx=0, expect='刃')
    gs = _attach_match_gs(sell_ctx, monkeypatch,
                          front_slots=[_unit('银狼'), None, None, None])
    op, _ = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:stale_proposal:刃!=银狼' in (result.status or '')
    assert gs.deployed.value.front_slots[0] is not None   # 拒单零写
    assert gs.deployed.value.front_slots[0].char_id == '银狼'


def test_round_detail_clean_on_accounted_frame(sell_ctx, monkeypatch) -> None:
    """正常记账帧 detail 不含拒单段;摘槽上报落账(deployed 置 None
    不移位——槽位反查记账形态)。"""
    param = CwActionSellDeployedParam(deployed_idx=3)
    gs = _attach_match_gs(sell_ctx, monkeypatch,
                          front_slots=[None, None, None, _unit('银狼')])
    op, _ = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert gs.deployed.value.front_slots[3] is None


def test_sim_shape_mechanical_silent_report_walks(sell_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用,自上报照走(两执行面同源)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    param = CwActionSellDeployedParam(deployed_idx=0)
    gs = _attach_match_gs(sell_ctx, monkeypatch,
                          front_slots=[_unit('刃'), None, None, None])
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_drags == []
    assert controller.recorded_mouse_moves == []
    assert gs.deployed.value.front_slots[0] is None
