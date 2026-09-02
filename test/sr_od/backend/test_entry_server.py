"""后端服务入口（``create_app`` 装配 + 日志分流配置）的单元测试。

通过 ``MagicMock`` 伪造 backend（不真启动 uvicorn），只校验 ``create_app``
是否把 MCP ``/mcp`` 端点与 ``/game/*`` custom_route 同进程挂到同一 Starlette app。
``app.routes`` 可能含 ``Mount``，因此递归收集子路由的 ``path``。

日志分流测试锁(2026-08-24 职责划分):MCP server 进程的框架 logger 必须指向
专属文件 ``.log/mcp_server.log`` 且**不挂 console handler**——否则框架日志双写
(``.log/log.txt`` 混 GUI/调度器进程身份 + stdout→main_server.log 全量副本),
详见 ``server.py`` ``_configure_server_logging`` 的注释。
"""

import contextlib
import logging
from typing import Any
from unittest.mock import MagicMock

from one_dragon.utils import log_utils
from one_dragon.utils.log_utils import _close_managed_handlers
from sr_od.backend.entry.server import create_app


def _collect_paths(routes: list[Any]) -> list[str]:
    """递归收集 Starlette 路由（含 ``Mount`` 子路由）的 ``path``。

    Args:
        routes: ``app.routes`` 或某 ``Mount`` 的 ``routes`` 列表。

    Returns:
        所有非空 ``path`` 字符串列表。
    """
    paths: list[str] = []
    for r in routes:
        p = getattr(r, "path", None)
        if p:
            paths.append(p)
        sub = getattr(r, "routes", None)
        if sub:
            paths.extend(_collect_paths(sub))
    return paths


def test_create_app_mounts_mcp_and_game_routes() -> None:
    """``create_app`` 应在同一 app 上同时挂载 ``/game/*`` 与 ``mcp`` 端点。"""
    backend = MagicMock()
    app = create_app(backend)
    paths = _collect_paths(app.routes)
    assert any("/game/window" in p for p in paths)
    assert any("mcp" in p for p in paths)


def test_serve_configures_logging_before_context_creation() -> None:
    """锁启动顺序:``_serve`` 里日志分流必须先于 ``SrContext()``。

    上下文构造期间(地图数据/实例配置加载)就打框架日志;分流若在其后,
    这段 init 日志走默认双写——console→main_server.log(stdout 兜底日志混入
    框架日志)与共享 log.txt(与 GUI 的跨进程轮转竞态窗口)。静态锁用
    ``_serve`` 函数体内的调用先后,防未来重排时回归。
    """
    import inspect

    from sr_od.backend.entry import server

    src = inspect.getsource(server._serve)
    configure_pos = src.index('_configure_server_logging()')
    root_pos = src.index('_configure_root_logger_single_channel()')
    ctx_pos = src.index('ctx = SrContext()')
    assert configure_pos < ctx_pos, (
        '日志分流必须在 SrContext() 之前调用,否则 init 窗口框架日志'
        '双写进 main_server.log 与共享 log.txt'
    )
    assert root_pos < ctx_pos, (
        'root logger 单一信道修必须在 SrContext()/FastMCP 构造之前,'
        '否则 init 窗口的 getLogger(__name__) 型日志走裸 stderr 进 main_server.log'
    )


def test_serve_uses_no_uvicorn_log_config() -> None:
    """uvicorn 不得自配 logging(日志信道漂移的另一写端的回归锁)。

    uvicorn 缺省 LOGGING_CONFIG 给自己的 logger 族挂 stderr StreamHandler,
    每次重启的启动块(Started server process/Uvicorn running)都写进被 daemon
    重定向的 main_server.log → 该文件 mtime 每次重启一度变新,哨兵按
    「两候选 mtime 最新」选活性信道时随之来回切换。锁两层:
    ①静态:_serve 构造 uvicorn.Config 必须传 log_config=None;
    ②行为:log_config=None 的 Config.configure_logging() 后 uvicorn logger 族
    不得出现任何自有 handler(裸 logger 沿层级上传 root → mcp_server.log)。
    """
    import inspect

    from sr_od.backend.entry import server

    src = inspect.getsource(server._serve)
    assert 'log_config=None' in src, (
        'uvicorn.Config 必须传 log_config=None,否则 uvicorn 启动块每次重启'
        '都写 stderr→main_server.log,哨兵活性信道来回漂移'
    )

    import uvicorn

    saved = {}
    try:
        for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
            saved[name] = (logging.getLogger(name).handlers[:],
                           logging.getLogger(name).level,
                           logging.getLogger(name).propagate)
        config = uvicorn.Config(lambda scope, receive, send: None,
                                log_config=None)
        config.configure_logging()
        for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
            lg = logging.getLogger(name)
            assert lg.handlers == [], (
                f'{name} 不得有自有 handler(stderr 启动块=信道漂移写端),实得 {lg.handlers}'
            )
    finally:
        for name, (handlers, level, propagate) in saved.items():
            lg = logging.getLogger(name)
            lg.handlers = handlers
            lg.setLevel(level)
            lg.propagate = propagate


def test_root_logger_single_channel_blocks_fastmcp_basicconfig() -> None:
    """root 单一信道锁:w944 哨兵双信道漂移根因是 FastMCP.__init__ 经
    mcp.server.fastmcp.utilities.logging.configure_logging → logging.basicConfig
    给 root 挂裸 stderr handler,使 getLogger(__name__) 型业务 logger 的行
    (collect_plane_intel 等)以裸格式进 main_server.log。本锁断言:
    ①本函数先给 root 挂 mcp_server.log 文件 handler;②之后模拟 FastMCP 的
    configure_logging(真调 mcp SDK 函数)时 root handler 集不变
    (basicConfig no-op),不再出现 StreamHandler 漂移通道。"""
    from sr_od.backend.entry.server import _configure_root_logger_single_channel

    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    root.handlers = []          # 模拟干净生产 root(本函数有「已有 handler 不覆盖」守卫)
    root.setLevel(logging.WARNING)
    try:
        _configure_root_logger_single_channel()
        assert root.level == logging.INFO
        assert len(root.handlers) == 1, f'root 应有且仅有一个 handler,实得 {root.handlers}'
        h = root.handlers[0]
        assert isinstance(h, logging.FileHandler)
        assert h.baseFilename.endswith('mcp_server.log')
        # FastMCP.__init__ 实际调用的 SDK 函数:root 已有 handler → no-op
        from mcp.server.fastmcp.utilities.logging import (
            configure_logging as mcp_configure,
        )
        mcp_configure('INFO')
        assert len(root.handlers) == 1, (
            'FastMCP configure_logging 后 root handler 集必须不变'
            '(basicConfig no-op),否则裸 stderr handler 复活 → 双信道漂移回归'
        )
        assert not any(isinstance(x, logging.StreamHandler)
                       and not isinstance(x, logging.FileHandler)
                       for x in root.handlers)
    finally:
        for x in root.handlers[:]:
            root.removeHandler(x)
            with contextlib.suppress(Exception):
                if isinstance(x, logging.FileHandler):
                    x.close()
        root.handlers = saved_handlers
        root.setLevel(saved_level)


def test_route_uvicorn_logs_fragile_branch_attaches_file_handler() -> None:
    """uvicorn 日志路由兜底:root 被外来 handler 占位时显式挂 mcp_server.log。

    实证背景(2026-09-02 tmp 日志探针):主路径 root 单一信道 + propagate
    默认 → uvicorn 启动行落 mcp_server.log,不失明;脆弱分支 =
    ``_configure_root_logger_single_channel`` 跳过(root 已有外来 handler,
    如测试预置)→ uvicorn 行落外来 handler。锁:
    ①脆弱分支:uvicorn logger 族挂 SafeTimedRotatingFileHandler 且关
    propagate(单目的地 mcp_server.log);
    ②主路径(root 已挂本文件 handler):不重复挂(否则每行双写)。"""
    from one_dragon.utils.log_utils import (
        SafeTimedRotatingFileHandler,
        get_log_file_path,
    )
    from sr_od.backend.entry.server import (
        MCP_SERVER_LOG_FILE_NAME,
        _route_uvicorn_logs_to_mcp_log,
    )

    names = ('uvicorn', 'uvicorn.error', 'uvicorn.access')
    root = logging.getLogger()
    saved_root_handlers = root.handlers[:]
    saved = {n: (logging.getLogger(n).handlers[:],
                 logging.getLogger(n).level,
                 logging.getLogger(n).propagate) for n in names}
    try:
        # ①脆弱分支:root 只有外来 StreamHandler
        foreign = logging.NullHandler()
        root.handlers = [foreign]
        for n in names:
            logging.getLogger(n).handlers = []
        _route_uvicorn_logs_to_mcp_log()
        for n in names:
            lg = logging.getLogger(n)
            assert len(lg.handlers) == 1, f'{n} 应挂且仅挂一个兜底 handler'
            assert isinstance(lg.handlers[0], SafeTimedRotatingFileHandler)
            assert lg.handlers[0].baseFilename.endswith(MCP_SERVER_LOG_FILE_NAME)
            assert lg.propagate is False, f'{n} 应关 propagate(单目的地)'

        # ②主路径:root 已挂本文件 handler → 不重复挂、不动 propagate
        own = SafeTimedRotatingFileHandler(
            get_log_file_path(default_name=MCP_SERVER_LOG_FILE_NAME),
            when='midnight', interval=1, backupCount=3,
            encoding='utf-8', delay=True)
        root.handlers = [own]
        for n in names:
            lg = logging.getLogger(n)
            lg.handlers = []
            lg.propagate = True
        _route_uvicorn_logs_to_mcp_log()
        for n in names:
            lg = logging.getLogger(n)
            assert lg.handlers == [], f'{n} 主路径不得重复挂 handler(双写)'
            assert lg.propagate is True, '主路径应保持 root 传播默认'
    finally:
        for n, (handlers, level, propagate) in saved.items():
            lg = logging.getLogger(n)
            for h in lg.handlers[:]:
                lg.removeHandler(h)
                with contextlib.suppress(Exception):
                    if isinstance(h, logging.FileHandler):
                        h.close()
            lg.handlers = handlers
            lg.setLevel(level)
            lg.propagate = propagate
        root.handlers = saved_root_handlers


def test_configure_server_logging_routes_to_dedicated_file() -> None:
    """框架 logger 应被切到 ``mcp_server.log`` 专属文件且不再挂 console handler。

    锁两个不变量:①文件 handler 的目标文件名是 ``mcp_server.log``(进程身份即文件);
    ②无 ``StreamHandler``(console 关闭,stdout/main_server.log 回归兜底职责)。
    """
    from sr_od.backend.entry.server import _configure_server_logging

    _configure_server_logging()
    try:
        logger = log_utils.log
        assert logger.name == log_utils.LOGGER_NAME
        # 只看框架自管 handler(带 owner 标记),外部挂载的不算
        managed = [h for h in logger.handlers
                   if getattr(h, log_utils._HANDLER_OWNER_ATTR, None) == logger.name]
        assert managed, '框架 logger 应有自管 handler'
        file_handlers = [h for h in managed if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1, f'应有且仅有一个文件 handler,实得 {len(file_handlers)}'
        assert file_handlers[0].baseFilename.endswith('mcp_server.log'), (
            f"文件 handler 应指向 mcp_server.log,实得 {file_handlers[0].baseFilename}"
        )
        stream_handlers = [h for h in managed if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, logging.FileHandler)]
        assert not stream_handlers, (
            f'不应再有 console(StreamHandler),否则框架日志双写进 main_server.log,实得 {stream_handlers}'
        )
    finally:
        # 还原为 pytest 进程的「不落盘」默认态(conftest 日志隔离):
        # 该 logger 是共享单例,别让 mcp_server.log 分流配置泄漏给其他测试;
        # 也不得还原成默认 log.txt handler——那会让本 pytest 进程重新持有
        # 共享日志句柄,回到并发轮转竞态面。
        _close_managed_handlers(logger)
        _null_handler = logging.NullHandler()
        _null_handler._one_dragon_logger_owner = logger.name  # noqa: SLF001
        logger.addHandler(_null_handler)
        logger.propagate = False
