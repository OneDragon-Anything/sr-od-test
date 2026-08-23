"""stop 路径不借 pause toggle 单测(2026-08-23 两大归因误判根治)。

锁定三点:
① stop_running() 路径不产生「暂停运行」日志(caplog 断言,含 RUNNING 态 stop);
② RUNNING 态 stop 后 is_context_stop==True 且 last_run_result.stop_source 保留
   (叠加 test_stop_source_chain.py 的锁);
③ PAUSE 态下 stop_running 也直达 STOP(不再经过 RUNNING,不发 PAUSE 事件)。
"""
import logging
from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
    ApplicationRunContextStateEnum,
    RunFinishReason,
)


def _make_run_context() -> ApplicationRunContext:
    """构造真实 ApplicationRunContext(ctx 为 mock;stop 路径不触控制器)。"""
    return ApplicationRunContext(MagicMock(name='OneDragonContext'))


def _set_running(rc: ApplicationRunContext) -> None:
    """直接置 RUNNING 态(绕过 start_running 的控制器初始化)。"""
    rc._run_state = ApplicationRunContextStateEnum.RUNNING


def test_stop_from_running_no_pause_log(caplog):
    """① RUNNING 态 stop 不产生「暂停运行」日志。"""
    rc = _make_run_context()
    _set_running(rc)
    with caplog.at_level(logging.INFO, logger='one_dragon.base.operation.application.application_run_context'):
        rc.stop_running(reason='mcp:stop_run')
    assert '暂停运行' not in caplog.text


def test_stop_from_idle_no_pause_log(caplog):
    """①-补充:非 RUNNING 态(初始 STOP)stop 同样不打暂停日志。"""
    rc = _make_run_context()
    with caplog.at_level(logging.INFO, logger='one_dragon.base.operation.application.application_run_context'):
        rc.stop_running(reason='hook:x')
    assert '暂停运行' not in caplog.text


def test_stop_from_running_reaches_stop_and_keeps_source():
    """② RUNNING→stop 后 is_context_stop 且 stop_source 保留。"""
    rc = _make_run_context()
    _set_running(rc)
    result = rc.stop_running(reason='mcp:stop_run')
    assert rc.is_context_stop
    assert rc.last_run_result is result
    assert result.finish_reason == RunFinishReason.STOPPED
    assert result.stop_source == 'mcp:stop_run'


def test_stop_from_pause_reaches_stop_directly(caplog):
    """③ PAUSE 态下 stop 直达 STOP(无 RESUME 绕道,无暂停日志)。"""
    rc = _make_run_context()
    rc._run_state = ApplicationRunContextStateEnum.PAUSE
    with caplog.at_level(logging.INFO, logger='one_dragon.base.operation.application.application_run_context'):
        result = rc.stop_running(reason='gui:hotkey')
    assert rc.is_context_stop
    assert result.stop_source == 'gui:hotkey'
    assert '暂停运行' not in caplog.text


def test_stop_does_not_dispatch_pause_event():
    """③-补充:stop 路径只发 STOP 事件,不发 PAUSE 事件(事件序列锁)。"""
    rc = _make_run_context()
    _set_running(rc)
    events: list[str] = []
    from one_dragon.base.operation.application.application_run_context import (
        ApplicationRunContextStateEventEnum,
    )
    rc.event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE, lambda e: events.append('PAUSE'))
    rc.event_bus.listen_event(ApplicationRunContextStateEventEnum.STOP, lambda e: events.append('STOP'))
    rc.stop_running(reason='mcp:stop_run')
    assert events == ['STOP']
