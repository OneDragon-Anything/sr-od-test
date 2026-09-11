"""ApplicationRunContext 跨进程窗口互斥运行门测试。

验收语义(T-59):
- start_running 在进程内单跑道检查通过后真实取得窗口锁;他进程(测试里用
  同键的第二个锁实例模拟,Windows 字节锁按句柄冲突)持锁时拒绝启动,并经
  ``window_mutex_blocker`` 透出占用者描述;
- 收口(_finish_running,覆盖 finish_running 与 stop_running 两条路径)释放锁,
  释放后可再入;
- 锁不跨失败泄漏:控制器初始化失败 / 初始化抛异常都先还锁。

stub ctx 只需 ``controller.game_win.win_title`` 与 ``init_before_context_run``
(运行门不触碰 ctx 其余部分);锁目录由根 conftest 的
``_isolate_window_run_mutex`` 重定向到 tmp。
"""

import pytest

from one_dragon.base.operation import window_run_mutex
from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
)


class _StubGameWin:
    def __init__(self) -> None:
        self.win_title: str = '测试窗口:A'


class _StubController:
    def __init__(self, init_result: bool = True, raises: Exception | None = None) -> None:
        self.game_win: _StubGameWin = _StubGameWin()
        self._init_result: bool = init_result
        self._raises: Exception | None = raises

    def init_before_context_run(self) -> bool:
        if self._raises is not None:
            raise self._raises
        return self._init_result


class _StubCtx:
    def __init__(self, controller: _StubController) -> None:
        self.controller: _StubController = controller


def _external_mutex(rc: ApplicationRunContext) -> window_run_mutex.WindowRunMutex:
    """构造与运行门同键的他方锁实例(模拟另一进程持锁)。"""
    return window_run_mutex.WindowRunMutex(
        window_run_mutex.default_lock_dir(),
        window_run_mutex.resolve_lock_key(rc.ctx.controller),
        owner_source='他进程',
    )


def test_start_acquires_lock_and_finish_releases() -> None:
    """运行持锁(他方句柄取不到)、收口释放(释放后他方可取)。"""
    rc = ApplicationRunContext(_StubCtx(_StubController()))

    assert rc.start_running() is True
    assert _external_mutex(rc).acquire() is False         # 运行中:窗口被本运行锁住

    rc.finish_running()
    assert rc.window_mutex_blocker is None
    assert _external_mutex(rc).acquire() is True          # 收口后:锁已释放
    _external_mutex(rc).release()


def test_start_refused_when_window_held_elsewhere() -> None:
    """他进程持锁时拒绝启动(缺省拒绝,不排队)并透出占用描述。"""
    rc = ApplicationRunContext(_StubCtx(_StubController()))
    external = _external_mutex(rc)
    assert external.acquire() is True
    try:
        assert rc.start_running() is False
        blocker = rc.window_mutex_blocker
        assert blocker is not None
        assert 'pid=' in blocker                          # 占用者可归因
        assert _external_mutex(rc).acquire() is False     # 未偷取他方锁
    finally:
        external.release()

    # 他方释放后可再入(第二实例拒绝 + 释放后可再入 的运行门侧验收)。
    assert rc.start_running() is True
    rc.finish_running()


def test_init_failure_releases_lock() -> None:
    """控制器初始化失败:拒绝启动且不持锁泄漏(他方可取)。"""
    rc = ApplicationRunContext(_StubCtx(_StubController(init_result=False)))

    assert rc.start_running() is False
    assert rc.window_mutex_blocker is None                # 非占用类失败不写占用描述
    external = _external_mutex(rc)
    assert external.acquire() is True
    external.release()


def test_init_exception_releases_lock_and_propagates() -> None:
    """取锁后初始化抛异常:先还锁再上抛(锁不悬到进程退出)。"""
    boom = RuntimeError('init 爆炸')
    rc = ApplicationRunContext(_StubCtx(_StubController(raises=boom)))

    with pytest.raises(RuntimeError):
        rc.start_running()
    external = _external_mutex(rc)
    assert external.acquire() is True
    external.release()


def test_stop_running_releases_lock() -> None:
    """停止路径收口(stop_running → _finish_running)同样释放窗口锁。"""
    rc = ApplicationRunContext(_StubCtx(_StubController()))
    assert rc.start_running() is True

    rc.stop_running(reason='测试停止')
    assert _external_mutex(rc).acquire() is True          # 停止后:锁已释放
    _external_mutex(rc).release()
