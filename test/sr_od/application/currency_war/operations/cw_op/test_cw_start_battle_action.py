"""CwActionStartBattleOp 出战单击原子行为测试(harness 剧本)。

锁设计约定(单击原子:定位动作本体 → 单击一次 → 自上报 → round_success
交回主循环;零收尾零验证——点击后的弹窗渲染/画面转移归下一帧观察,
弹窗处理归独立弹窗 op 经主循环阶段一身份分发接管):

- 备战帧有「按钮-出战」→ 恰一次点击(落出战档)+ 上报出口
  battle_resolve(next_screen = 结算屏)+ env.skip_substate=False + 终结返回;
- 免战帧(免战与开商店叠加帧,出战按钮变「跳过」形态)→ fallback 点跳过
  (不点出战)+ skip_substate=True 携带(env 回执位)+ 上报出口 battle_skip;
- 出战点击后弹窗帧弹出(未达上限警告在场)→ 只点出战、零弹窗区点击、
  直接返回(段间识别仅限动作本体定位,op 内无弹窗识别/收尾);
- 弹窗主路径(loop 镜像锚,以 loop 分派层 ``_dispatch_identity_screen``
  直调形态驱动):出战点击返回 → 下一帧弹窗帧 → 阶段一身份分发接住
  弹窗 op → 确认点击 → 交回主循环(轮转等待)。未达上限警告与前台
  无角色两形态同构覆盖。
"""

import time
import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.kernel.cw_game_state import SCREEN_SETTLE
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionStartBattleParam,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop
from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
    CwActionStartBattleOp,
)
from sr_od.application.currency_war.operations.cw_operation_base import CwOperation
from sr_od.application.currency_war.prep_actions import (
    PrepActionExecutor,
    PrepExecEnv,
)

#: 备战帧存档(有「按钮-出战」)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')
#: 免战叠加帧存档(免战牌激活,出战按钮变「跳过」;与开商店态叠加)。
_SKIP_FRAME: tuple[str, str] = ('货币战争-备战-开商店', '免战叠加态')
#: 未达上限警告弹窗帧存档。
_POPUP_DEPLOY_FRAME: tuple[str, str] = ('货币战争-未达上限警告', 'default')
#: 前台无角色提示弹窗帧存档。
_POPUP_NO_FRONT_FRAME: tuple[str, str] = ('货币战争-提示-前台无角色', '出战被拒')


class _ClickRecordingController(FixtureController):
    """补出战 op 触达面的记录 stub:mouse_move 记录(防吞点击前置动作)。"""

    def __init__(self, ctx: SrTestContext, standard_width: int = 1920,
                 standard_height: int = 1080) -> None:
        FixtureController.__init__(self, ctx,
                                   standard_width=standard_width,
                                   standard_height=standard_height)
        self.recorded_mouse_moves: list[tuple[int, int]] = []

    def mouse_move(self, pos) -> None:
        self.recorded_mouse_moves.append((int(pos.x), int(pos.y)))


class _HostOp(CwOperation):
    """测试宿主 op(生产 = 备战画面 op;op 体仅消费其 screenshot /
    round_by_find_area 原语,继承面用最小 CwOperation 形态)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        CwOperation.__init__(self, ctx, op_name='cw_start_battle_test_host',
                             need_check_game_win=False)


class _WatchedStartBattle(WatchdogOperationMixin, CwActionStartBattleOp):
    """带看门狗的出战 op(流程测试防无限轮)。"""


class _NoSleepTime:
    """模块级 time 替身:sleep 记 no-op,其余属性透传真模块。

    覆盖「弹窗 op 模块内裸 import time 直睡」的写法(fast_sleep 按被测
    op MRO 挂桩,分派层内部构造的 op 其模块不在桩面)。
    """

    def __init__(self, real_module: object) -> None:
        self._real_module: object = real_module

    def sleep(self, seconds: float) -> None:
        pass

    def __getattr__(self, name: str):
        return getattr(self._real_module, name)


def _require_screens(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_PREP_FRAME, _SKIP_FRAME,
                               _POPUP_DEPLOY_FRAME, _POPUP_NO_FRONT_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _make_env(test_context: SrTestContext,
              match: object) -> tuple[PrepExecEnv, PrepActionExecutor]:
    """生产形态组装:宿主 op → 执行器 → 执行环境(op 体消费同一三件)。"""
    host = _HostOp(test_context)
    executor = PrepActionExecutor(host, test_context)
    env = PrepExecEnv(op=host, match=match, config=None, executor=executor)
    return env, executor


def _run_start_battle(test_context: SrTestContext,
                      monkeypatch: pytest.MonkeyPatch,
                      phases: list[dict],
                      match: object = None,
                      ) -> tuple[_ClickRecordingController, object,
                                 PrepExecEnv]:
    """装假控制器 + 跑完整 execute(),返回(控制器, 结果, env)供断言。"""
    ctrl = _ClickRecordingController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases(phases)
    env, _executor = _make_env(test_context, match)
    op = _WatchedStartBattle(test_context, CwActionStartBattleParam(), env=env)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result, env


def test_prep_frame_single_click_report_and_return(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 A:备战帧有「按钮-出战」→ 恰一次点击 + 上报出口
    battle_resolve(skip=False)+ 终结返回。"""
    _require_screens(test_context)
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    ctrl, result, env = _run_start_battle(
        test_context, monkeypatch, [{'frame': _PREP_FRAME}], match=match)

    assert result.success, f'出战点击应终结返回,实际 {result.status}'
    assert len(ctrl.recorded_clicks) == 1, (
        f'单击原子:应恰一次点击:{ctrl.recorded_clicks}')
    assert len(ctrl.recorded_mouse_moves) == 1, (
        f'点击前防吞 mouse_move 恰一次:{ctrl.recorded_mouse_moves}')
    assert ctrl.click_hit_area(_PREP_FRAME[0], '按钮-出战')
    assert env.skip_substate is False, '常规出战帧 skip_substate 应为 False'
    # 上报出口(声明随 round 结果 data 回传):常规出口 = battle_resolve,
    # next_screen = 结算屏。
    assert result.data is not None and result.data.trigger == 'battle_resolve'
    assert result.data.next_screen == SCREEN_SETTLE


def test_skip_fallback_clicks_skip_button(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 B:免战帧只有「按钮-跳过」→ fallback 点跳过(不点出战)+
    skip_substate 携带(env 回执位)+ 上报出口 battle_skip。"""
    _require_screens(test_context)
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    ctrl, result, env = _run_start_battle(
        test_context, monkeypatch, [{'frame': _SKIP_FRAME}], match=match)

    assert result.success, f'免战跳过点击应终结返回,实际 {result.status}'
    assert len(ctrl.recorded_clicks) == 1, (
        f'单击原子:应恰一次点击:{ctrl.recorded_clicks}')
    assert ctrl.click_hit_area(_PREP_FRAME[0], '按钮-跳过'), (
        f'应点「按钮-跳过」档(area 单源备战屏):{ctrl.recorded_clicks}')
    assert env.skip_substate is True, '跳过子态事实应写 env 回执位'
    assert result.data is not None and result.data.trigger == 'battle_skip'


def test_popup_frame_clicks_battle_only_no_settle(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 C:出战点击后弹窗帧弹出(未达上限警告在场)→ op 只点出战、
    零弹窗区点击、直接返回(零收尾:op 内无弹窗识别/勾选/确认,弹窗帧
    不再截屏不反应)。"""
    _require_screens(test_context)
    ctrl, result, _env = _run_start_battle(test_context, monkeypatch, [
        {'frame': _PREP_FRAME,
         'exit': ('on_click_in', _PREP_FRAME[0], '按钮-出战')},
        {'frame': _POPUP_DEPLOY_FRAME},
    ])

    assert result.success, f'出战点击应终结返回,实际 {result.status}'
    assert ctrl.click_hit_area(_PREP_FRAME[0], '按钮-出战')
    assert len(ctrl.recorded_clicks) == 1, (
        f'应只点出战一次:{ctrl.recorded_clicks}')
    assert ctrl.phase_idx == 1, (
        f'点击后弹窗帧已弹出(op 未再截屏不反应):phase_idx={ctrl.phase_idx}')
    assert not ctrl.click_hit_area(_POPUP_DEPLOY_FRAME[0], '按钮-确认'), (
        f'出战 op 不得处理弹窗(确认点击残留):{ctrl.recorded_clicks}')
    assert not ctrl.click_hit_area(
        _POPUP_DEPLOY_FRAME[0], '勾选-本局不再提示'), (
        f'出战 op 不得勾选弹窗(勾选点击残留):{ctrl.recorded_clicks}')


def _run_popup_main_path(test_context: SrTestContext,
                         monkeypatch: pytest.MonkeyPatch,
                         popup_frame: tuple[str, str],
                         confirm_area: str,
                         dispatch_screen: str,
                         tmp_path) -> tuple[_ClickRecordingController,
                                            object, object]:
    """弹窗主路径剧本(loop 镜像锚,分派层直调形态):

    出战点击返回 → 下一帧弹窗帧 → 阶段一身份分发接住弹窗 op → 确认 →
    交回。分派层用 ``CwLoop._dispatch_identity_screen`` 直调(最小壳:
    该分支消费 ctx + 分派包装,不触循环体其余分支)。
    """
    ctrl = _ClickRecordingController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _PREP_FRAME,
         'exit': ('on_click_in', _PREP_FRAME[0], '按钮-出战')},
        {'frame': popup_frame,
         'exit': ('on_click_in', popup_frame[0], confirm_area)},
        {'frame': _PREP_FRAME},
    ])
    env, _executor = _make_env(test_context, match=None)
    op = _WatchedStartBattle(test_context, CwActionStartBattleParam(), env=env)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            start_result = op.execute()
        assert start_result.success, (
            f'出战点击应终结返回,实际 {start_result.status}')
        assert ctrl.phase_idx == 1, (
            f'出战点击应推进到弹窗帧:phase_idx={ctrl.phase_idx}')

        # —— 分派层直调形态的装缝(零真实落盘):决策帧留存证据桩
        # (先例 = harness/sim_backend_runner 装配缝 1)+ 弹窗 op 模块内
        # 裸 time 直睡桩(fast_sleep 桩面按被测 op MRO,分派内部构造的
        # op 模块不在其中)。
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', lambda *a, **k: None)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.decision_frame_hooks.'
            'get_project_root', lambda: tmp_path)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_screen.'
            'cw_screen_deploy_not_full.time', _NoSleepTime(time))
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_screen.'
            '_overlay_confirm.time', _NoSleepTime(time))
        loop_shell = CwLoop.__new__(CwLoop)
        loop_shell.ctx = test_context
        loop_shell.last_screenshot = None
        with fast_sleep(loop_shell):
            dispatch_result = loop_shell._dispatch_identity_screen(
                dispatch_screen, ctrl.current_frame)
    finally:
        reset_running_state(test_context, op)
    return ctrl, start_result, dispatch_result


def test_popup_main_path_deploy_not_full(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """剧本 D(未达上限警告形态):出战点击返回 → 下一帧弹窗帧 → 阶段一
    身份分发接住弹窗 op → 勾选 + 确认 → 交回主循环。"""
    _require_screens(test_context)
    ctrl, _start_result, dispatch_result = _run_popup_main_path(
        test_context, monkeypatch, _POPUP_DEPLOY_FRAME,
        confirm_area='按钮-确认', dispatch_screen='货币战争-未达上限警告',
        tmp_path=tmp_path)

    assert ctrl.click_hit_area(_POPUP_DEPLOY_FRAME[0], '按钮-确认'), (
        f'弹窗 op 应发确认点击:{ctrl.recorded_clicks}')
    assert ctrl.phase_idx == 2, (
        f'确认点击应推进到交回帧:phase_idx={ctrl.phase_idx}')
    # 交回语义 = 分派包装默认映射 round_wait(轮转等待,交回主循环)。
    assert dispatch_result.result == OperationRoundResultEnum.WAIT, (
        f'弹窗 op 处理完应交回主循环,实际 {dispatch_result.result}')


def test_popup_main_path_no_front_hint(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """剧本 D(前台无角色形态):出战点击返回 → 下一帧弹窗帧 → 阶段一
    身份分发接住弹窗 op → 确认 → 交回主循环。"""
    _require_screens(test_context)
    ctrl, _start_result, dispatch_result = _run_popup_main_path(
        test_context, monkeypatch, _POPUP_NO_FRONT_FRAME,
        confirm_area='按钮-确认', dispatch_screen='货币战争-提示-前台无角色',
        tmp_path=tmp_path)

    assert ctrl.click_hit_area(_POPUP_NO_FRONT_FRAME[0], '按钮-确认'), (
        f'弹窗 op 应发确认点击:{ctrl.recorded_clicks}')
    assert ctrl.phase_idx == 2, (
        f'确认点击应推进到交回帧:phase_idx={ctrl.phase_idx}')
    assert dispatch_result.result == OperationRoundResultEnum.WAIT, (
        f'弹窗 op 处理完应交回主循环,实际 {dispatch_result.result}')
