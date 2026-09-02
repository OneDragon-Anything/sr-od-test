"""SrBackendContext.click_game() 的单元测试(独立仓)。"""

from unittest.mock import MagicMock

import pytest

from sr_od.backend.backend_context import BackendNotReadyError, SrBackendContext


@pytest.fixture
def mock_ctx_game_ready():
    """游戏就绪的 mock SrContext。"""
    ctx = MagicMock(name='SrContext')
    ctx.ready_for_application = True
    ctx.controller.is_game_window_ready = True
    ctx.controller.click.return_value = True
    return ctx


def test_click_game_delegates_to_controller(mock_ctx_game_ready):
    """click_game 应激活窗口并委托 controller.click(Point(x,y), press_time=...)。"""
    backend = SrBackendContext(mock_ctx_game_ready)
    result = backend.click_game(960, 540, press_time=0.5)
    mock_ctx_game_ready.controller.active_window.assert_called_once()
    call = mock_ctx_game_ready.controller.click.call_args
    # Point 无 __eq__(比 id),故比坐标字段而非 == Point(...)
    assert (call.args[0].x, call.args[0].y) == (960, 540)
    assert call.kwargs['press_time'] == 0.5
    assert call.kwargs['pc_alt'] is False
    assert result == {'success': True, 'x': 960, 'y': 540, 'in_window': True, 'pc_alt': False}


def test_click_game_out_of_window_returns_false(mock_ctx_game_ready):
    """controller.click 返 False(坐标不在窗口内)时 success/in_window=False。"""
    mock_ctx_game_ready.controller.click.return_value = False
    backend = SrBackendContext(mock_ctx_game_ready)
    result = backend.click_game(9999, 9999)
    assert result == {'success': False, 'x': 9999, 'y': 9999, 'in_window': False, 'pc_alt': False}


def test_click_game_window_not_ready_raises(mock_ctx_game_ready):
    """游戏窗口未就绪时 click_game 抛 BackendNotReadyError。"""
    mock_ctx_game_ready.controller.is_game_window_ready = False
    backend = SrBackendContext(mock_ctx_game_ready)
    with pytest.raises(BackendNotReadyError):
        backend.click_game(100, 100)


def test_click_game_default_press_time(mock_ctx_game_ready):
    """press_time 默认 0.1。"""
    backend = SrBackendContext(mock_ctx_game_ready)
    backend.click_game(10, 20)
    assert mock_ctx_game_ready.controller.click.call_args.kwargs['press_time'] == 0.1


def test_click_game_exempted_when_stop_latch_armed():
    """停机闩窗口内 click_game 放行不抛(ADR-0406 豁免机制的实证裁决)。

    裁决背景(2026-09-02 第二轮审计冲突):FastMCP 同步工具经 anyio to_thread
    在单一 worker 线程执行整个工具体,backend.click_game 内的
    ``with stop_guard_exemption():`` 与 controller 调用同线程——线程本地豁免
    令牌覆盖到位,守卫不抛。本测试用真 ControllerBase 子类 + 武装闩 + 独立
    worker 线程(模拟 anyio 线程池)复现该路径:
    ① 裸调 controller.click(无豁免)抛 StopRunInterrupted——证明闩是活的;
    ② 经 backend.click_game(豁免内)同线程放行返回成功——证明豁免覆盖;
    ③ 守卫异常是 BaseException,若豁免缺失会穿透工具层泛型兜底(另见
    test_mcp_app 的工具层按名收口测试)。
    """
    import threading

    from one_dragon.base.controller.controller_base import ControllerBase
    from one_dragon.base.controller.stop_guard import StopRunInterrupted
    from one_dragon.base.geometry.point import Point

    class _GuardedController(ControllerBase):
        """带守卫的记录型 controller(输入入口先查守卫,复刻 PcControllerBase)。"""

        def __init__(self) -> None:
            ControllerBase.__init__(self)
            self.clicked: list[tuple[int, int]] = []

        @property
        def is_game_window_ready(self) -> bool:
            return True

        def active_window(self) -> None:
            pass

        def click(self, pos: Point = None, press_time: float = 0, pc_alt: bool = False,
                  gamepad_key: str | None = None) -> bool:
            self._check_stop_guard()
            self.clicked.append((pos.x, pos.y))
            return True

    controller = _GuardedController()
    controller.stop_guard = lambda: True  # 闩窗口内(latch 武装)
    ctx = MagicMock(name='SrContext')
    ctx.ready_for_application = True
    ctx.controller = controller
    backend = SrBackendContext(ctx)

    result_box: dict = {}

    def _mcp_worker_thread():
        # 模拟 anyio to_thread 的 worker 线程:整个调用链在一个非主线程
        result_box['result'] = backend.click_game(960, 540)

    t = threading.Thread(target=_mcp_worker_thread)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), 'worker 线程不得因守卫异常卡死/死亡'

    # ② 豁免内放行:结构化成功返回,点击落地
    assert result_box['result'] == {'success': True, 'x': 960, 'y': 540,
                                    'in_window': True, 'pc_alt': False}
    assert controller.clicked == [(960, 540)]

    # ① 对照:同线程裸调(无豁免)确实被守卫拦——闩是活的,豁免才是放行原因
    with pytest.raises(StopRunInterrupted):
        controller.click(Point(1, 1))
