"""RunSlot 单跑道跨进程窗口占用拒绝测试(T-59)。

验收语义:
- 本槽空闲但游戏窗口被他进程驱动时,``_start`` 受理前即拒(ok=False),
  ``last_refusal_reason`` 带可归因的占用描述(区别于本进程已有 run 的历史拒绝);
- 释放后可再入:占用方释放后同一 ``_start`` 受理成功,拒绝原因清空;
- op 路径运行门兜底:start_running 失败时终态消息区分「窗口被他进程占用」
  与历史文案「有其它运行」;
- ``run_refusal_response`` 统一拒绝响应:error 优先取跨进程占用原因。

mock_ctx 是 MagicMock:``controller.game_win.win_title`` 非字符串 → 锁键回退
``DEFAULT_LOCK_KEY``(防御式推导),测试直接持同键锁即可模拟他进程占用;
锁目录由根 conftest 的 ``_isolate_window_run_mutex`` 重定向到 tmp。
"""

from unittest.mock import MagicMock

from one_dragon.base.operation import window_run_mutex
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.backend.backend_context import RunState, SrBackendContext


def _make_op(result=None):
    """构造 mock op factory(execute 立即返回 result);与 test_run_slot 同款。"""
    def factory(ctx):
        op = MagicMock(name='Operation')
        op.__class__ = type('OpenAndEnterGame', (), {})
        op.op_name = ''
        node = MagicMock()
        node.cn = '进入游戏'
        op._current_node = node
        op.node_retry_times = 0
        op.execute.return_value = result
        return op
    return factory


def _hold_default_key_lock():
    """持默认键锁(= mock ctx 推导出的键),模拟他进程占用游戏窗口。"""
    mutex = window_run_mutex.WindowRunMutex(
        window_run_mutex.default_lock_dir(),
        window_run_mutex.DEFAULT_LOCK_KEY,
        owner_source='他进程',
    )
    assert mutex.acquire() is True
    return mutex


def test_start_refused_when_window_held_by_other_process(slot) -> None:
    """窗口被他进程占用:_start 受理前拒绝,原因可归因(非笼统的已有运行)。"""
    external = _hold_default_key_lock()
    try:
        ok, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
        assert ok is False and fut is None
        reason = slot.last_refusal_reason
        assert reason is not None
        assert '游戏窗口被他进程占用' in reason
        assert 'pid=' in reason                           # 占用者可归因
    finally:
        external.release()


def test_start_accepted_after_holder_releases(slot) -> None:
    """释放后可再入:占用方释放后同一 _start 受理成功,拒绝原因清空。"""
    external = _hold_default_key_lock()
    external.release()

    ok, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
    assert ok is True and fut is not None
    fut.result(timeout=5)
    assert slot.last_refusal_reason is None


def test_op_path_status_names_window_occupancy(slot, mock_ctx) -> None:
    """运行门兜底:start_running 失败时终态按占用原因落 FAILED 消息。"""
    mock_ctx.run_context.start_running.return_value = False
    mock_ctx.run_context.window_mutex_blocker = 'pid=42, 来源=他进程'

    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status is not None
    assert '游戏窗口被他进程占用' in slot.last_status

    # 无占用描述时保持历史文案(如进程内其它运行导致)。
    mock_ctx.run_context.window_mutex_blocker = None
    _, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
    fut.result(timeout=5)
    assert slot.last_status == 'start_running 失败(有其它运行)'


def test_app_path_not_started_names_window_occupancy(slot, mock_ctx) -> None:
    """app 路径:NOT_STARTED 且存在占用描述时,状态透出占用原因。"""
    from one_dragon.base.operation.application.application_run_context import (
        ApplicationRunResult,
        RunFinishReason,
    )

    mock_ctx.run_context.run_application.return_value = ApplicationRunResult(
        finish_reason=RunFinishReason.NOT_STARTED,
        app_id='currency_war', instance_idx=0, group_id=None,
    )
    mock_ctx.run_context.window_mutex_blocker = 'pid=42, 来源=他进程'
    mock_ctx.run_context.get_application_name.return_value = '货币战争'

    _, fut = slot._start('mcp', app_id='currency_war')
    fut.result(timeout=5)
    assert slot.terminal_state == RunState.FAILED
    assert slot.last_status is not None
    assert '游戏窗口被他进程占用' in slot.last_status


def test_run_refusal_response_prefers_occupancy_reason(slot, mock_ctx) -> None:
    """统一拒绝响应:跨进程占用原因优先;无占用原因回退历史文案。"""
    backend = SrBackendContext(mock_ctx)
    backend.run_slot = slot

    slot.last_refusal_reason = '游戏窗口被他进程占用(pid=42)'
    resp = backend.run_refusal_response('提示语')
    assert resp == {
        'started': False,
        'error': '游戏窗口被他进程占用(pid=42)',
        'source': slot.source,
        'hint': '提示语',
    }

    slot.last_refusal_reason = None
    resp = backend.run_refusal_response('提示语')
    assert resp['error'] == '已有运行在进行中'


def test_probe_refusal_does_not_start_run(slot, mock_ctx) -> None:
    """拒绝路径零副作用:被拒后槽保持空闲,不进运行线程、不触运行门。"""
    external = _hold_default_key_lock()
    try:
        ok, fut = slot._start('mcp', op_factory=_make_op(OperationResult(success=True)))
        assert ok is False and fut is None
        assert slot.future is None                        # 未受理:无 future
        assert not mock_ctx.run_context.start_running.called  # 未触运行门
    finally:
        external.release()
