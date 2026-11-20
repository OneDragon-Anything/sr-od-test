"""出战发出链回归集(prep_actions;harness 剧本直调发出链函数)。

锁设计约定(armed/resume 两调用面;判据、顺序、计数、face 语义为发出链
冻结面,design §2.8 第 3 条四路径):

- 屏态复验 stale 放弃:执行时刻 fresh 帧备战两识别标志 miss →
  ``(False, 'readiness_stale_screen')`` 零发出 + cw4_counters 分键计数
  (切屏瞬间非备战屏上的拖空事故防线);
- 浮层闸门 hold:身份分发名单命中非备战屏 → ``(False,
  'readiness_overlay_hold:<屏名>')`` 零发出 + 分键计数(投资策略浮层盖
  备战、识别标志穿透命中的事故防线);
- armed 面发出序:部署原子序(策略层部署计划现算)依序发出、先于出战
  点击,出战点击收尾返回 (True, detail);
- resume 面发出即写证据位:首调执行同步步部署原子序并置 Match 宿主的
  ``locked_sync_done``;二调跳过同步步(部署计划零再执行)、
  出战点击仍发。

驱动形态:发出链函数直调(不经 op 节点循环),宿主 op 只承载识别原语;
动作 op 的模块级裸 ``time.sleep`` 经替身桩掉(harness ``fast_sleep`` 只
覆盖宿主 MRO 内模块,不在其内的动作 op 模块单独桩——真机等待语义由
生产路径保留,测试画面为 mock 无需等待)。
"""

import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController

from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
)
from sr_od.application.currency_war.operations.cw_operation_base import (
    CwOperation,
)
from sr_od.application.currency_war.prep_actions import (
    drag_overlay_block_status,
    launch_battle_unified,
    locked_resume_sync_and_battle,
    prep_drag_overlay_gate,
)

#: 备战帧存档(备战两识别标志命中;发出链正常推进形态)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


class _LaunchHostOp(CwOperation):
    """发出链宿主 op(零节点;仅承载 screenshot/round_by_* 识别原语——
    发出链函数以函数形态直调,宿主不跑 execute)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        CwOperation.__init__(self, ctx, op_name='发出链测试宿主',
                             need_check_game_win=False)


class _LaunchTestController(FixtureController):
    """补发出链触达面的记录 stub:mouse_move 记录 + drag_to 双端记录
    (drag settle 先 mouse_move 后 drag_to,出战点击先 mouse_move 后
    click——mouse_move 序即机械动作时序证据)。"""

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


class _NoSleepTime:
    """模块级 ``time`` 替身:sleep 记录 no-op、其余属性透传真模块
    (harness _NoSleepTimeProxy 同款;覆盖不在宿主 MRO 内的动作 op 模块)。"""

    def __init__(self, real_module: types.ModuleType) -> None:
        self._real = real_module
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)

    def __getattr__(self, name: str):
        return getattr(self._real, name)


#: 发出链机械段会裸睡的模块(统一拖动拖后等待 / 出战弹窗渲染等待 /
#: 统一拖拽原语 settle / 失焦守卫激活等待 / 席满守卫卖出动画等待)。
_NOSLEEP_MODULES: tuple[str, ...] = (
    'sr_od.application.currency_war.operations.cw_op.cw_move_unit_action',
    'sr_od.application.currency_war.operations.cw_op.cw_start_battle_action',
    'sr_od.application.currency_war.operations.cw_op.cw_prep_sell_bench_action',
    'sr_od.application.currency_war.operations.actions.drag_cw_char',
    'sr_od.application.currency_war.prep_actions',
)


@pytest.fixture
def launch_env(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch,
               ) -> tuple[SrTestContext, _LaunchHostOp, _LaunchTestController]:
    """发出链测试夹具:假控制器换装(monkeypatch 自动还原)+ 动作 op
    模块裸睡桩(模块当前无裸 time 引用则跳过——名单是超集)+ 宿主 op。"""
    ctrl = _LaunchTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    for mod_name in _NOSLEEP_MODULES:
        import importlib
        mod = importlib.import_module(mod_name)
        if hasattr(mod, 'time'):
            monkeypatch.setattr(mod, 'time', _NoSleepTime(mod.time))
    return test_context, _LaunchHostOp(test_context), ctrl


def _require_frame(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    screen_name, state = _PREP_FRAME
    if not test_context.has_screen(screen_name, state):
        pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _set_frame(ctrl: _LaunchTestController,
               frame: tuple[str, str]) -> None:
    ctrl.set_phases([{'frame': frame}])


def _attach_counters_ctx(test_context: SrTestContext,
                         monkeypatch: pytest.MonkeyPatch) -> dict:
    """挂假局与策略状态计数表(monkeypatch 还原 cw_match;counters =
    发出链分键计数的读面,strategy_state_of 经 session.strategy_state 取)。"""
    counters: dict = {}
    match = types.SimpleNamespace(session=types.SimpleNamespace(
        strategy_state=types.SimpleNamespace(cw4_counters=counters)))
    monkeypatch.setattr(test_context, 'cw_match', match)
    return counters


def _patch_deploy_plan(monkeypatch: pytest.MonkeyPatch,
                       moves: list[CwActionMoveUnitParam],
                       ) -> list[int]:
    """部署计划单一源打桩(计划函数 = _battle_chain_deploy_moves 函数级
    import 的源符号;返回调用计数容器供断言「跳过同步步」)。"""
    calls: list[int] = []

    def _fake(session) -> list:
        calls.append(1)
        return list(moves)

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan,
    )
    monkeypatch.setattr(deploy_plan, 'battle_chain_deploy_params', _fake)
    return calls


def _expected_center(ctx: SrTestContext, area_name: str
                     ) -> tuple[int, int]:
    """期望拖点/点击从同源 screen_info 档案现算(rect 中心;角色拖动族
    裸中心权威派生式,非手抄坐标)。"""
    area = ctx.screen_loader.get_area('货币战争-备战', area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: 货币战争-备战/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


def test_armed_deploys_then_battle_click(launch_env,
                                         monkeypatch) -> None:
    """armed 面发出序:部署原子序依序发出(拖拽双端 = screen_info 裸中心
    现算)、先于出战点击,出战点击命中「按钮-出战」返回 (True, detail)。
    时序证据 = mouse_move 序(两次拖拽 settle 在前,出战按钮在后)。"""
    test_context, host, ctrl = launch_env
    _require_frame(test_context)
    _set_frame(ctrl, _PREP_FRAME)
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    moves = [
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='front', dst_slot=1),
        CwActionMoveUnitParam(src_domain='bench', src_slot=1,
                              dst_domain='front', dst_slot=2),
    ]
    _patch_deploy_plan(monkeypatch, moves)

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert ok, f'armed 面应发出成功,实际 detail={detail!r}'
    exp_b0 = _expected_center(test_context, '备战栏-1')
    exp_f1 = _expected_center(test_context, '前排-1')
    exp_b1 = _expected_center(test_context, '备战栏-2')
    exp_f2 = _expected_center(test_context, '前排-2')
    exp_btn = _expected_center(test_context, '按钮-出战')
    assert ctrl.recorded_drags == [(exp_b0, exp_f1), (exp_b1, exp_f2)], \
        f'部署原子序应按计划序发出,实际 {ctrl.recorded_drags}'
    assert ctrl.recorded_mouse_moves == [exp_b0, exp_b1, exp_btn], \
        (f'机械时序应为 拖拽settle×2 → 出战按钮(mouse_move 序),'
         f'实际 {ctrl.recorded_mouse_moves}')
    assert ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'出战点击应命中按钮-出战 area,实际 {ctrl.recorded_clicks}'


def test_resume_sync_once_writes_evidence(launch_env,
                                          monkeypatch) -> None:
    """resume 面发出即写证据位:首调执行同步步部署原子序并置 Match 宿主
    ``locked_sync_done``;二调跳过同步步(部署计划零再执行零拖拽)、
    出战点击仍发。"""
    test_context, host, ctrl = launch_env
    _require_frame(test_context)
    _set_frame(ctrl, _PREP_FRAME)
    # 证据位宿主 = Match.locked_sync_done;初值 False = 生产前置(锁定确认
    # 同帧配对写 False 后才进首战)。
    match = types.SimpleNamespace(session=types.SimpleNamespace(),
                                  locked_sync_done=False)
    monkeypatch.setattr(test_context, 'cw_match', match)
    moves = [
        CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                              dst_domain='front', dst_slot=1),
    ]
    plan_calls = _patch_deploy_plan(monkeypatch, moves)

    ok1, detail1 = locked_resume_sync_and_battle(host, test_context)
    assert ok1, f'首调应发出成功,实际 detail={detail1!r}'
    assert test_context.cw_match.locked_sync_done is True, \
        '首调发出后应置证据位 locked_sync_done(Match 宿主)'
    assert plan_calls == [1], f'首调应执行一次部署计划,实际 {plan_calls}'
    assert len(ctrl.recorded_drags) == 1, \
        f'首调应发出同步步拖拽×1,实际 {ctrl.recorded_drags}'
    assert ctrl.click_hit_area('货币战争-备战', '按钮-出战')

    ok2, detail2 = locked_resume_sync_and_battle(host, test_context)
    assert ok2, f'二调应仍发出出战,实际 detail={detail2!r}'
    assert plan_calls == [1], \
        f'二调应跳过同步步(部署计划零再执行),实际 {plan_calls}'
    assert len(ctrl.recorded_drags) == 1, \
        f'二调不应再发拖拽,实际 {ctrl.recorded_drags}'
    assert ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        '二调出战点击仍应发出'


# ============================================================ drag 浮层守卫 helper(执行前输入契约拒绝)

#: 合成确认浮层帧存档(✓/✕ 双锚在场)。
_OVERLAY_FRAME: tuple[str, str] = ('货币战争-备战-合成确认', '合成确认浮层')
#: 角色详情面板帧存档(装备推荐/合成公式锚在场)。
_CHAR_DETAIL_FRAME: tuple[str, str] = ('货币战争-备战-角色详情', '信息tab')


def _require_gate_frames(test_context: SrTestContext) -> None:
    """守卫语料帧缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_OVERLAY_FRAME, _CHAR_DETAIL_FRAME, _PREP_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_overlay_gate_hits_synthesis_overlay(test_context) -> None:
    """合成确认浮层帧 → 守卫返回在场标识(单锚命中即拦,宁误拦口径)。"""
    _require_gate_frames(test_context)
    host = _LaunchHostOp(test_context)
    host.last_screenshot = test_context.load_screen(*_OVERLAY_FRAME)
    assert prep_drag_overlay_gate(host) == '合成确认浮层'


def test_overlay_gate_hits_char_detail(test_context) -> None:
    """角色详情面板帧 → 守卫返回在场标识(H3 退化链面板阻断面)。"""
    _require_gate_frames(test_context)
    host = _LaunchHostOp(test_context)
    host.last_screenshot = test_context.load_screen(*_CHAR_DETAIL_FRAME)
    assert prep_drag_overlay_gate(host) == '角色详情面板'


def test_overlay_gate_clean_on_prep_baseline(test_context) -> None:
    """干净备战帧 → None 放行(零误拦)。"""
    _require_gate_frames(test_context)
    host = _LaunchHostOp(test_context)
    host.last_screenshot = test_context.load_screen(*_PREP_FRAME)
    assert prep_drag_overlay_gate(host) is None


def test_overlay_block_status_receipt_mapping() -> None:
    """round_fail status → 受阻码闭集映射命中登记行(非原文兜底)。"""
    from sr_od.application.currency_war.prep_actions import (
        _prep_receipt_block_code,
    )
    for label in ('合成确认浮层', '角色详情面板'):
        status = drag_overlay_block_status(label)
        assert status.startswith('未执行:浮层在场')
        assert _prep_receipt_block_code(status) == \
            '未执行:浮层在场(合成确认/角色详情)', \
            f'{label} 的受阻码应命中登记行,实际 {_prep_receipt_block_code(status)}'


# ============================================================ 出战前置席满守卫(执行前输入契约守卫)
#
# 锁设计约定(守卫 = prep_actions.guard_bench_overflow_for_battle,
# 安装点 = launch_prepared_battle 部署原子序后、出战单击前):
# - 席满态(「备战席已满」告警横幅在场,实机实证:此态出战被游戏静默
#   忽略)→ 先卖一个备战席角色腾位(选槽 = 槽位表第一 unit 槽确定性
#   规则,零策略语义)→ 复查告警消失 → 放行出战(先卖后战时序);
# - 告警不在场 → 零行为变化(现役发出序断言由上方 armed 面测试承载,
#   干净帧上守卫零新增动作);
# - 告警在场但无角色可卖 → 出战未发出 (False, detail),交回外循环;
# - 卖出后复查告警仍在场(机械落空形态)→ 出战未发出 (False, detail)。

#: 席满帧存档(「备战席已满」告警横幅在场;告警 area OCR 命中实证帧)。
_OVERFLOW_FRAME: tuple[str, str] = ('货币战争-备战', 'rail_badge_prep_r4')


def _require_overflow_frame(test_context: SrTestContext) -> None:
    """席满帧存档缺失 skip(采到后自动恢复),不 error。"""
    if not test_context.has_screen(*_OVERFLOW_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_OVERFLOW_FRAME[0]}/'
                    f'{_OVERFLOW_FRAME[1]}.webp')


def _seed_overflow_gs(test_context: SrTestContext,
                      monkeypatch: pytest.MonkeyPatch,
                      *, bench_units: bool) -> None:
    """挂假局并种 game state(告警在场的状态容器镜像):
    bench 9 槽(bench_units=True 全 unit / False 全 empty)+
    overflow_warning=True + overflow_card + gold(卖出回金消费面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        BenchView,
        ChannelSig,
        Unit,
        game_state_of,
    )
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    gs = game_state_of(match.session)
    sig = ChannelSig(family='obs', actor='test')
    slot = (BenchSlot(kind='unit', unit=Unit(char_id='银狼', star=2,
                                             equips=[]))
            if bench_units else BenchSlot(kind='empty'))
    gs.observe(gs.bench, BenchView(slots=[slot] * 9, capacity=9), sig=sig)
    if bench_units:
        gs.observe(gs.overflow_warning, True, sig=sig)
        gs.observe(gs.overflow_card, '刃心', sig=sig)
        gs.observe(gs.gold, 100, sig=sig)


def test_overflow_guard_sells_then_battle(launch_env,
                                          monkeypatch) -> None:
    """席满态出战 → 先卖后战:告警在场 → 守卫卖备战栏-1 腾位(拖拽双端
    = 裸中心 → 出售区单一源)→ 复查告警消失(干净帧)→ 出战点击命中
    「按钮-出战」;机械时序 = 卖出 settle 在前(mouse_move 序)。"""
    test_context, host, ctrl = launch_env
    _require_overflow_frame(test_context)
    _seed_overflow_gs(test_context, monkeypatch, bench_units=True)
    _patch_deploy_plan(monkeypatch, [])
    # 截图序:守卫第一查(席满帧)→ 卖出 op 浮层守卫帧(仍席满帧,on_polls
    # 2 触发推进)→ 守卫复查(干净帧,告警消失)→ 出战按钮定位(干净帧)。
    ctrl.set_phases([{'frame': _OVERFLOW_FRAME, 'exit': ('on_polls', 2)},
                     {'frame': _PREP_FRAME}])

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert ok, f'席满腾位后应发出出战,实际 detail={detail!r}'
    exp_b1 = _expected_center(test_context, '备战栏-1')
    exp_sell = _expected_center(test_context, '区域-出售区')
    exp_btn = _expected_center(test_context, '按钮-出战')
    assert ctrl.recorded_drags == [(exp_b1, exp_sell)], \
        (f'席满守卫应先卖备战栏-1(拖至出售区),'
         f'实际 {ctrl.recorded_drags}')
    assert ctrl.recorded_mouse_moves == [exp_b1, exp_btn], \
        (f'机械时序应为 卖出settle(mouse_move 备战栏-1) → 出战按钮,'
         f'实际 {ctrl.recorded_mouse_moves}')
    assert ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'腾位后应发出出战点击,实际 {ctrl.recorded_clicks}'


def test_overflow_guard_fail_no_unit(launch_env,
                                     monkeypatch) -> None:
    """告警在场但无角色可卖(bench 全 empty)→ 出战未发出:
    (False, detail),零卖出拖拽、零出战点击。"""
    test_context, host, ctrl = launch_env
    _require_overflow_frame(test_context)
    _seed_overflow_gs(test_context, monkeypatch, bench_units=False)
    _patch_deploy_plan(monkeypatch, [])
    ctrl.set_phases([{'frame': _OVERFLOW_FRAME}])

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert not ok, f'无角色可卖应判失败,实际 detail={detail!r}'
    assert '无角色可卖' in detail, f'失败 detail 应带原因,实际 {detail!r}'
    assert ctrl.recorded_drags == [], \
        f'不应发生卖出拖拽,实际 {ctrl.recorded_drags}'
    assert not ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'出战不应发出,实际 {ctrl.recorded_clicks}'


def test_overflow_guard_fail_still_full_after_sell(launch_env,
                                                   monkeypatch) -> None:
    """卖出后告警仍在场(单帧剧本 = 复查仍席满,机械落空形态)→
    出战未发出:(False, detail),有卖出拖拽、零出战点击。"""
    test_context, host, ctrl = launch_env
    _require_overflow_frame(test_context)
    _seed_overflow_gs(test_context, monkeypatch, bench_units=True)
    _patch_deploy_plan(monkeypatch, [])
    ctrl.set_phases([{'frame': _OVERFLOW_FRAME}])

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert not ok, f'卖出后仍席满应判失败,实际 detail={detail!r}'
    assert '卖出后告警仍在场' in detail, \
        f'失败 detail 应带原因,实际 {detail!r}'
    assert ctrl.recorded_drags, \
        f'应发生卖出拖拽(守卫先卖),实际 {ctrl.recorded_drags}'
    assert not ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'腾位失败不应发出出战点击,实际 {ctrl.recorded_clicks}'
