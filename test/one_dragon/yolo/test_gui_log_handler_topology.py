"""回归锁:GUI 消费端 yolo 日志 handler 挂接拓扑(一条 INFO 恰显一次)。

背景:``OneDragon.YOLO`` 收口为 ``propagate=True`` 的纯层级子 logger 后,
GUI 两消费端(日志卡片 / overlay)旧拓扑仍把**同一个 handler 实例**挂到
``OneDragon``(od_log)与 ``OneDragon.YOLO``(yolo_log)两个 logger ——
yolo 记录先命中子 logger 的 handler,传播到父后又命中同一 handler,
一条 yolo INFO 显示两次(logging 传播不去重)。

修后语义:消费端只在框架根 logger ``OneDragon`` 上挂 handler,yolo 记录
经层级传播到达同一 handler 恰一次;子 logger 上零消费端 handler。

GUI 模块需要 QApplication/Qt 上下文,测试仓无 Qt 基建无法实例化,故用
①源码拓扑锁(消费端源码不得引用 yolo logger 挂/摘 handler) +
②行为锁(按修后拓扑真实挂接并经层级发记录,断言恰收一次)双保险。
"""

import logging
from pathlib import Path

import pytest

from one_dragon.utils.log_utils import LOGGER_NAME
from one_dragon.utils.log_utils import log as framework_log
from one_dragon.yolo import log_utils as yolo_log_utils

_SRC_ROOT = Path(__file__).parents[4] / 'src'
#: GUI 侧消费框架/yolo 日志 logger 的全部挂接点(新增消费端时在此登记)。
_CONSUMER_FILES = [
    _SRC_ROOT / 'one_dragon_qt' / 'widgets' / 'log_display_card.py',
    _SRC_ROOT / 'one_dragon_qt' / 'overlay' / 'overlay_manager.py',
]


class _CountingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.mark.parametrize('consumer_path', _CONSUMER_FILES, ids=lambda p: p.name)
def test_gui_consumers_do_not_attach_handlers_to_yolo_logger(
    consumer_path: Path,
) -> None:
    """源码拓扑锁:GUI 消费端不得在 yolo 子 logger 上挂/摘 handler。

    yolo logger 的收口契约 = 零自有 handler + propagate;任何消费端往它
    上挂 handler 都会破坏「一条记录恰命中一次」(同 handler 挂父子两处
    各收一遍,logging 传播不去重)。
    """
    assert consumer_path.is_file(), f'消费端源文件应存在: {consumer_path}'
    source = consumer_path.read_text(encoding='utf-8')
    assert 'yolo_log.addHandler' not in source, (
        f'{consumer_path.name} 不得往 yolo 子 logger 挂 handler:'
        '收口后 yolo 记录经 propagate 由框架根 logger 的 handler 统一接收,'
        '子侧再挂 = 同一条日志双显'
    )
    assert 'yolo_log.removeHandler' not in source, (
        f'{consumer_path.name} 不得操作 yolo 子 logger 的 handler'
        '(挂接已收口到框架根 logger,摘除也应只针对根 logger)'
    )


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
