"""回归锁:YOLO 子系统日志单一信道(哨兵「日志信道漂移」的写端修复)。

背景:.log/mcp_server.log 与 .debug/sr_od_mcp/main_server.log 反复切换的
双写源之一 —— 旧 ``one_dragon/yolo/log_utils.py`` 给 ``'OneDragon-YOLO'``
挂裸 stderr StreamHandler:server 进程里 stderr 被重定向进 main_server.log,
而框架日志走 mcp_server.log,每次 YOLO 模型加载两文件 mtime 交替变新,
哨兵按「mtime 最新」选活性信道时来回切换。

修后语义:logger 改名 ``'OneDragon.YOLO'``(成为框架 logger ``OneDragon``
的子层级)、零自有 handler、propagate=True —— 信道随进程身份自动归位。
"""

import logging

from one_dragon.yolo import log_utils as yolo_log_utils


def test_yolo_logger_has_no_own_stream_channel() -> None:
    """YOLO logger 不得自带任何 handler(裸 stderr 双写通道的回归锁)。"""
    logger = yolo_log_utils.get_logger()
    assert logger.name == 'OneDragon.YOLO', (
        f"logger 名必须留在 'OneDragon.YOLO' 层级(父=框架 logger),实得 {logger.name!r}"
    )
    assert logger.handlers == [], (
        f'YOLO logger 不得自带 handler(stderr 裸挂=双信道漂移写端),实得 {logger.handlers}'
    )
    assert logger.propagate, (
        'YOLO logger 必须 propagate(否则记录无处可去或被迫自配信道)'
    )


def test_yolo_records_land_on_process_single_channel(tmp_path) -> None:
    """行为锁:server 形态配置下,YOLO 记录只落框架文件信道,不进 stderr。

    模拟 server 进程的框架配置(专属文件、无 console),经真 logger 层级
    发一条 YOLO INFO:①文件收到;②捕获到的 stderr/stderr 形态 handler 为空。
    """
    from one_dragon.utils import log_utils
    from one_dragon.utils.log_utils import LoggerConfig, configure_logger

    framework = log_utils.log
    log_file = tmp_path / 'mcp_server.log'
    configure_logger(
        framework,
        LoggerConfig(log_file_path=str(log_file), add_console_handler=False),
    )
    try:
        yolo = yolo_log_utils.get_logger()
        yolo.info('单信道探针行')
        for h in (*yolo.handlers, *framework.handlers):
            h.flush()
        text = log_file.read_text(encoding='utf-8')
        assert '单信道探针行' in text, 'YOLO 记录应经框架层级落进程专属文件'
        # 只锁「指向真实 stderr/stdout 的裸 StreamHandler」——那才是双写通道
        # (pytest 的 LogCaptureHandler 等测试基建 handler 不指向终端,不算)。
        import sys

        bare = [h for h in (*yolo.handlers, *framework.handlers)
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.FileHandler)
                and getattr(h, 'stream', None) in (sys.stderr, sys.stdout)]
        assert not bare, (
            f'层级内不得出现指向 stderr/stdout 的裸 StreamHandler'
            f'(=双信道漂移写端复活),实得 {bare}'
        )
    finally:
        # 还原 pytest 进程「不落盘」默认态(与 test_entry_server 同口径),
        # 防 mcp_server.log 分流配置泄漏给其他测试。
        from one_dragon.utils.log_utils import _close_managed_handlers

        _close_managed_handlers(framework)
        null_handler = logging.NullHandler()
        null_handler._one_dragon_logger_owner = framework.name  # noqa: SLF001
        framework.addHandler(null_handler)
        framework.propagate = False
