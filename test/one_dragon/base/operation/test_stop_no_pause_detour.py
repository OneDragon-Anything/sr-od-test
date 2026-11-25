"""stop 路径不借 pause toggle 单测(2026-08-23 两大归因误判根治)。

锁定三点:
① stop_running() 路径不产生「暂停运行」日志(caplog 断言,含 RUNNING 态 stop);
② RUNNING 态 stop 后 is_context_stop==True 且 last_run_result.stop_source 保留
   (叠加 test_stop_source_chain.py 的锁);
③ PAUSE 态下 stop_running 也直达 STOP(不再经过 RUNNING,不发 PAUSE 事件)。
"""
import logging
from unittest.mock import MagicMock

import pytest

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


@pytest.mark.parametrize('from_running,reason', [
    (True, 'mcp:stop_run'),   # RUNNING 态 stop
    (False, 'hook:x'),        # 非 RUNNING 态(初始 STOP)stop
], ids=['from-running', 'from-idle'])
def test_stop_no_pause_log(caplog, from_running: bool, reason: str):
    """① RUNNING / 非 RUNNING 两形态 stop 均不产生「暂停运行」日志。"""
    rc = _make_run_context()
    if from_running:
        _set_running(rc)
    with caplog.at_level(logging.INFO, logger='one_dragon.base.operation.application.application_run_context'):
        rc.stop_running(reason=reason)
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
    """③ PAUSE 态 stop 直达 STOP(无 RESUME 绕道):状态收尾 + stop_source 保留
    + 事件序列只发 STOP 不发 PAUSE + 不打暂停日志。"""
    rc = _make_run_context()
    rc._run_state = ApplicationRunContextStateEnum.PAUSE
    events: list[str] = []
    from one_dragon.base.operation.application.application_run_context import (
        ApplicationRunContextStateEventEnum,
    )
    rc.event_bus.listen_event(ApplicationRunContextStateEventEnum.PAUSE, lambda e: events.append('PAUSE'))
    rc.event_bus.listen_event(ApplicationRunContextStateEventEnum.STOP, lambda e: events.append('STOP'))
    with caplog.at_level(logging.INFO, logger='one_dragon.base.operation.application.application_run_context'):
        result = rc.stop_running(reason='gui:hotkey')
    assert rc.is_context_stop
    assert result.stop_source == 'gui:hotkey'
    assert events == ['STOP']
    assert '暂停运行' not in caplog.text
