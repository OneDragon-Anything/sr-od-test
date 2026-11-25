"""CwActionSellBenchOp 参数面迁移执行体测试(harness 剧本 + 真建档派生)。

锁的设计约定(卖备战席参数面迁移形态;被测单一源 = cw_prep_sell_bench_action):
- 守卫断言双域统一:bench_idx 负值/越界 → AssertionError 响亮暴露零拖拽
  (商店域不再 getattr 容缺跳守卫——迁移前该形态静默拖拽);非法画面档
  空点表 = 建档漂移哨同断言(文案带画面档定位);
- 双域形态:拖点 = row_area_centers 裸中心(角色拖动族权威派生式,期望值
  从同源 yml 现算非手抄)+ 区域-出售区单一源落点;备战域(env=None)解析
  备战画面档,商店域(env 带 ShopActionExecutor)解析商店开画面档(两档
  同名 area 坐标逐位同的实证锁测——档案漂移分叉时此测先红);
- round detail 组装形态:记账拒单帧 detail 带「记账拒单:<reason>(拖拽已
  发生,账未落)」段,正常记账帧与 gs 缺席帧不带;
- ledger:商店域 env 卖出帧 total_sell+1,备战域/env=None 无 ledger 零
  异常跳过;
- sim 形态(port 关闭)机械零调用,自上报照走。
"""

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSellBenchParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_sell_bench_action import (
    CwActionSellBenchOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopActionExecutor,
    ShopExecEnv,
    ShopVisitLedger,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_PREP_SCREEN = '货币战争-备战'
_SHOP_SCREEN = '货币战争-备战-开商店'
_OBS = ChannelSig(family='obs', actor='test')


class _SellTestController(FixtureController):
    """补卖备战席 op 触达面的记录 stub:mouse_move 记录 + drag_to 双端记录。"""

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


def _expected_center(ctx, area_name: str,
                     screen_name: str = _PREP_SCREEN) -> tuple[int, int]:
    """期望拖点从同源 screen_info 档案现算(rect 中心;角色拖动族裸中心
    权威派生式,非 +21)。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {screen_name}/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


@pytest.fixture
def sell_ctx(test_context, monkeypatch):
    """共享 ctx 的卖备战席测试夹具:controller 换装记录型 stub(monkeypatch
    自动还原,防污染 session 级共享 ctx);默认剧本 = 干净备战帧(个别
    用例要读屏时用;拖拽本身不读屏)。"""
    controller = _SellTestController(test_context)
    controller.set_phases([{'frame': ('货币战争-备战', 'deployed_2star')}])
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _make_op(sell_ctx, param: CwActionSellBenchParam,
             env=None) -> tuple[CwActionSellBenchOp, _SellTestController]:
    controller = sell_ctx.controller
    assert isinstance(controller, _SellTestController)
    # env 缺省(None)= 缺省备战档形态锁测。
    return CwActionSellBenchOp(sell_ctx, param, env=env), controller


def _shop_env(sell_ctx, gs) -> ShopExecEnv:
    """商店域执行环境(真 ShopExecEnv/ShopActionExecutor/ShopVisitLedger;
    op 只消费 executor.screen_name 与 ledger 两元数据,其余字段填中性值)。"""
    return ShopExecEnv(
        op=types.SimpleNamespace(), match=types.SimpleNamespace(),
        config=None, click_pts=[], level_btn=Point(0, 0),
        refresh_btn=Point(0, 0), ledger=ShopVisitLedger(),
        state=gs,
        executor=ShopActionExecutor(types.SimpleNamespace(), sell_ctx))


def _unit(char_id: str, star: int = 2) -> Unit:
    return Unit(char_id=char_id, star=star, equips=[])


def _attach_match_gs(sell_ctx, monkeypatch,
                     bench_slots: list | None = None):
    """挂假局(懒建 gs)并种子 bench 视图,供自上报走通(与观察链同写入口
    gs.observe;cw_match 经 monkeypatch 还原。session 用 SimpleNamespace =
    可弱引用可挂属性,game_state_of 惰建单例跨调用稳定;bench 全空槽种子
    = 上报空槽拒单形态)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(sell_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.bench,
               BenchView(slots=bench_slots if bench_slots is not None
                         else [BenchSlot()] * 9),
               sig=_OBS)
    return gs


def test_guard_assertions(sell_ctx) -> None:
    """守卫断言:bench_idx 负值 / 越界(≥9)→ AssertionError 且零拖拽
    (负下标回环防锁测——下界显式闭合)。"""
    cases = [
        CwActionSellBenchParam(bench_idx=-1),
        CwActionSellBenchParam(bench_idx=9),
        CwActionSellBenchParam(bench_idx=99),
    ]
    for param in cases:
        op, controller = _make_op(sell_ctx, param)
        with pytest.raises(AssertionError), fast_sleep(op):
            op.run()
        assert controller.recorded_drags == []
        assert controller.recorded_mouse_moves == []


def test_guard_empty_pts_archive_drift_sentinel(sell_ctx, monkeypatch) -> None:
    """空点表 = 建档漂移哨:画面档在但 备战栏-N area 缺失(row_area_centers
    返回空列)→ 同一断言响亮暴露,文案带画面档定位。"""
    fake_si = types.SimpleNamespace(area_list=[])
    monkeypatch.setattr(sell_ctx.screen_loader, 'get_screen',
                        lambda name: fake_si)
    param = CwActionSellBenchParam(bench_idx=0)
    op, controller = _make_op(sell_ctx, param)
    with pytest.raises(AssertionError) as exc_info, fast_sleep(op):
        op.run()
    assert '画面档=货币战争-备战' in str(exc_info.value)
    assert controller.recorded_drags == []


def test_shop_domain_guard_unified(sell_ctx) -> None:
    """守卫双域统一锁测:商店域 env 下 bench_idx 越界 → AssertionError
    (getattr 容缺退役锁测——迁移前该形态静默拖拽,迁移后必须炸),文案
    带商店画面档定位(域分派生效证据)。"""
    param = CwActionSellBenchParam(bench_idx=9)
    env = _shop_env(sell_ctx, types.SimpleNamespace())
    op, controller = _make_op(sell_ctx, param, env=env)
    with pytest.raises(AssertionError) as exc_info, fast_sleep(op):
        op.run()
    assert controller.recorded_drags == []
    assert '画面档=货币战争-备战-开商店' in str(exc_info.value)


def test_prep_domain_drag_uses_prep_archive(sell_ctx) -> None:
    """备战域形态(env=None):拖拽双端 = 备战画面档 备战栏-N 裸中心 →
    区域-出售区中心(单一源落点);gs 缺席(无局)= 无 outcome,detail
    不带拒单段。"""
    param = CwActionSellBenchParam(bench_idx=0, reason='m4_fuel_sell')
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '备战栏-1')
    expected_end = _expected_center(sell_ctx, '区域-出售区')
    assert controller.recorded_mouse_moves[0] == expected_start
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success
    assert '记账拒单' not in (result.status or '')


def test_shop_domain_drag_uses_shop_archive(sell_ctx) -> None:
    """商店域形态(env 带 ShopActionExecutor):拖拽双端 = 商店画面档
    同名 area 中心(两档坐标逐位同的实证锁测——档案漂移分叉时此测先红
    = 域分派防线价值证明);访问账卖出计数落账。"""
    param = CwActionSellBenchParam(bench_idx=4, reason='shop_swap')
    env = _shop_env(sell_ctx, types.SimpleNamespace())
    op, controller = _make_op(sell_ctx, param, env=env)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '备战栏-5', _SHOP_SCREEN)
    expected_end = _expected_center(sell_ctx, '区域-出售区', _SHOP_SCREEN)
    assert controller.recorded_mouse_moves[0] == expected_start
    assert controller.recorded_drags == [(expected_start, expected_end)]
    assert result.is_success
    assert env.ledger.total_sell == 1


def test_prep_domain_env_without_ledger_skips(sell_ctx) -> None:
    """备战域 env(有 executor 无 ledger 字段与 screen_name 属性)→
    ledger 消费零异常跳过 + screen_name 缺省回落备战画面档(拖拽起点 =
    备战档 area 中心即证据)。"""
    param = CwActionSellBenchParam(bench_idx=1)
    env = types.SimpleNamespace(executor=types.SimpleNamespace())
    assert getattr(env, 'ledger', None) is None   # 备战域形态前提
    op, controller = _make_op(sell_ctx, param, env=env)
    with fast_sleep(op):
        result = op.run()
    expected_start = _expected_center(sell_ctx, '备战栏-2')
    assert controller.recorded_drags == [
        (expected_start, _expected_center(sell_ctx, '区域-出售区'))]
    assert result.is_success


def test_round_detail_carries_reject_code(sell_ctx, monkeypatch) -> None:
    """拒单帧 round detail:目标槽空 → success + bench_idx_out_of_range
    拒单码段(机械成功语义不变,拖拽照发;禁补拖口径)。"""
    param = CwActionSellBenchParam(bench_idx=0)
    gs = _attach_match_gs(sell_ctx, monkeypatch)   # bench 全空槽
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:bench_idx_out_of_range:0' in (result.status or '')
    assert '拖拽已发生,账未落' in (result.status or '')
    assert len(controller.recorded_drags) == 1
    # 拒单零写:bench 原值保持(全空槽)
    assert gs.bench.value.slots[0].kind == 'empty'


def test_round_detail_stale_proposal(sell_ctx, monkeypatch) -> None:
    """陈旧提案拒单帧:expect 填名不符槽现任 → success + stale_proposal
    拒单段(代际防线消费,零写)。"""
    param = CwActionSellBenchParam(bench_idx=0, expect='刃')
    gs = _attach_match_gs(
        sell_ctx, monkeypatch,
        [BenchSlot(kind='unit', unit=_unit('银狼'))] + [BenchSlot()] * 8)
    op, _ = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单:stale_proposal:刃!=银狼' in (result.status or '')
    assert gs.bench.value.slots[0].kind == 'unit'   # 拒单零写
    assert gs.bench.value.slots[0].unit.char_id == '银狼'


def test_round_detail_clean_on_accounted_frame(sell_ctx, monkeypatch) -> None:
    """正常记账帧 detail 不含拒单段;摘槽上报落账(bench 置 empty 不移位
    ——槽位反查记账形态)。"""
    param = CwActionSellBenchParam(bench_idx=3)
    gs = _attach_match_gs(
        sell_ctx, monkeypatch,
        [BenchSlot()] * 3 + [BenchSlot(kind='unit', unit=_unit('银狼'))]
        + [BenchSlot()] * 5)
    op, _ = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert '记账拒单' not in (result.status or '')
    assert gs.bench.value.slots[3].kind == 'empty'


def test_sim_shape_mechanical_silent_report_walks(sell_ctx, monkeypatch
                                                  ) -> None:
    """sim 形态:port 关闭 → 机械零调用(拖拽与机械后等待零执行),自上报
    照走(两执行面同源)。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed',
                        lambda: False)
    param = CwActionSellBenchParam(bench_idx=0)
    gs = _attach_match_gs(
        sell_ctx, monkeypatch,
        [BenchSlot(kind='unit', unit=_unit('刃'))] + [BenchSlot()] * 8)
    op, controller = _make_op(sell_ctx, param)
    with fast_sleep(op):
        result = op.run()
    assert result.is_success
    assert controller.recorded_drags == []
    assert controller.recorded_mouse_moves == []
    assert gs.bench.value.slots[0].kind == 'empty'
