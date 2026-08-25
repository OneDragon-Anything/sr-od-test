"""Fixture 驱动的 op 流程测试脚手架(从 ZZZ ``zzz-od-test/test/harness/fixture_controller.py``
同步,SrContext 适配)。

提供两类能力:

1. :class:`FixtureController` —— 继承现有 ``MockController``,充当"反应式假游戏":
   按剧本(phase 列表)在多帧间推进,记录所有 click/input 动作,供多节点 op
   跑完整 ``execute()`` 循环。
2. :class:`WatchdogOperationMixin` —— 测试专用看门狗,覆盖 ``_execute_one_round``
   计总轮次,超阈值即置 ``_run_state=STOP``(框架的 WAIT 段无轮次上限)。

以及两个辅助:

- :func:`enter_running_state` —— 建立 op 执行前的运行态前置(``is_context_stop``
  默认 True 会让 op 首轮即退出)。
- :func:`reset_running_state` —— ``finally`` 中复位运行态 + 清理 event_bus 监听。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContextStateEnum,
)
from test.conftest import MockController

if TYPE_CHECKING:
    from test.conftest import SrTestContext


# --------------------------------------------------------------------------- #
# 假的子控制器 / 窗口对象:MockController 没有这些,而 op 会触达。
# --------------------------------------------------------------------------- #


class _FakeKeyboard:
    """pynput ``keyboard.Controller`` 的空实现,``type`` 记录到给定列表(供断言输入)。

    SR 增强(相对 ZZZ 的 pass):op 经 ``controller.keyboard_controller.keyboard.type``
    输入(如 ``input_account_password`` 输账号密码),记录后测试可断言输入发生。
    """

    def __init__(self, recorder: list[str]) -> None:
        self._recorder: list[str] = recorder

    def type(self, text: str) -> None:  # noqa: A003 - 对齐 pynput 接口名
        self._recorder.append(text)


class _FakeKeyboardMouse:
    """``KeyboardMouseController`` 的空实现。"""

    def __init__(self, recorder: list[str]) -> None:
        self.keyboard: _FakeKeyboard = _FakeKeyboard(recorder)

    def reset(self) -> None:
        pass


class _FakeBtnController:
    """``PcButtonController`` 的空实现,仅保留 ``tap`` 等按键接口。"""

    def tap(self, key: str) -> None:
        pass

    def press(self, key: str, press_time: float | None = None) -> None:
        pass

    def release(self, key: str) -> None:
        pass

    def tap_combo(self, keys: list[str]) -> None:
        pass

    def reset(self) -> None:
        pass


class _FakeGameWin:
    """``PcGameWindow`` 的最小替身,只暴露 ``win_title``。"""

    def __init__(self) -> None:
        self.win_title: str = '<fixture-fake-game-window>'


# --------------------------------------------------------------------------- #
# 剧本类型约定(phase)。
# --------------------------------------------------------------------------- #
#
# phase = {
#   'frame': (screen_name, state),            # 经 ctx.load_screen 读取的存档截图
#   'exit' : exit_spec,                       # 推进条件,见下;末 phase 可省略
# }
#
# exit_spec 取值:
#   ('on_click_in', screen_name, area_name)   # click 落在 area 的 pc_rect 内才推进
#   ('on_click_in', [x1, y1, x2, y2])         # click 落在显式坐标矩形内才推进
#   ('on_action',)                            # 任意 click/input 都推进(仅无恢复 click 的 phase)
#   ('on_polls', n)                           # screenshot() 调用 n 次后推进(游戏自动流转)


class FixtureController(MockController):
    """反应式假游戏控制器:按剧本人为推进画面、记录动作。

    继承 ``MockController``(已有 screenshot/click stub),新增:

    - 多帧推进(phase 列表 + exit 条件);
    - 补全 op 会触达的 stub 面(keyboard_controller/btn_controller/game_win/drag_to);
    - ``is_game_window_ready = True``,绕过框架注入的"检测游戏窗口→打开游戏"前置链;
    - 记录所有 click pos / input 文本,供断言。
    """

    def __init__(
        self,
        ctx: SrTestContext,
        standard_width: int = 1920,
        standard_height: int = 1080,
    ) -> None:
        MockController.__init__(
            self,
            game_config=ctx.game_config,
            standard_width=standard_width,
            standard_height=standard_height,
        )
        self.ctx: SrTestContext = ctx

        # 剧本与推进状态
        self._phases: list[dict] = []
        self._phase_idx: int = 0
        self._poll_count: int = 0

        # 动作记录(供测试断言)
        self.recorded_clicks: list[Point] = []
        self.recorded_inputs: list[str] = []

        # MockController 缺失、但 op 会触达的子对象;
        # _FakeKeyboard.type 记录到 self.recorded_inputs(供断言输入账密)。
        self.keyboard_controller: _FakeKeyboardMouse = _FakeKeyboardMouse(self.recorded_inputs)
        self.btn_controller: _FakeBtnController = _FakeBtnController()
        self.game_win: _FakeGameWin = _FakeGameWin()

    # ----------------------------- 剧本管理 ----------------------------- #

    def set_phases(self, phases: list[dict]) -> None:
        """载入剧本并重置推进状态。"""
        self._phases = list(phases)
        self._phase_idx = 0
        self._poll_count = 0
        self.recorded_clicks.clear()
        self.recorded_inputs.clear()

    @property
    def phase_idx(self) -> int:
        return self._phase_idx

    @property
    def current_frame(self) -> MatLike:
        """当前 phase 对应的存档截图。"""
        phase = self._phases[self._phase_idx]
        screen_name, state = phase['frame']
        return self.ctx.load_screen(screen_name, state)

    # ----------------------------- 框架接口 ----------------------------- #

    @property
    def is_game_window_ready(self) -> bool:
        """恒为 True:绕过"检测游戏窗口→打开游戏"前置链。"""
        return True

    def get_screenshot(self, independent: bool = False) -> MatLike:
        """返回当前 phase 的帧;按 ``on_polls`` 推进由基类 screenshot 调用链外单独处理。

        这里直接返回当前帧(不推进),推进放在 :meth:`screenshot` 重写中。
        """
        return self.current_frame

    def screenshot(self, independent: bool = False) -> tuple[float, MatLike]:
        """返回当前 phase 的帧,并按 ``on_polls`` 推进。"""
        frame = self.current_frame
        # 同步到父类 mock_screenshot,保持与 MockController 行为一致
        self.mock_screenshot = frame

        self._maybe_advance_on_polls()

        return time.time(), frame

    def click(
        self,
        pos: Point | None = None,
        press_time: float = 0,
        pc_alt: bool = False,
        gamepad_key: str | None = None,
    ) -> bool:
        """记录 click,并按 ``on_click_in``/``on_action`` 推进。

        Returns:
            与 ``MockController`` 一致的 in-bounds 布尔(供框架判断点击是否成功)。
        """
        if pos is not None:
            self.recorded_clicks.append(Point(int(pos.x), int(pos.y)))
            in_bounds = (
                0 <= pos.x < self.standard_width
                and 0 <= pos.y < self.standard_height
            )
        else:
            in_bounds = True

        self._maybe_advance_on_click(pos)
        return in_bounds

    # op 偶尔触达的输入/拖拽接口:MockController 未覆盖,这里补 stub + 记录。

    def input_str(self, to_input: str, interval: float = 0.1) -> None:
        self.recorded_inputs.append(to_input)

    def delete_all_input(self) -> None:  # noqa: D401 - stub
        pass

    def drag_to(
        self,
        end: Point,
        start: Point | None = None,
        duration: float = 0.5,
    ) -> None:
        # 国际服换服滚动会触达;CN 登录流程不会。记录一次 click 以便调试。
        self.recorded_clicks.append(Point(int(end.x), int(end.y)))

    def active_window(self) -> None:
        """stub:op 调 controller.active_window 聚焦游戏窗口(测试无真实窗口,空操作)。"""
        pass

    # ----------------------------- 推进判定 ----------------------------- #

    def _current_exit(self) -> tuple | None:
        if self._phase_idx >= len(self._phases):
            return None
        return self._phases[self._phase_idx].get('exit')

    def _advance_phase(self) -> None:
        """推进到下一 phase(末 phase 不越界)。"""
        if self._phase_idx < len(self._phases) - 1:
            self._phase_idx += 1
            self._poll_count = 0

    def _maybe_advance_on_click(self, pos: Point | None) -> None:
        exit_spec = self._current_exit()
        if exit_spec is None or pos is None:
            return
        kind = exit_spec[0]
        if kind == 'on_click_in':
            region = self._resolve_region(exit_spec)
            if region is not None and self._pos_in_region(pos, region):
                self._advance_phase()
        elif kind == 'on_action':
            self._advance_phase()
        # on_polls / 未知类型:不在 click 时推进

    def _maybe_advance_on_polls(self) -> None:
        exit_spec = self._current_exit()
        if exit_spec is None:
            return
        if exit_spec[0] != 'on_polls':
            return
        n: int = int(exit_spec[1])
        self._poll_count += 1
        if self._poll_count >= n:
            self._advance_phase()

    def _resolve_region(self, exit_spec: tuple) -> tuple[int, int, int, int] | None:
        """``on_click_in`` 的目标区域 → ``(x1, y1, x2, y2)``。

        支持两种形式:

        - ``('on_click_in', [x1, y1, x2, y2])`` 显式坐标矩形;
        - ``('on_click_in', screen_name, area_name)`` 查 screen_info 的 pc_rect。
        """
        arg = exit_spec[1]
        if (
            isinstance(arg, list | tuple)
            and len(arg) == 4
            and all(isinstance(v, int | float) for v in arg)
        ):
            x1, y1, x2, y2 = arg
            return int(x1), int(y1), int(x2), int(y2)

        if len(exit_spec) >= 3:
            screen_name, area_name = exit_spec[1], exit_spec[2]
            area = self.ctx.screen_loader.get_area(screen_name, area_name)
            if area is None:
                return None
            rect = area.pc_rect
            return rect.x1, rect.y1, rect.x2, rect.y2
        return None

    @staticmethod
    def _pos_in_region(
        pos: Point, region: tuple[int, int, int, int]
    ) -> bool:
        x1, y1, x2, y2 = region
        return x1 <= pos.x <= x2 and y1 <= pos.y <= y2

    # ----------------------------- 断言辅助 ----------------------------- #

    def click_hit_area(self, screen_name: str, area_name: str) -> bool:
        """是否记录过落在指定 area 内的 click。"""
        area = self.ctx.screen_loader.get_area(screen_name, area_name)
        if area is None:
            return False
        rect = area.pc_rect
        region = (rect.x1, rect.y1, rect.x2, rect.y2)
        return any(
            self._pos_in_region(p, region) for p in self.recorded_clicks
        )


# --------------------------------------------------------------------------- #
# 看门狗:覆盖 _execute_one_round,计总轮次,超限即 STOP。
# --------------------------------------------------------------------------- #


class WatchdogOperationMixin:
    """测试专用看门狗混入。

    框架的 round 上限只管 RETRY;WAIT 会重置 ``node_retry_times`` 死循环。
    本混入覆盖 ``_execute_one_round``(循环内每轮调一次),计总轮次 > N 时
    直接置 ``ctx.run_context._run_state = STOP``,父类 ``execute`` 在下轮
    的 ``is_context_stop`` 检查即退出。

    用法::

        class _WatchedEnterGame(WatchdogOperationMixin, EnterGame):
            pass

    注意 MRO:混入在前,``super()._execute_one_round()`` 解析到真正的 op 实现。
    """

    #: 总轮次上限(覆盖默认请在子类或实例上设置)。
    watchdog_max_rounds: int = 300

    def _init_watchdog(self) -> None:
        """在 ``execute()`` 前调用一次,重置计数。"""
        self._watchdog_round_count: int = 0

    def _execute_one_round(self):  # type: ignore[override]
        count = getattr(self, '_watchdog_round_count', 0) + 1
        self._watchdog_round_count = count
        if count > self.watchdog_max_rounds:
            self.ctx.run_context._run_state = (
                ApplicationRunContextStateEnum.STOP
            )
            return self.round_fail(f'看门狗:轮次超限 ({self.watchdog_max_rounds})')
        return super()._execute_one_round()


# --------------------------------------------------------------------------- #
# 运行态前置:is_context_stop 只读,直接写 _run_state。
# --------------------------------------------------------------------------- #


def enter_running_state(ctx: SrTestContext) -> None:
    """建立 op 执行前的运行态前置。

    ``test_context`` fixture 从不调 ``start_running()``,而 ``_run_state`` 默认
    STOP → ``is_context_stop=True`` → op 首轮即退出。``start_running()`` 本身要
    ``init_before_context_run()`` 返 True,``MockController`` 继承的默认实现返 False
    → ``start_running()`` 也会失败。故直接置 ``_run_state``。
    """
    ctx.run_context._run_state = ApplicationRunContextStateEnum.RUNNING  # noqa: SLF001


def reset_running_state(ctx: SrTestContext, op: object) -> None:
    """``finally`` 中复位运行态 + 清理 event_bus 监听。

    session 级 ``test_context`` 被复用:``_init_before_execute`` 在
    ``run_context.event_bus`` 上注册了 PAUSE/RESUME 监听,不清理会累积泄漏。
    """
    ctx.run_context._run_state = ApplicationRunContextStateEnum.STOP  # noqa: SLF001
    ctx.run_context.event_bus.unlisten_all_event(op)  # noqa: SLF001


# --------------------------------------------------------------------------- #
# 轮间等待 no-op:流程测试的时间加速器
# --------------------------------------------------------------------------- #


class _NoSleepTimeProxy:
    """``operation.py`` 模块级 ``time`` 引用的替身。

    只把 ``sleep`` 变成记录 no-op,其余属性(``time()`` / ``monotonic()`` 等)
    透传真模块 —— 轮次计时语义不变,只是不再真实等待。挂回 ``operation.time``
    时只影响 op 框架,不动全局 ``time`` 模块(线程同步等真实 sleep 不受影响)。
    """

    def __init__(self, real_module: ModuleType, skipped: list[float]) -> None:
        self._real_module: ModuleType = real_module
        self.skipped: list[float] = skipped

    def sleep(self, seconds: float) -> None:
        """记录被跳过的等待时长(诊断用),不真正睡眠。"""
        self.skipped.append(seconds)

    def __getattr__(self, name: str):
        return getattr(self._real_module, name)


@contextmanager
def fast_sleep() -> Iterator[list[float]]:
    """流程测试内把 op 框架的轮间/点击前等待变成 no-op 记录。

    背景:op 框架的 ``_after_round_wait`` / ``pre_delay`` 在真机上等待画面切换,
    是必要延迟;但 fixture 流程测试里 mock 画面在 click 后**瞬间**切换,这些
    sleep 纯属空等(2026-08-25 实测:单条流程测试 24s 中 ~21s 是 time.sleep,
    占全量套件 ~315s 中的 ~85s)。本上下文管理器把 ``operation.py`` 模块里的
    ``time`` 引用换成替身,``execute()`` 期间不再真实等待。

    用法::

        with fast_sleep():
            result = op.execute()

    Yields:
        被跳过的 sleep 时长列表(诊断/断言等待行为时可用)。
    """
    import one_dragon.base.operation.operation as operation_module

    skipped: list[float] = []
    real_time: ModuleType = operation_module.time
    operation_module.time = _NoSleepTimeProxy(real_time, skipped)  # type: ignore[assignment]
    try:
        yield skipped
    finally:
        operation_module.time = real_time  # type: ignore[assignment]


__all__ = [
    'FixtureController',
    'WatchdogOperationMixin',
    'enter_running_state',
    'reset_running_state',
    'fast_sleep',
]
