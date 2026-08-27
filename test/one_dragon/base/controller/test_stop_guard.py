"""停机刹车语义锁(ADR-0396,W217;ADR-0406 手动端点豁免语义修订):停机信号后零游戏输入。

锁的是**语义**不锁实现:
- 闩语义:运行中被 stop_running 打断 → is_stop_interrupted=True;idle 杂散
  stop / 自然完成收口(finish_running)不置闩;start_running 清闩。
  **无显式消费入口**(ADR-0406 移除 consume_stop_interrupted——手动端点
  不再摘全局闩)。
- 守卫语义:controller 公开输入入口(click/drag/btn/scroll/input/mouse_move)
  在闩置位后抛 StopRunInterrupted,动作零落地。
- 手动豁免语义(ADR-0406):显式外部接管走 ``stop_guard_exemption`` 本地
  豁免——动作放行但闩不清位、豁免按线程隔离(run 线程视角守卫永远生效)。
- 穿透语义:守卫异常不被中间 op 层吞成普通失败——嵌套 op 链(外环→子 op→
  点击)停机后首个被拦输入即整链中止,外环不再继续下一节点(ADR-0388 实证
  的 director「已停止后又出战」形态由本层结构性消除)。

run 26 实证背景:.log/mcp_server.log 08-26 12:56:12「已停止[gui:hotkey]」后
12:56:16 director 仍点「出战成功」——stop 只设标志位,轮内执行链不查。
ADR-0406 实证背景(W241 A1b):stop_run 返回≠run 线程结束,MCP 手动端点在
run 收口期清全局闩 → unwind 中的多动作节点失去守卫成幽灵输入。
"""
import threading
from unittest.mock import MagicMock

import pytest

from one_dragon.base.controller.controller_base import ControllerBase
from one_dragon.base.controller.pc_controller_base import PcControllerBase
from one_dragon.base.controller.stop_guard import (
    StopRunInterrupted,
    stop_guard_exemption,
)
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)
from one_dragon.base.operation.operation import Operation
from one_dragon.base.operation.operation_node import operation_node
from one_dragon.base.operation.operation_round_result import OperationRoundResult


def _make_run_context() -> ApplicationRunContext:
    """真实 ApplicationRunContext(ctx 为 mock;start 路径控制器返 True)。"""
    ctx = MagicMock(name='OneDragonContext')
    ctx.controller.init_before_context_run.return_value = True
    return ApplicationRunContext(ctx)


# ============ ① 闩语义 ============


def test_latch_idle_stop_does_not_arm():
    """idle 态杂散 stop 不置闩(STOP 也是 idle 初始态,不能作中断判据)。"""
    rc = _make_run_context()
    rc.stop_running(reason='stray')
    assert rc.is_stop_interrupted is False


def test_latch_armed_on_live_stop_and_cleared_on_start():
    """运行中被停 → 置闩;新运行 start_running → 清闩。"""
    rc = _make_run_context()
    assert rc.start_running() is True
    rc.stop_running(reason='gui:hotkey')
    assert rc.is_stop_interrupted is True
    assert rc.start_running() is True
    assert rc.is_stop_interrupted is False


def test_latch_pause_stop_also_arms():
    """暂停中被停 = 合理中断,同样置闩。"""
    rc = _make_run_context()
    rc.start_running()
    rc.switch_context_pause_and_run()
    rc.stop_running(reason='gui:hotkey')
    assert rc.is_stop_interrupted is True


def test_finish_running_does_not_arm_latch():
    """自然完成收口(finish_running,backend op 槽 finally)不置闩——
    否则后续 MCP 手动操作(残局清理)会被守卫误拦。"""
    rc = _make_run_context()
    rc.start_running()
    result = rc.finish_running()
    assert result is not None
    assert rc.is_stop_interrupted is False


def test_no_consume_entry_on_latch():
    """无显式消费入口(ADR-0406):consume_stop_interrupted 已移除——
    手动端点不再有「单 actor 清全局闩」路径,闩只由 start_running 清。"""
    rc = _make_run_context()
    rc.start_running()
    rc.stop_running(reason='mcp:stop_run')
    assert rc.is_stop_interrupted is True
    assert not hasattr(rc, 'consume_stop_interrupted')


# ============ ② 守卫语义(controller 输入入口) ============


class _RecordingController(ControllerBase):
    """带守卫的记录型 controller:模拟真实 controller「输入入口先查守卫」。"""

    def __init__(self) -> None:
        ControllerBase.__init__(self)
        self.actions: list[str] = []

    @property
    def is_game_window_ready(self) -> bool:
        """恒 True:绕过框架注入的「检测游戏窗口」前置节点。"""
        return True

    def _guard_and_record(self, name: str) -> None:
        self._check_stop_guard()
        self.actions.append(name)

    def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False,
              gamepad_key: str | None = None) -> bool:
        self._guard_and_record('click')
        return True

    def drag_to(self, end: Point, start: Point | None = None, duration: float = 0.5) -> None:
        self._guard_and_record('drag')

    def btn_tap(self, key: str) -> None:
        self._guard_and_record(f'btn_tap:{key}')

    def scroll(self, down: int, pos: Point | None = None) -> None:
        self._guard_and_record('scroll')

    def input_str(self, to_input: str, interval: float = 0.1) -> None:
        self._guard_and_record('input')

    def mouse_move(self, game_pos: Point) -> None:
        self._guard_and_record('mouse_move')


def test_guard_blocks_all_input_entries_when_armed():
    """闩置位后全部输入入口抛 StopRunInterrupted 且零动作落地。"""
    c = _RecordingController()
    c.stop_guard = lambda: True
    for act in (
        lambda: c.click(Point(100, 100)),
        lambda: c.drag_to(Point(200, 200), Point(100, 100)),
        lambda: c.btn_tap('esc'),
        lambda: c.scroll(1),
        lambda: c.input_str('x'),
        lambda: c.mouse_move(Point(1, 1)),
    ):
        with pytest.raises(StopRunInterrupted):
            act()
    assert c.actions == [], '停机后不得有任何输入动作落地'


def test_guard_inactive_when_not_armed_or_unwired():
    """闩未置位 / 未接线(stop_guard=None)不误拦。"""
    c = _RecordingController()
    c.stop_guard = lambda: False
    assert c.click(Point(1, 1)) is True
    c.stop_guard = None
    c.btn_tap('w')
    assert c.actions == ['click', 'btn_tap:w']


def test_pc_controller_real_entries_guarded():
    """真实 PcControllerBase 公开输入入口带守卫(绕过 __init__,只验入口首行
    拦截——守卫先于任何 win32/pyautogui 调用,无需真实窗口)。"""
    c = PcControllerBase.__new__(PcControllerBase)
    c.stop_guard = lambda: True
    with pytest.raises(StopRunInterrupted):
        c.click(Point(100, 100))
    with pytest.raises(StopRunInterrupted):
        c.btn_tap('esc')
    with pytest.raises(StopRunInterrupted):
        c.btn_press('w', 1.0)
    with pytest.raises(StopRunInterrupted):
        c.drag_to(Point(2, 2), Point(1, 1))
    with pytest.raises(StopRunInterrupted):
        c.scroll(1)
    with pytest.raises(StopRunInterrupted):
        c.input_str('x')
    with pytest.raises(StopRunInterrupted):
        c.mouse_move(Point(1, 1))


# ============ ②b 手动豁免语义(ADR-0406:手动端点不清闩,本地豁免) ============


def test_exemption_passes_but_keeps_latch_armed():
    """本地豁免:闩置位下豁免内动作放行,且闩不清位——豁免退出后同线程
    (模拟 run 线程视角)的后续输入仍被拦(ADR-0406 核心:收口期守卫仍活)。"""
    c = _RecordingController()
    rc = _make_run_context()
    rc.start_running()
    rc.stop_running(reason='mcp:stop_run')
    c.stop_guard = lambda: rc.is_stop_interrupted
    # 模拟 MCP 手动端点(click_game 内层形态):豁免令牌内 controller 调用
    with stop_guard_exemption():
        assert c.click(Point(100, 100)) is True
        c.btn_tap('esc')  # 无返回值,不抛即过
    assert c.actions == ['click', 'btn_tap:esc'], '豁免内手动动作应落地'
    # 闩未被清:run 收口期(unwind 中)的输入仍被守卫拦截
    assert rc.is_stop_interrupted is True
    with pytest.raises(StopRunInterrupted):
        c.click(Point(1, 1))


def test_exemption_is_thread_local():
    """豁免按线程隔离(模拟 run 线程视角):手动端点线程持有豁免期间,
    另一线程(run 线程)同时发起的输入仍被守卫拦截——线程级豁免而非
    全局开关,是「不清闩」修复不引入新竞态的关键性质。"""
    c = _RecordingController()
    c.stop_guard = lambda: True

    def _run_thread_input():
        # 模拟 unwind 中的 run 线程:无豁免,闩置位 → 被拦(异常就地吞,
        # 落地与否由 actions 断言)
        try:
            c.click(Point(1, 1))
        except StopRunInterrupted:
            pass

    with stop_guard_exemption():
        assert c.click(Point(100, 100)) is True  # 手动线程放行
        t = threading.Thread(target=_run_thread_input)
        t.start()
        t.join(timeout=5)
    assert not t.is_alive()
    assert c.actions == ['click'], 'run 线程输入不得落地(线程隔离)'

# ============ ③ 穿透语义:嵌套 op 链停机即整链中止 ============


class _InnerOp(Operation):
    """子 op:节点内连点 3 次;第 2 次后模拟用户停机(轮内 stop,
    复现 run 26 形态:stop 到达时节点方法仍在执行)。"""

    def __init__(self, ctx, controller: _RecordingController):
        Operation.__init__(self, ctx, op_name='内侧链')
        self._controller = controller

    @operation_node(name='内侧节点', is_start_node=True)
    def _node(self) -> OperationRoundResult:
        for i in range(3):
            self._controller.click(Point(10 + i, 10))
            if i == 1:  # 第 2 次点击后用户按停
                self.ctx.run_context.stop_running(reason='gui:hotkey')
        return self.round_success('内侧完成(停机后不应到达)')


class _OuterOp(Operation):
    """外环(模拟 PrepDirector/battle_loop 形态):节点内调子 op.execute(),
    子 op 返回失败后**外环仍想继续下一节点再点一次**——守卫语义下这一次
    必须被拦,且异常穿出到外环 execute 之外。"""

    def __init__(self, ctx, controller: _RecordingController):
        Operation.__init__(self, ctx, op_name='外侧环')
        self._controller = controller

    @operation_node(name='环节点', is_start_node=True)
    def _step(self) -> OperationRoundResult:
        inner = _InnerOp(self.ctx, self._controller)
        inner.execute()  # 子 op 被守卫中断后向上抛,不得在此被吞
        return self.round_success('子链完成')

    @operation_node(name='环下一节点')
    def _next_step(self) -> OperationRoundResult:
        self._controller.click(Point(999, 999))  # 停机后不得到达
        return self.round_success('下一节点')


def _restore_session_run_state(test_context) -> None:
    """还原 session 级 run_context 状态(纪律①:test_context 共享)。

    本文件两处测试会在 session run_context 上留下 last_run_result(非 None)
    与停机闩——前者会被 ADR-0388 的 CW 刹车判据(last_run_result is not None)
    当成「运行中被停」误拦后续测试文件的 executor 路径(全量实测污染)。
    """
    rc = test_context.run_context
    rc.last_run_result = None
    rc._stop_interrupted = False  # noqa: SLF001


def test_stop_mid_round_blocks_rest_of_chain(test_context, monkeypatch):
    """核心锁:停机信号到达后,本轮执行链剩余点击 + 后续节点全部中止。

    复现 run 26/27 事故形态(stop 时轮内链在跑),断言:
    ① 落地点击 = 停机前的 2 次,停机后的第 3 次与外环下一节点 0 落地;
    ② StopRunInterrupted 穿透外环 execute 抛出(不被吞成普通失败)。
    """
    from test.harness.fixture_controller import (
        enter_running_state,
        reset_running_state,
    )

    controller = _RecordingController()
    rc = test_context.run_context
    controller.stop_guard = lambda: rc.is_stop_interrupted
    monkeypatch.setattr(test_context, 'controller', controller)

    enter_running_state(test_context)
    op = _OuterOp(test_context, controller)
    try:
        with pytest.raises(StopRunInterrupted):
            op.execute()
    finally:
        reset_running_state(test_context, op)
        _restore_session_run_state(test_context)

    assert controller.actions.count('click') == 2, \
        f'停机后必须零输入:期待恰 2 次停机前点击,实得 {controller.actions}'


def test_run_application_collects_guard_stop_as_stopped(test_context, monkeypatch):
    """顶层收口:守卫中断经 run_application 收口为「已停止」,非执行异常。"""
    from one_dragon.base.operation.application.application_run_context import (
        RunFinishReason,
    )

    rc = test_context.run_context
    monkeypatch.setattr(rc, '_application_factory_map', {})
    controller = _RecordingController()
    controller.stop_guard = lambda: rc.is_stop_interrupted
    monkeypatch.setattr(test_context, 'controller', controller)
    # run_application → start_running 需要控制器初始化返 True
    monkeypatch.setattr(controller, 'init_before_context_run', lambda: True)

    class _Factory:
        app_id = 'stop_guard_probe'
        app_name = '停机守卫探针'

        def __init__(self) -> None:
            self.created: list[_OuterOp] = []

        def create_application(self, instance_idx, group_id):
            op = _OuterOp(test_context, controller)
            self.created.append(op)
            return op

    factory = _Factory()
    rc._application_factory_map['stop_guard_probe'] = factory
    monkeypatch.setattr(test_context, 'ready_for_application', True, raising=False)

    result = rc.run_application('stop_guard_probe', 0, 'default')
    assert result.finish_reason == RunFinishReason.STOPPED
    assert rc.last_application_result is not None
    assert rc.last_application_result.status.startswith('已停止')
    assert 'gui:hotkey' in rc.last_application_result.status
    # 顶层收口后复位 session 态(不污染后续测试文件;闩复位由
    # _restore_session_run_state 直改,ADR-0406 后无消费入口)
    from test.harness.fixture_controller import reset_running_state
    for op in factory.created:
        reset_running_state(test_context, op)
    _restore_session_run_state(test_context)
