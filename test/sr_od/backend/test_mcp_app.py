"""MCP 适配器的单元测试。

测试使用 MagicMock 伪造 backend，避免依赖真实游戏窗口与 SrContext。

包含两类用例（互补）：
- ``_mcp_with_backend`` + 直接 await/调用 ``Tool.fn``：覆盖 check/capture/analyze
  + close_game 工具的注册与行为（来自 understand-game 主仓归一）。
- ``_mock_backend`` + ``app_mod.make_*`` 工厂：覆盖 open_game/get_run_status
  /stop_run 的委托与 block/nonblock/失败分支（来自 backend/run-status-schema）。
"""

import asyncio
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.backend.backend_context import BackendNotReadyError, SrBackendContext
from sr_od.backend.mcp import app as app_mod
from sr_od.backend.mcp.app import create_mcp_server
from sr_od.backend.schemas import AnalyzeScreenResult, RunStatusResult


def _mcp_with_backend() -> tuple[object, MagicMock]:
    """构造一个 MCP 服务器与对应的伪造 backend。

    Returns:
        ``(mcp, backend)`` 元组：mcp 为注册了全部 game 工具的 FastMCP 实例
        （check/capture/analyze + close_game/click_game/input_text
        + open_game/get_run_status/stop_run），
        backend 为 MagicMock，可在测试中配置其方法返回值或副作用。
    """
    backend = MagicMock()
    mcp = create_mcp_server(backend)
    return mcp, backend


def _mock_backend(start_ok: bool = True) -> MagicMock:
    """构造一个 mock SrBackendContext,start_run 返回 (start_ok, Future)。"""
    b = MagicMock(name='SrBackendContext')
    b.start_run.return_value = (start_ok, Future())
    b.query_status.return_value = RunStatusResult(
        state='running',
        source='mcp',
        app='OpenAndEnterGame',
        started_at='2026-07-02T00:00:00',
        duration_seconds=1.0,
    )
    b.stop.return_value = {'stopped': False, 'error': '当前无运行'}
    # 并发拒绝响应由 backend 统一助手产出(start 类工具只透传):
    # 绑真实现——方法只读 query_status / run_slot,二者均已被 mock。
    b.run_refusal_response = lambda hint: SrBackendContext.run_refusal_response(b, hint)
    return b


# ===== check/capture/analyze/close_game 工具注册与行为 =====

def test_registers_all_tools() -> None:
    """create_mcp_server 应注册全部 game 工具(open_game 替换 open_and_enter_game + 新增 click/input)。"""
    mcp, _ = _mcp_with_backend()
    names = set(mcp._tool_manager._tools.keys())
    assert {
        "check_game_window",
        "capture_game_screen",
        "analyze_screen",
        "open_game",
        "close_game",
        "click_game",
        "input_text",
        "get_run_status",
        "stop_run",
    } <= names


def test_check_game_window_tool_error_on_not_ready() -> None:
    """check_game_window 在 backend 未就绪时返回带 error 的 dict(工具层兜底)。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["check_game_window"]
    # FastMCP 工具实际可调用对象在 .fn / .func；按版本取能 call 的那个
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    out = fn()
    assert isinstance(out, dict)
    assert "未就绪" in out["error"]


def test_analyze_tool_returns_result() -> None:
    """analyze_screen 应直接返回 backend.analyze() 的结果。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(success=True, ocr_texts=[], error=None)
    tool = mcp._tool_manager._tools["analyze_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    result = fn()
    assert result.success is True


def test_tool_annotations_marked() -> None:
    """观察类 tool 标 read_only、破坏性 tool 标 destructive(P3 副作用机器可读标注)。"""
    mcp, _ = _mcp_with_backend()
    tools = mcp._tool_manager._tools
    # 观察类(只读)
    assert tools["check_game_window"].annotations.readOnlyHint is True
    assert tools["analyze_screen"].annotations.readOnlyHint is True
    assert tools["get_run_status"].annotations.readOnlyHint is True
    assert tools["list_applications"].annotations.readOnlyHint is True
    # 破坏性(不可逆)
    assert tools["close_game"].annotations.destructiveHint is True
    assert tools["delete_screen_area"].annotations.destructiveHint is True
    # 操作类(非破坏)不标 read_only
    click_ann = tools["click_game"].annotations
    assert click_ann is None or click_ann.readOnlyHint is None


def test_close_game_tool_error_on_not_ready() -> None:
    """close_game 在 backend 未就绪时返回 {success: False, error}(工具层兜底)。"""
    mcp, backend = _mcp_with_backend()
    backend.close_game.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["close_game"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    out = fn()
    assert out['success'] is False
    assert '未就绪' in out['error']


def test_capture_game_screen_returns_path(tmp_path, monkeypatch) -> None:
    """capture_game_screen 应保存截图并返回 {success, path}。"""
    import numpy as np

    # 写盘目录重定向 tmp_path(纪律 2:测试禁写真实 .debug/)
    monkeypatch.setattr(
        'sr_od.backend.backend_context.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )

    mcp, backend = _mcp_with_backend()
    backend.capture.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    tool = mcp._tool_manager._tools["capture_game_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    out = fn()
    assert out['success'] is True
    assert out['path'].endswith(".png")


# ===== open_game 工厂委托(enter 选 op)+ get_run_status/stop_run =====

def test_open_game_nonblock_returns_started() -> None:
    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=False))
    assert res['started'] is True
    backend.start_run.assert_called_once()


def test_open_game_concurrent_reject() -> None:
    backend = _mock_backend(start_ok=False)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=False))
    assert res['started'] is False and 'source' in res


@pytest.mark.parametrize('enter, expect_msg', [
    (True, '成功打开并进入星穹铁道游戏'),
    (False, '成功打开游戏(未登录)'),
], ids=['enter', 'open-only'])
def test_open_game_block_success(enter: bool, expect_msg: str) -> None:
    """block=True + 成功 future → 按 enter 分支返回对应成功文案。"""
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='成功'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=enter, block=True))
    assert res == {'success': True, 'result': expect_msg}


def test_open_game_block_failed() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=False, status='打开游戏失败'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=True))
    assert res == {'success': False, 'result': '打开游戏失败: 打开游戏失败'}


def test_open_game_enter_flag_selects_op() -> None:
    """enter 开关决定 op_factory 构造的 op:False→OpenGame,True→OpenAndEnterGame。"""
    from unittest.mock import MagicMock

    from sr_od.operations.enter_game.open_and_enter_game import OpenAndEnterGame
    from sr_od.operations.enter_game.open_game import OpenGame

    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    asyncio.run(tool(enter=False, block=False))
    op_factory = backend.start_run.call_args[0][1]
    assert isinstance(op_factory(MagicMock(name='SrContext')), OpenGame)

    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    asyncio.run(tool(enter=True, block=False))
    op_factory = backend.start_run.call_args[0][1]
    assert isinstance(op_factory(MagicMock(name='SrContext')), OpenAndEnterGame)


def test_get_run_status_delegates() -> None:
    backend = _mock_backend()
    res = app_mod.make_get_run_status(backend)()
    assert isinstance(res, RunStatusResult)
    backend.query_status.assert_called_once()


def test_stop_run_delegates() -> None:
    backend = _mock_backend()
    res = app_mod.make_stop_run(backend)()
    assert res['stopped'] is False
    backend.stop.assert_called_once()


# ===== click_game / input_text 工具(内联注册,同 close_game) =====

def test_click_game_tool_delegates() -> None:
    """click_game tool 直调 backend.click_game(),默认 press_time=0.1/pc_alt=False,并原样返回。"""
    mcp, backend = _mcp_with_backend()
    backend.click_game.return_value = {'success': True, 'x': 960, 'y': 540, 'in_window': True, 'pc_alt': False}
    tool = mcp._tool_manager._tools['click_game']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(x=960, y=540)
    backend.click_game.assert_called_once_with(960, 540, 0.1, False)
    assert result['success'] is True


def test_input_tools_collect_stop_interrupted_as_structured_error() -> None:
    """停机守卫异常(BaseException)在工具层按名收尾为结构化错误,不外抛。

    裁决背景(2026-09-02 第二轮审计冲突):ServerErrorMiddleware/FastMCP 泛型
    兜底只接 Exception,BaseException 穿透会变成 ASGI 层错误 + 连接断,客户端
    拿不到结构化错误。正常路径手动端点已在 backend 层豁免不应到达此处;本
    兜底是防御纵深(未来端点忘豁免时客户端仍拿到可读错误)。锁全部输入族
    工具:click_game/key_tap/drag/input_text/goto_screen/close_game。
    """
    from one_dragon.base.controller.stop_guard import StopRunInterrupted

    mcp, backend = _mcp_with_backend()
    for name, invoke in (
        ('click_game', lambda fn: fn(x=1, y=2)),
        ('key_tap', lambda fn: fn(key='esc')),
        ('drag', lambda fn: fn(x1=1, y1=2, x2=3, y2=4)),
        ('input_text', lambda fn: fn(text='abc')),
        ('goto_screen', lambda fn: fn(target_screen_name='邮件')),
        ('close_game', lambda fn: fn()),
    ):
        backend_method = getattr(backend, name)
        backend_method.side_effect = StopRunInterrupted('停机')
        tool = mcp._tool_manager._tools[name]
        fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
        result = invoke(fn)  # 不抛即过:按名收尾为结构化错误
        assert result['success'] is False, f'{name} 应返回失败结构'
        assert '停机中断' in result['error'], f'{name} 错误文案应指明停机中断,实得 {result["error"]}'
        backend_method.side_effect = None


def test_input_text_tool_delegates() -> None:
    """input_text tool 直调 backend.input_text() 并原样返回。"""
    mcp, backend = _mcp_with_backend()
    backend.input_text.return_value = {'success': True, 'method': 'clipboard', 'masked_text': '***'}
    tool = mcp._tool_manager._tools['input_text']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(text='abc', use_clipboard=True)
    backend.input_text.assert_called_once_with('abc', True)
    assert result['method'] == 'clipboard'


def test_analyze_screen_tool_passes_save_image() -> None:
    """analyze_screen tool 应把 save_image/include_ocr 透传给 backend.analyze,并回带 screenshot_path。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(
        success=True, ocr_texts=[], error=None, screenshot_path='/tmp/x.png')
    tool = mcp._tool_manager._tools['analyze_screen']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(save_image=True)
    backend.analyze.assert_called_once_with(None, True, False)
    assert result.screenshot_path == '/tmp/x.png'


# ===== list_operations / describe_operation / run_operation(自定义 operation 入口)=====

_OPEN_AND_ENTER = 'sr_od.operations.enter_game.open_and_enter_game.OpenAndEnterGame'
# 带必填参数的 SR op fixture(替换原 ZZZ MapTransport——SR 侧无等价 op,旧测试长期 skip 死占位)
_GET_RID_OF_STUCK = 'sr_od.operations.move.get_rid_of_stuck.GetRidOfStuck'
_CHARGE_PLAN_ITEM = 'sr_od.application.charge_plan.charge_plan_config.ChargePlanItem'


def test_registers_operation_tools() -> None:
    """create_mcp_server 应注册 list_operations/describe_operation/run_operation。"""
    mcp, _ = _mcp_with_backend()
    names = set(mcp._tool_manager._tools.keys())
    assert {'list_operations', 'describe_operation', 'run_operation'} <= names


def test_list_operations_contains_open_and_enter_game() -> None:
    """list_operations 定位符形态应含 OpenAndEnterGame(无同名类 → 短名)。"""
    from sr_od.backend.mcp.service_app import make_list_operations

    backend = MagicMock()
    result = make_list_operations(backend)()
    assert 'OpenAndEnterGame' in result['operations']
    assert result['total'] == result['count'] == len(result['operations'])
    # 元素唯一:短名或完整 op_id 均可直接传 describe/run,不得重复
    assert len(set(result['operations'])) == len(result['operations'])


def test_list_operations_query_filter() -> None:
    """query 子串过滤(按完整 op_id 匹配);无命中返回空列表且 total 仍为全量数。"""
    from sr_od.backend.mcp.service_app import make_list_operations

    backend = MagicMock()
    result = make_list_operations(backend)('openandenter')  # 小写过滤大写类名
    assert result['count'] == 1
    assert result['operations'] == ['OpenAndEnterGame']
    assert result['total'] > result['count']

    miss = make_list_operations(backend)('不存在的关键字xyz')
    assert miss['count'] == 0
    assert miss['operations'] == []
    assert miss['total'] > 0


def test_list_operations_error_fallback() -> None:
    """scan_operations 抛异常时 list_operations 返回 {error}(工具层兜底)。"""
    from sr_od.backend import operation_registry
    from sr_od.backend.mcp.service_app import make_list_operations

    backend = MagicMock()
    original = operation_registry.scan_operations

    def _boom(_ctx, refresh: bool = False):  # noqa: ANN202
        raise RuntimeError('扫描失败')

    operation_registry.scan_operations = _boom
    try:
        res = make_list_operations(backend)()
    finally:
        operation_registry.scan_operations = original
    assert isinstance(res, dict) and 'error' in res


def test_describe_operation_delegates() -> None:
    """describe_operation 纯反射参数 schema(op_id 走参数,已剔除 self/ctx)。"""
    from sr_od.backend.mcp.service_app import make_describe_operation

    backend = MagicMock()
    info = make_describe_operation(backend)(_GET_RID_OF_STUCK)
    assert info['op_id'] == _GET_RID_OF_STUCK
    assert info['class_name'] == 'GetRidOfStuck'
    param_names = [p['name'] for p in info['params']]
    assert param_names == ['stuck_times']


def test_describe_operation_error_on_bad_op() -> None:
    """describe_operation 非 Operation → {error}(异常兜底)。"""
    from sr_od.backend.mcp.service_app import make_describe_operation

    backend = MagicMock()
    info = make_describe_operation(backend)(_CHARGE_PLAN_ITEM)
    assert isinstance(info, dict) and 'error' in info


def test_describe_operation_accepts_short_name() -> None:
    """describe_operation 支持类名短名(唯一命中)→ 返回完整 op_id 的 schema。"""
    from sr_od.backend.mcp.service_app import make_describe_operation

    backend = MagicMock()
    info = make_describe_operation(backend)('GetRidOfStuck')
    assert info['op_id'] == _GET_RID_OF_STUCK
    assert info['class_name'] == 'GetRidOfStuck'


def test_run_operation_runs_via_slot() -> None:
    """合法 op_id + 空 args → run_slot._start 被调(op_factory 路径),started=True。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (True, Future())
    backend.query_status.return_value = RunStatusResult(
        state='running', source='mcp', started_at='2026-07-02T00:00:00', duration_seconds=1.0)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, args={}, block=False))
    assert res['started'] is True
    backend.run_slot._start.assert_called_once()
    call = backend.run_slot._start.call_args
    assert call.args[0] == 'mcp'                                   # source
    op_factory = call.kwargs.get('op_factory') or call.args[1]
    assert callable(op_factory)
    assert call.kwargs.get('display_name') == _OPEN_AND_ENTER      # op_id 作定位标识


def test_run_operation_rejects_non_operation() -> None:
    """op_id 解析出非 Operation(resolve_op_class raise)→ {started: False, error},不调 _start。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    res = asyncio.run(make_run_operation(backend)(op_id=_CHARGE_PLAN_ITEM, block=False))
    assert res['started'] is False and 'error' in res
    backend.run_slot._start.assert_not_called()


def test_run_operation_rejects_missing_required() -> None:
    """缺必填参数(validate_args 返错)→ {started: False, error},不调 _start。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    res = asyncio.run(make_run_operation(backend)(
        op_id=_GET_RID_OF_STUCK, args={}, block=False))
    assert res['started'] is False
    assert 'stuck_times' in res['error']
    backend.run_slot._start.assert_not_called()


def test_run_operation_concurrent_reject() -> None:
    """单跑道已有运行 → run_slot._start 返 (False, None) → {started: False, source}。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (False, None)
    backend.query_status.return_value = RunStatusResult(state='running', source='http')
    # 并发拒绝响应由 backend 统一助手产出,绑真实现(依赖均已被 mock)。
    backend.run_refusal_response = lambda hint: SrBackendContext.run_refusal_response(backend, hint)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, block=False))
    assert res['started'] is False
    assert res['error'] == '已有运行在进行中'
    assert res['source'] == 'http'


def test_run_operation_block_success() -> None:
    """block=True + 成功结果 → 返回 {success: True, result} 终态 dict。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='ok'))
    backend = MagicMock()
    backend.run_slot._start.return_value = (True, fut)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, args={}, block=True))
    assert res['success'] is True and '成功' in res['result']


def test_run_operation_bakes_args_into_factory() -> None:
    """op_factory 闭包 bake 了 args:展开后等价 cls(ctx, stuck_times=...)。"""
    from unittest.mock import MagicMock

    from sr_od.backend.mcp.service_app import make_run_operation
    from sr_od.operations.move.get_rid_of_stuck import GetRidOfStuck

    backend = MagicMock()
    backend.run_slot._start.return_value = (True, Future())
    backend.query_status.return_value = RunStatusResult(state='running', source='mcp')
    asyncio.run(make_run_operation(backend)(
        op_id=_GET_RID_OF_STUCK, args={'stuck_times': 3}, block=False))
    call = backend.run_slot._start.call_args
    op_factory = call.kwargs.get('op_factory') or call.args[1]
    op = op_factory(MagicMock(name='SrContext'))
    assert isinstance(op, GetRidOfStuck)
    assert op.stuck_times == 3


def test_run_operation_accepts_short_name() -> None:
    """run_operation 支持类名短名(唯一命中)→ 正常启动,display_name 用完整 op_id。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (True, Future())
    backend.query_status.return_value = RunStatusResult(
        state='running', source='mcp', started_at='2026-07-02T00:00:00', duration_seconds=1.0)
    res = asyncio.run(make_run_operation(backend)(
        op_id='OpenAndEnterGame', args={}, block=False))
    assert res['started'] is True
    assert backend.run_slot._start.call_args.kwargs.get('display_name') == _OPEN_AND_ENTER
