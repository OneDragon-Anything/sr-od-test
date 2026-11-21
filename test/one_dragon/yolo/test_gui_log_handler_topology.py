"""回归锁:GUI 消费端 yolo 日志 handler 挂接拓扑(一条 INFO 恰显一次)。

背景:``OneDragon.YOLO`` 收口为 ``propagate=True`` 的纯层级子 logger 后,
GUI 两消费端(日志卡片 / overlay)旧拓扑仍把**同一个 handler 实例**挂到
``OneDragon``(od_log)与 ``OneDragon.YOLO``(yolo_log)两个 logger ——
yolo 记录先命中子 logger 的 handler,传播到父后又命中同一 handler,
一条 yolo INFO 显示两次(logging 传播不去重)。

修后语义:消费端只在框架根 logger ``OneDragon`` 上挂 handler,yolo 记录
经层级传播到达同一 handler 恰一次;子 logger 上零消费端 handler。
"""

import logging

from one_dragon.utils.log_utils import LOGGER_NAME
from one_dragon.utils.log_utils import log as framework_log
from one_dragon.yolo import log_utils as yolo_log_utils


class _CountingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_yolo_info_reaches_parent_handler_exactly_once() -> None:
    """行为锁:按修后拓扑(仅框架根挂消费端 handler),一条 yolo INFO 恰收一次。

    复现双显机制的对照组:若同一 handler 再挂到 yolo 子 logger,计数将翻倍
    ——本用例锁死修后拓扑下计数恒为 1。
    """
    yolo = yolo_log_utils.get_logger()
    assert yolo.propagate, '前置: yolo logger 必须传播到父层级'
    assert yolo.name.startswith(f'{LOGGER_NAME}.'), (
        '前置: yolo logger 必须是框架根 logger 的子层级'
    )

    receiver = _CountingHandler()
    framework_log.addHandler(receiver)
    try:
        yolo.info('拓扑探针行')
        assert receiver.messages.count('拓扑探针行') == 1, (
            f'一条 yolo INFO 应恰被消费端 handler 收一次,'
            f'实收 {receiver.messages.count("拓扑探针行")} 次'
            f'(>1 = handler 同时挂在父子两个 logger 上,双显回归)'
        )
    finally:
        framework_log.removeHandler(receiver)
