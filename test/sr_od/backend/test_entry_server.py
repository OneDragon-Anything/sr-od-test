"""后端服务入口（``create_app`` 装配 + 日志分流配置）的单元测试。

通过 ``MagicMock`` 伪造 backend（不真启动 uvicorn），只校验 ``create_app``
是否把 MCP ``/mcp`` 端点与 ``/game/*`` custom_route 同进程挂到同一 Starlette app。
``app.routes`` 可能含 ``Mount``，因此递归收集子路由的 ``path``。

日志分流测试锁(2026-08-24 职责划分):MCP server 进程的框架 logger 必须指向
专属文件 ``.log/mcp_server.log`` 且**不挂 console handler**——否则框架日志双写
(``.log/log.txt`` 混 GUI/调度器进程身份 + stdout→main_server.log 全量副本),
详见 ``server.py`` ``_configure_server_logging`` 的注释。
"""

import logging
from typing import Any
from unittest.mock import MagicMock

from one_dragon.utils import log_utils
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
        # 还原默认配置(测试进程内该 logger 是共享单例,别让分流配置泄漏给其他测试)
        log_utils.configure_logger(
            logger, log_utils.LoggerConfig(add_console_handler=False),
        )
