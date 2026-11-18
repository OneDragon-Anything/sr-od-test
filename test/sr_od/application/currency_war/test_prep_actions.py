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
#: 非备战帧存档(屏态复验 stale 形态;遭遇面板盖住槽区,两识别标志 miss)。
_STALE_FRAME: tuple[str, str] = ('货币战争-遭遇节点', 'default')


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
#: 统一拖拽原语 settle / 失焦守卫激活等待)。
_NOSLEEP_MODULES: tuple[str, ...] = (
    'sr_od.application.currency_war.operations.cw_op.cw_move_unit_action',
    'sr_od.application.currency_war.operations.cw_op.cw_start_battle_action',
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
    for screen_name, state in (_PREP_FRAME, _STALE_FRAME):
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


def test_screen_recheck_stale_gives_up(launch_env,
                                       monkeypatch) -> None:
    """屏态复验 stale 放弃:fresh 帧备战标志 miss → (False,
    'readiness_stale_screen') 零发出,分键计数落 readiness_stale_screen。"""
    test_context, host, ctrl = launch_env
    _require_frame(test_context)
    _set_frame(ctrl, _STALE_FRAME)
    counters = _attach_counters_ctx(test_context, monkeypatch)

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert (ok, detail) == (False, 'readiness_stale_screen'), \
        f'stale 帧应放弃发射,实际 ({ok}, {detail!r})'
    assert ctrl.recorded_drags == [], 'stale 放弃不应有拖拽'
    assert ctrl.recorded_clicks == [], 'stale 放弃不应有点击'
    assert counters.get('readiness_stale_screen') == 1, \
        f'stale 分键应计 1,实际 {counters!r}'


def test_overlay_gate_holds_launch(launch_env,
                                   monkeypatch) -> None:
    """浮层闸门 hold:备战标志穿透命中但身份分发名单命中非备战屏 →
    (False, 'readiness_overlay_hold:<屏名>') 零发出 + 分键计数。
    (身份读点 = prep_actions 模块级 get_match_screen_name 绑定,打桩
    模拟「浮层在场」读数;屏态复验仍走真帧识别。)
    """
    test_context, host, ctrl = launch_env
    _require_frame(test_context)
    _set_frame(ctrl, _PREP_FRAME)
    counters = _attach_counters_ctx(test_context, monkeypatch)
    import sr_od.application.currency_war.prep_actions as pa
    monkeypatch.setattr(pa, 'get_match_screen_name',
                        lambda *a, **k: '货币战争-投资策略')

    ok, detail = launch_battle_unified(host, test_context, face='armed')

    assert (ok, detail) == (False, 'readiness_overlay_hold:货币战争-投资策略'), \
        f'浮层在场应 hold,实际 ({ok}, {detail!r})'
    assert ctrl.recorded_drags == [], '浮层 hold 不应有拖拽'
    assert ctrl.recorded_clicks == [], '浮层 hold 不应有点击'
    assert counters.get('readiness_overlay_hold') == 1, \
        f'hold 分键应计 1,实际 {counters!r}'


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
