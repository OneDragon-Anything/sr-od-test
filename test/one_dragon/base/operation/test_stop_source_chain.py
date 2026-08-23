"""stop 原因贯通链单测(「人工结束」误标根治)。

锁定三点:
① stop_running(reason='x') 后 last_run_result.stop_source == 'x';
② 幂等二次调用不覆盖首 reason(返回首结果);
③ operation 停止出口文案带来源(「已停止[来源]」)。
"""
from unittest.mock import MagicMock

from one_dragon.base.operation.application.application_run_context import (
    ApplicationRunContext,
    RunFinishReason,
)
from one_dragon.base.operation.operation import Operation


def _make_run_context() -> ApplicationRunContext:
    """构造真实 ApplicationRunContext(ctx 为 mock;stop 路径不触控制器)。"""
    return ApplicationRunContext(MagicMock(name='OneDragonContext'))


def test_stop_running_records_reason():
    """① stop_running 的 reason 写入结果 stop_source。"""
    rc = _make_run_context()
    result = rc.stop_running(reason='mcp:stop_run')
    assert result.finish_reason == RunFinishReason.STOPPED
    assert result.stop_source == 'mcp:stop_run'
    assert rc.last_run_result is result
    assert rc.last_run_result.stop_source == 'mcp:stop_run'


def test_stop_running_idempotent_keeps_first_reason():
    """② 已停止时二次 stop_running 返回首结果,不覆盖首 reason。"""
    rc = _make_run_context()
    first = rc.stop_running(reason='hook:summon_unknown')
    second = rc.stop_running(reason='mcp:stop_run')
    assert second is first
    assert rc.last_run_result.stop_source == 'hook:summon_unknown'


def test_operation_stop_exit_message_contains_source():
    """③ operation 停止出口文案含来源。"""
    rc = _make_run_context()
    rc.stop_running(reason='hook:shop_unknown_card')
    ctx = MagicMock(name='OneDragonContext')
    ctx.run_context = rc
    op = Operation(ctx)
    # 跳过节点网络/事件初始化(本测试只验证停止出口分支)
    op._init_before_execute = lambda: None  # type: ignore[method-assign]
    result = op.execute()
    assert not result.success
    assert result.status.startswith('已停止')
    assert '[hook:shop_unknown_card]' in result.status


def test_operation_stop_exit_message_unknown_when_no_reason():
    """③-补充:无来源停止时出口文案回退 'unknown'(不再是「人工结束」)。"""
    rc = _make_run_context()
    rc.stop_running()
    ctx = MagicMock(name='OneDragonContext')
    ctx.run_context = rc
    op = Operation(ctx)
    op._init_before_execute = lambda: None  # type: ignore[method-assign]
    result = op.execute()
    assert result.status == '已停止[unknown]'
