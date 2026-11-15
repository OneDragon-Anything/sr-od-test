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
from sr_od.backend.schemas import (
    AnalyzeScreenResult,
    RunFinishOut,
    RunStartOut,
    RunStatusOut,
    RunStatusResult,
    RunStopOut,
    RunStopResult,
)


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
    b.stop.return_value = RunStopResult(stopped=False, source=None)
    # 并发拒绝由 backend 统一助手产出(start 类工具只透传):
    # 绑真实现——方法只读 query_status / run_slot,二者均已被 mock。
    b.run_refusal_response = lambda hint: SrBackendContext.run_refusal_response(b, hint)
    b.run_refusal_error = lambda hint: SrBackendContext.run_refusal_error(b, hint)
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


def test_check_game_window_raises_on_not_ready() -> None:
    """check_game_window 在 backend 未就绪时异常透传(失败走错误通道,不做兜底包装)。"""
    mcp, backend = _mcp_with_backend()
    backend.check_window.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["check_game_window"]
    # FastMCP 工具实际可调用对象在 .fn / .func；按版本取能 call 的那个
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    with pytest.raises(BackendNotReadyError, match="未就绪"):
        fn()


def test_check_game_window_tool_error_via_call_tool() -> None:
    """序列化层冒烟:backend 异常穿透到 FastMCP.call_tool 变 ToolError,原始文案保留。

    H1 同构教训(函数层测试绕过序列化层漏网):本测试锁「工具层不吞异常,
    文案到达 sdk 边界」。lowlevel 层再把 ToolError 包装为
    CallToolResult(isError=True)(sdk 固定行为,源码确认:lowlevel/server.py
    call_tool handler 的 except Exception 分支),连接不断。
    """
    from mcp.server.fastmcp.exceptions import ToolError

    mcp, backend = _mcp_with_backend()
    backend.check_window.side_effect = BackendNotReadyError('未就绪')
    with pytest.raises(ToolError, match='未就绪'):
        asyncio.run(mcp.call_tool('check_game_window', {}))


def test_analyze_tool_converts_to_output_model() -> None:
    """analyze_screen 应把 backend 结果转成 AnalyzeScreenOut(异常透传,不做兜底包装)。"""
    from one_dragon.base.screen.screen_match import AreaMatchDetail, ScreenMatch
    from sr_od.backend.schemas import AnalyzeScreenOut

    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(
        ocr_texts=[], screenshot_path='/tmp/x.png',
        screens=[ScreenMatch(screen_name='菜单', is_precise=True, areas=[
            AreaMatchDetail(area_name='标题', pc_rect=[1, 1, 2, 2],
                            matched_text='菜单', match_target='菜单'),
        ])])
    tool = mcp._tool_manager._tools["analyze_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    result = fn()
    assert isinstance(result, AnalyzeScreenOut)
    assert result.screenshot_path == '/tmp/x.png'
    # 嵌套转换:dataclass → Out 模型,字段逐值等价
    assert result.screens[0].screen_name == '菜单'
    assert result.screens[0].areas[0].match_target == '菜单'


def test_check_game_window_converts_to_output_model() -> None:
    """check_game_window 成功分支转 WindowStatusOut(字段语义走 outputSchema)。"""
    from sr_od.backend.schemas import WindowStatus, WindowStatusOut

    mcp, backend = _mcp_with_backend()
    backend.check_window.return_value = WindowStatus(
        win_title='崩坏:星穹铁道', is_win_valid=True, is_win_active=True,
        is_win_scale=False, x=0, y=0, width=1920, height=1080)
    tool = mcp._tool_manager._tools['check_game_window']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn()
    assert isinstance(result, WindowStatusOut)
    assert result.is_win_valid is True


def test_list_applications_converts_to_output_model() -> None:
    """list_applications 成功分支转 ApplicationListResultOut(嵌套 applications 同步转换)。"""
    from sr_od.backend.schemas import (
        ApplicationInfo,
        ApplicationListResult,
        ApplicationListResultOut,
    )

    mcp, backend = _mcp_with_backend()
    backend.list_applications.return_value = ApplicationListResult(
        current_instance_idx=1, active_standalone_app_id=None,
        applications=[ApplicationInfo(app_id='x', app_name='X')])
    tool = mcp._tool_manager._tools['list_applications']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn()
    assert isinstance(result, ApplicationListResultOut)
    assert result.current_instance_idx == 1
    assert result.applications[0].app_id == 'x'


def test_list_screen_names_converts_to_output_model() -> None:
    """list_screen_names 成功分支转 ScreenNamesOut(画面名语义走 outputSchema)。"""
    from sr_od.backend.schemas import ScreenNamesOut

    mcp, backend = _mcp_with_backend()
    backend.list_screen_names.return_value = ['主界面', '邮件']
    tool = mcp._tool_manager._tools['list_screen_names']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn()
    assert isinstance(result, ScreenNamesOut)
    assert result.screen_names == ['主界面', '邮件']


def test_screen_crud_tools_convert_and_raise() -> None:
    """建档 CRUD 三工具:成功转 Out 模型,校验失败透传 ScreenInfoError(不做兜底包装)。"""
    from sr_od.backend.backend_context import ScreenInfoError
    from sr_od.backend.schemas import (
        AreaMutationOut,
        AreaMutationResult,
        ScreenCreateOut,
        ScreenCreateResult,
    )

    mcp, backend = _mcp_with_backend()
    backend.upsert_screen_area.return_value = AreaMutationResult(
        screen_name='邮件', area_name='标题', action='inserted', area_count=5)
    upsert_fn = getattr(mcp._tool_manager._tools['upsert_screen_area'],
                        'fn', None) or mcp._tool_manager._tools['upsert_screen_area'].func
    result = upsert_fn(screen_name='邮件', area_name='标题', pc_rect=[1, 1, 2, 2])
    assert isinstance(result, AreaMutationOut)
    assert result.action == 'inserted'
    assert result.area_count == 5

    backend.delete_screen_area.return_value = AreaMutationResult(
        screen_name='邮件', area_name='标题', action='deleted', area_count=4)
    delete_fn = getattr(mcp._tool_manager._tools['delete_screen_area'],
                        'fn', None) or mcp._tool_manager._tools['delete_screen_area'].func
    result = delete_fn(screen_name='邮件', area_name='标题')
    assert isinstance(result, AreaMutationOut)
    assert result.action == 'deleted'

    backend.create_screen.return_value = ScreenCreateResult(screen_id='mail', screen_name='邮件')
    create_fn = getattr(mcp._tool_manager._tools['create_screen'],
                        'fn', None) or mcp._tool_manager._tools['create_screen'].func
    result = create_fn(screen_id='mail', screen_name='邮件')
    assert isinstance(result, ScreenCreateOut)
    assert result.screen_id == 'mail'

    backend.upsert_screen_area.side_effect = ScreenInfoError('pc_rect 非法: [9, 9, 2, 2]')
    with pytest.raises(ScreenInfoError, match='pc_rect'):
        upsert_fn(screen_name='邮件', area_name='标题', pc_rect=[9, 9, 2, 2])
    backend.upsert_screen_area.side_effect = None
    backend.delete_screen_area.side_effect = ScreenInfoError('未找到 area: 不存在')
    with pytest.raises(ScreenInfoError, match='未找到 area'):
        delete_fn(screen_name='邮件', area_name='不存在')
    backend.delete_screen_area.side_effect = None
    backend.create_screen.side_effect = ScreenInfoError('screen_id 已存在: mail')
    with pytest.raises(ScreenInfoError, match='已存在'):
        create_fn(screen_id='mail', screen_name='邮件')
    backend.create_screen.side_effect = None


def test_get_screen_detail_renders_and_raises() -> None:
    """get_screen_detail:成功数据渲染 markdown,失败透传 ScreenInfoError(不渲染错误文案)。"""
    from sr_od.backend.backend_context import ScreenInfoError

    mcp, backend = _mcp_with_backend()
    backend.get_screen_detail.return_value = {
        'screen_name': '邮件', 'screen_id': 'mail', 'pc_alt': False,
        'area_count': 1,
        'areas': [{'area_name': '标题', 'id_mark': True, 'pc_rect': [1, 1, 100, 30],
                   'text': '邮件', 'lcs_percent': 0.5, 'template_id': '',
                   'template_sub_dir': '', 'template_match_threshold': 0.7,
                   'goto_list': []}],
        'goto_neighbors': ['主界面'],
    }
    tool = mcp._tool_manager._tools['get_screen_detail']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    out = fn(screen_name='邮件')
    assert isinstance(out, str)
    assert '画面档:邮件' in out
    assert '查询失败' not in out

    backend.get_screen_detail.side_effect = ScreenInfoError('画面名未找到: 邮箱')
    with pytest.raises(ScreenInfoError, match='画面名未找到'):
        fn(screen_name='邮箱')


def test_output_schema_matches_runtime_returns(tmp_path, monkeypatch) -> None:
    """带 outputSchema 的工具,运行时返回必须匹配其 schema。

    H1 教训:close_game 注解 `-> str` 但实际返回 dict,FastMCP 按 schema 校验
    直接炸——函数层测试绕过序列化层漏网,故对带 schema 工具做
    「调用 fn → jsonschema 校验返回」的序列化层冒烟。
    """
    import jsonschema
    import numpy as np

    from sr_od.backend.schemas import (
        ApplicationInfo,
        ApplicationListResult,
        AreaMutationResult,
        GotoScreenResult,
        InputTextResult,
        ScreenCreateResult,
        WindowStatus,
    )

    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(ocr_texts=[], screens=[])
    backend.query_status.return_value = RunStatusResult(
        state='running', source='mcp', app='OEG',
        started_at='2026-07-02T00:00:00', duration_seconds=1.0)
    backend.check_window.return_value = WindowStatus(
        win_title='t', is_win_valid=True, is_win_active=True, is_win_scale=False)
    backend.list_applications.return_value = ApplicationListResult(
        current_instance_idx=1, active_standalone_app_id=None,
        applications=[ApplicationInfo(app_id='x', app_name='X')])
    backend.list_screen_names.return_value = ['主界面', '邮件']
    backend.close_game.return_value = '已发送关闭游戏信号,可用 check_game_window 验证'
    backend.input_text.return_value = InputTextResult(method='clipboard', masked_text='***')
    backend.upsert_screen_area.return_value = AreaMutationResult(
        screen_name='邮件', area_name='标题', action='inserted', area_count=5)
    backend.delete_screen_area.return_value = AreaMutationResult(
        screen_name='邮件', area_name='标题', action='deleted', area_count=4)
    backend.create_screen.return_value = ScreenCreateResult(screen_id='mail', screen_name='邮件')
    backend.goto_screen.return_value = GotoScreenResult(
        arrived=True, current_screen='邮件', steps=[], reason=None)
    backend.click_game.return_value = True
    backend.key_tap.return_value = '已按下 esc'
    backend.drag.return_value = '已拖拽 (1,2)→(3,4)'
    backend.capture.return_value = np.zeros((4, 4, 3), dtype=np.uint8)
    monkeypatch.setattr(
        'sr_od.backend.backend_context.os_utils.get_path_under_work_dir',
        lambda *parts: str(tmp_path),
    )
    cases = {
        'analyze_screen': {'save_image': False},
        'check_game_window': {},
        'get_run_status': {},
        'list_applications': {},
        'list_screen_names': {},
        'close_game': {},
        'capture_game_screen': {},
        'input_text': {'text': 'abc', 'use_clipboard': True},
        'upsert_screen_area': {'screen_name': '邮件', 'area_name': '标题', 'pc_rect': [1, 1, 2, 2]},
        'delete_screen_area': {'screen_name': '邮件', 'area_name': '标题'},
        'create_screen': {'screen_id': 'mail', 'screen_name': '邮件'},
        'click_game': {'x': 1, 'y': 2},
        'key_tap': {'key': 'esc'},
        'drag': {'x1': 1, 'y1': 2, 'x2': 3, 'y2': 4},
        'goto_screen': {'target_screen_name': '邮件'},
    }
    for name, kwargs in cases.items():
        tool = mcp._tool_manager._tools[name]
        fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
        out = fn(**kwargs)
        instance = out.model_dump() if hasattr(out, 'model_dump') else out
        # 原子注解(-> str)与 union 返回的 schema 均为 wrapped 形态,运行时自动包 {'result': ...}
        if getattr(tool.fn_metadata, 'wrap_output', False):
            instance = {'result': instance}
        jsonschema.validate(instance=instance, schema=tool.output_schema)


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


def test_close_game_raises_on_not_ready() -> None:
    """close_game 在 backend 未就绪时异常透传(失败走错误通道,不做兜底包装)。"""
    mcp, backend = _mcp_with_backend()
    backend.close_game.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["close_game"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    assert fn is not None
    with pytest.raises(BackendNotReadyError, match="未就绪"):
        fn()


def test_capture_game_screen_returns_path(tmp_path, monkeypatch) -> None:
    """capture_game_screen 应保存截图并返回纯路径 str(失败异常透传)。"""
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
    assert isinstance(out, str)
    assert out.endswith(".png")


def test_capture_game_screen_raises_on_not_ready() -> None:
    """capture_game_screen 在 backend 未就绪时异常透传(失败走错误通道,不做兜底包装)。"""
    mcp, backend = _mcp_with_backend()
    backend.capture.side_effect = BackendNotReadyError("未就绪")
    tool = mcp._tool_manager._tools["capture_game_screen"]
    fn = getattr(tool, "fn", None) or getattr(tool, "func", None)
    with pytest.raises(BackendNotReadyError, match="未就绪"):
        fn()


# ===== open_game 工厂委托(enter 选 op)+ get_run_status/stop_run =====

def test_open_game_nonblock_returns_started() -> None:
    backend = _mock_backend()
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=False))
    assert isinstance(res, RunStartOut)
    assert res.app == 'OpenAndEnterGame'
    backend.start_run.assert_called_once()


def test_open_game_concurrent_reject() -> None:
    """单跑道占用 → RunStartRefusedError(异常通道,文案区分占用来源)。"""
    from sr_od.backend.backend_context import RunStartRefusedError

    backend = _mock_backend(start_ok=False)
    tool = app_mod.make_open_game(backend)
    with pytest.raises(RunStartRefusedError, match='已有运行'):
        asyncio.run(tool(enter=True, block=False))


@pytest.mark.parametrize('enter, expect_msg', [
    (True, '成功打开并进入星穹铁道游戏'),
    (False, '成功打开游戏(未登录)'),
], ids=['enter', 'open-only'])
def test_open_game_block_success(enter: bool, expect_msg: str) -> None:
    """block=True + 成功 future → RunFinishOut,按 enter 分支返回对应成功文案。"""
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='成功'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=enter, block=True))
    assert isinstance(res, RunFinishOut)
    assert res.success is True
    assert res.status == expect_msg


def test_open_game_block_failed() -> None:
    backend = _mock_backend()
    fut: Future = Future()
    fut.set_result(OperationResult(success=False, status='打开游戏失败'))
    backend.start_run.return_value = (True, fut)
    tool = app_mod.make_open_game(backend)
    res = asyncio.run(tool(enter=True, block=True))
    assert isinstance(res, RunFinishOut)
    assert res.success is False
    assert res.status == '打开游戏失败: 打开游戏失败'


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
    assert isinstance(res, RunStatusOut)   # tool 层转成 MCP 输出模型(字段语义走 outputSchema)
    backend.query_status.assert_called_once()


def test_stop_run_delegates() -> None:
    backend = _mock_backend()
    res = app_mod.make_stop_run(backend)()
    assert isinstance(res, RunStopOut)
    assert res.stopped is False
    backend.stop.assert_called_once()


def test_record_screen_failures_raise(monkeypatch) -> None:
    """record_screen:失败走 RuntimeError 异常通道(stop 无录屏/无 ffmpeg)。

    MCP 工具是纯透传(无转换逻辑),失败分支在 backend 方法体内——mock 替身
    backend 方法不可达,故用真 backend 实例直测。
    """
    from unittest.mock import MagicMock

    from sr_od.backend.backend_context import SrBackendContext

    backend = SrBackendContext(MagicMock(name='SrContext'))
    with pytest.raises(RuntimeError, match='没有正在进行的录屏'):
        backend.record_screen(mode='stop')
    monkeypatch.setattr('sr_od.backend.backend_context._resolve_ffmpeg_exe', lambda: None)
    with pytest.raises(RuntimeError, match='imageio-ffmpeg'):
        backend.record_screen(mode='fixed')


# ===== config 工具(Out 模型 + ConfigError 异常通道) =====

def test_config_tools_convert_and_raise() -> None:
    """config 工具:Out 模型 + ConfigError 异常通道(校验/引用失败不占成功结构)。"""
    import asyncio
    from unittest.mock import MagicMock

    from sr_od.backend.mcp.config_app import (
        ConfigError,
        make_add_config_item,
        make_describe_config,
        make_get_config,
        make_list_app_configs,
    )
    from sr_od.backend.schemas import ConfigListOut, ConfigReadOut, ConfigSchemaOut

    backend = MagicMock()
    ctx = MagicMock(name='SrContext')
    backend.ctx = ctx

    list_res = asyncio.run(make_list_app_configs(backend)(instance_idx=None))
    assert isinstance(list_res, ConfigListOut)
    assert any(c['app_id'] == 'standalone_app' for c in list_res.configs)

    with pytest.raises(ConfigError, match='list_app_configs'):
        asyncio.run(make_get_config(backend)(app_id='不存在的', key=None))

    with pytest.raises(ConfigError, match='非负下标'):
        asyncio.run(make_add_config_item(backend)(
            app_id='trailblaze_power', list_field='plan_list', item_dict={}, idx=-1))

    ctx.power_config.data = {'plan_enable': True}
    ctx.power_config._RO_FIELDS = {'loop'}  # 触发 set_config 只读拒绝路径
    read_res = asyncio.run(make_get_config(backend)(
        app_id='trailblaze_power', key='plan_enable', instance_idx=None))
    assert isinstance(read_res, ConfigReadOut)
    assert read_res.value is True

    from sr_od.backend.mcp.config_app import make_set_config
    with pytest.raises(ConfigError, match='只读字段'):
        asyncio.run(make_set_config(backend)(
            app_id='trailblaze_power', key='loop', value=True, instance_idx=None))

    schema_res = asyncio.run(make_describe_config(backend)(
        app_id='trailblaze_power', category=None, instance_idx=None))
    assert isinstance(schema_res, ConfigSchemaOut)
    assert isinstance(schema_res.set_fields, list)


# ===== click_game / key_tap / drag 工具(内联注册,原子返回) =====

def test_click_game_tool_delegates() -> None:
    """click_game tool 直调 backend.click_game()(默认 press_time=0.1/pc_alt=False),返回纯 bool。"""
    mcp, backend = _mcp_with_backend()
    backend.click_game.return_value = True
    tool = mcp._tool_manager._tools['click_game']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(x=960, y=540)
    backend.click_game.assert_called_once_with(960, 540, 0.1, False)
    assert result is True


def test_key_tap_and_drag_delegates_return_ack() -> None:
    """key_tap/drag tool 直调 backend 并透传确认文案 str。"""
    mcp, backend = _mcp_with_backend()
    backend.key_tap.return_value = '已按下 esc'
    backend.drag.return_value = '已拖拽 (1,2)→(3,4)'
    key_fn = getattr(mcp._tool_manager._tools['key_tap'], 'fn', None) or mcp._tool_manager._tools['key_tap'].func
    drag_fn = getattr(mcp._tool_manager._tools['drag'], 'fn', None) or mcp._tool_manager._tools['drag'].func
    assert key_fn(key='esc') == '已按下 esc'
    backend.key_tap.assert_called_once_with('esc', 0.0)
    assert drag_fn(x1=1, y1=2, x2=3, y2=4) == '已拖拽 (1,2)→(3,4)'
    backend.drag.assert_called_once_with(1, 2, 3, 4, 1.0)


def test_input_tools_stop_interrupted_raise_runtime_error() -> None:
    """click_game/key_tap/drag 停机守卫异常转 RuntimeError 走错误通道(BaseException 不裸透传)。

    裁决背景(2026-09-02 第二轮审计冲突):ServerErrorMiddleware/FastMCP 泛型
    兜底只接 Exception,BaseException 穿透会变成 ASGI 层错误 + 连接断。正常
    路径手动端点已在 backend 层豁免不应到达此处;工具层按名转 RuntimeError
    是防御纵深(与 close_game/input_text 同款)。
    """
    from one_dragon.base.controller.stop_guard import StopRunInterrupted

    mcp, backend = _mcp_with_backend()
    for name, invoke in (
        ('click_game', lambda fn: fn(x=1, y=2)),
        ('key_tap', lambda fn: fn(key='esc')),
        ('drag', lambda fn: fn(x1=1, y1=2, x2=3, y2=4)),
    ):
        backend_method = getattr(backend, name)
        backend_method.side_effect = StopRunInterrupted('停机')
        tool = mcp._tool_manager._tools[name]
        fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
        with pytest.raises(RuntimeError, match='停机中断'):
            invoke(fn)
        backend_method.side_effect = None


def test_close_game_stop_interrupted_raises_runtime_error() -> None:
    """close_game 停机守卫异常转 RuntimeError 走错误通道(BaseException 不裸透传)。"""
    from one_dragon.base.controller.stop_guard import StopRunInterrupted

    mcp, backend = _mcp_with_backend()
    backend.close_game.side_effect = StopRunInterrupted('停机')
    tool = mcp._tool_manager._tools['close_game']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    with pytest.raises(RuntimeError, match='停机中断'):
        fn()


def test_input_text_stop_interrupted_raises_runtime_error() -> None:
    """input_text 停机守卫异常转 RuntimeError 走错误通道(BaseException 不裸透传)。"""
    from one_dragon.base.controller.stop_guard import StopRunInterrupted

    mcp, backend = _mcp_with_backend()
    backend.input_text.side_effect = StopRunInterrupted('停机')
    tool = mcp._tool_manager._tools['input_text']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    with pytest.raises(RuntimeError, match='停机中断'):
        fn(text='abc')


def test_goto_screen_converts_and_carries_scene() -> None:
    """goto_screen:到达/中断均转 GotoScreenOut(中断带现场为正常结果);目标不存在透传 ScreenInfoError。

    停机守卫拦截是 backend.goto_screen 的真实可达路径(未豁免,停机后首次
    导航点击即被拦),内部转 arrived=False 中断结果——转换逻辑由
    test_backend_context 的停机直测覆盖;本文件 mock 替身整个 backend 方法,
    测不到该内部分支(见下 stop_interrupted 段说明)。
    """
    from sr_od.backend.backend_context import ScreenInfoError
    from sr_od.backend.schemas import GotoScreenOut, GotoScreenResult

    mcp, backend = _mcp_with_backend()
    tool = mcp._tool_manager._tools['goto_screen']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)

    backend.goto_screen.return_value = GotoScreenResult(
        arrived=True, current_screen='邮件', steps=['主界面 --邮件按钮--> 邮件'], reason=None)
    result = fn(target_screen_name='邮件')
    assert isinstance(result, GotoScreenOut)
    assert result.arrived is True
    assert result.reason is None

    backend.goto_screen.return_value = GotoScreenResult(
        arrived=False, current_screen='主界面', steps=[], reason='截图失败')
    result = fn(target_screen_name='邮件')
    assert result.arrived is False
    assert result.current_screen == '主界面'
    assert '截图失败' in result.reason

    backend.goto_screen.side_effect = ScreenInfoError('目标画面不存在: 邮箱(用 list_screen_names 查全量)')
    with pytest.raises(ScreenInfoError, match='目标画面不存在'):
        fn(target_screen_name='邮箱')
    backend.goto_screen.side_effect = None


def test_input_text_tool_delegates() -> None:
    """input_text tool 直调 backend.input_text() 并转 InputTextOut。"""
    from sr_od.backend.schemas import InputTextOut, InputTextResult

    mcp, backend = _mcp_with_backend()
    backend.input_text.return_value = InputTextResult(method='clipboard', masked_text='***')
    tool = mcp._tool_manager._tools['input_text']
    fn = getattr(tool, 'fn', None) or getattr(tool, 'func', None)
    result = fn(text='abc', use_clipboard=True)
    backend.input_text.assert_called_once_with('abc', True)
    assert isinstance(result, InputTextOut)
    assert result.method == 'clipboard'
    assert result.masked_text == '***'


def test_analyze_screen_tool_passes_save_image() -> None:
    """analyze_screen tool 应把 save_image/include_ocr 透传给 backend.analyze,并回带 screenshot_path。"""
    mcp, backend = _mcp_with_backend()
    backend.analyze.return_value = AnalyzeScreenResult(
        ocr_texts=[], screenshot_path='/tmp/x.png')
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
    """合法 op_id + 空 args → run_slot._start 被调(op_factory 路径),RunStartOut 受理。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (True, Future())
    backend.query_status.return_value = RunStatusResult(
        state='running', source='mcp', started_at='2026-07-02T00:00:00', duration_seconds=1.0)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, args={}, block=False))
    assert isinstance(res, RunStartOut)
    backend.run_slot._start.assert_called_once()
    call = backend.run_slot._start.call_args
    assert call.args[0] == 'mcp'                                   # source
    op_factory = call.kwargs.get('op_factory') or call.args[1]
    assert callable(op_factory)
    assert call.kwargs.get('display_name') == _OPEN_AND_ENTER      # op_id 作定位标识


def test_run_operation_rejects_non_operation() -> None:
    """op_id 解析出非 Operation(resolve_op_class raise)→ 异常透传,不调 _start。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    with pytest.raises(ValueError):
        asyncio.run(make_run_operation(backend)(op_id=_CHARGE_PLAN_ITEM, block=False))
    backend.run_slot._start.assert_not_called()


def test_run_operation_rejects_missing_required() -> None:
    """缺必填参数(validate_args 返错)→ ValueError 带参数名,不调 _start。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    with pytest.raises(ValueError, match='stuck_times'):
        asyncio.run(make_run_operation(backend)(
            op_id=_GET_RID_OF_STUCK, args={}, block=False))
    backend.run_slot._start.assert_not_called()


def test_run_operation_concurrent_reject() -> None:
    """单跑道已有运行 → run_slot._start 返 (False, None) → RunStartRefusedError(异常通道)。"""
    from sr_od.backend.backend_context import RunStartRefusedError
    from sr_od.backend.mcp.service_app import make_run_operation

    backend = MagicMock()
    backend.run_slot._start.return_value = (False, None)
    backend.query_status.return_value = RunStatusResult(state='running', source='http')
    # 拒绝异常由 backend 统一助手产出,绑真实现(依赖均已被 mock)。
    backend.run_refusal_error = lambda hint: SrBackendContext.run_refusal_error(backend, hint)
    with pytest.raises(RunStartRefusedError) as exc_info:
        asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, block=False))
    assert '已有运行' in str(exc_info.value)
    assert 'http' in str(exc_info.value)  # 来源进文案


def test_run_operation_block_success() -> None:
    """block=True + 成功结果 → RunFinishOut 终态。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='ok'))
    backend = MagicMock()
    backend.run_slot._start.return_value = (True, fut)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, args={}, block=True))
    assert isinstance(res, RunFinishOut)
    assert res.success is True and '成功' in res.status


def test_run_operation_block_returns_data() -> None:
    """block=True + op 携带 data → RunFinishOut 带 data 通道(读数类 op 契约)。"""
    from sr_od.backend.mcp.service_app import make_run_operation

    payload = {'pool_type': 'character', 'stellar_jade': 12183}
    fut: Future = Future()
    fut.set_result(OperationResult(success=True, status='WARP_STATUS', data=payload))
    backend = MagicMock()
    backend.run_slot._start.return_value = (True, fut)
    res = asyncio.run(make_run_operation(backend)(op_id=_OPEN_AND_ENTER, args={}, block=True))
    assert isinstance(res, RunFinishOut)
    assert res.success is True
    assert res.data == payload


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
    assert isinstance(res, RunStartOut)
    assert backend.run_slot._start.call_args.kwargs.get('display_name') == _OPEN_AND_ENTER
