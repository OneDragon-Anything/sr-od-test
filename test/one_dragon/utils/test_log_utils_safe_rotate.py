"""回归锁:.log 并发写竞态(SafeTimedRotatingFileHandler)。

机制(先证后裁的实证面):Windows 不允许 rename 被任何进程打开中的文件,
``TimedRotatingFileHandler.doRollover`` 的 ``os.rename`` 遇另一份打开句柄即抛
``PermissionError(WinError 32)``。本文件在同一进程内用两个指向同一文件的
handler 复现同一 OS 层约束(A 的流开着,B 换名必撞锁),与跨进程场景同型 ——
进程边界不改变句柄语义。

判定标准:SafeTimedRotatingFileHandler 轮转被占用时不得抛异常 —— 退避重试,
全失败则放弃本次轮转、恢复可写流并推迟下一个轮转时点;原版 handler 则应
复现抛错(证明测试自身测的是真病,不是安慰剂)。
"""

import logging
import logging.handlers
import os
import time

import pytest

from one_dragon.utils.log_utils import (
    LOGGER_NAME,
    SafeTimedRotatingFileHandler,
    _handler_belongs_to_logger,
)
from one_dragon.utils.log_utils import log as framework_log

_NT_ONLY = pytest.mark.skipif(os.name != 'nt', reason='rename 占位报错是 Windows 行为')


def _make_stock_handler(path: str) -> logging.handlers.TimedRotatingFileHandler:
    return logging.handlers.TimedRotatingFileHandler(
        path, when='midnight', backupCount=3, encoding='utf-8',
    )


@_NT_ONLY
@pytest.mark.parametrize('safe', [False, True])
def test_rollover_with_foreign_open_handle(tmp_path, safe: bool) -> None:
    """A 流保持打开,B 换名:原版抛 WinError 32,safe 版推迟不抛。"""
    target = str(tmp_path / 'log.txt')
    holder = _make_stock_handler(target)
    try:
        holder.stream.write('held open\n')
        holder.stream.flush()

        rotator = (
            SafeTimedRotatingFileHandler(target, when='midnight', backupCount=3, encoding='utf-8')
            if safe else _make_stock_handler(target)
        )
        rotator.rolloverAt = int(time.time())  # 强制到点轮转
        try:
            raised = False
            try:
                rotator.doRollover()
            except PermissionError:
                raised = True

            if safe:
                assert not raised, 'safe handler 被占用轮转不应抛异常'
                # 降级而非停摆:无归档文件产生,流可写,轮转时点已推迟。
                assert not any(p.name.startswith('log.txt.') for p in tmp_path.iterdir())
                assert rotator.stream is not None and not rotator.stream.closed
                rotator.stream.write('post-defer\n')
                rotator.stream.flush()
                assert rotator.rolloverAt > time.time(), '全败后应推迟下一个轮转时点'
            else:
                assert raised, '原版 handler 应在此场景复现 WinError 32(测试有效性前提)'
        finally:
            rotator.close()
    finally:
        holder.close()


@_NT_ONLY
def test_safe_handler_emits_record_after_deferred_rollover(tmp_path) -> None:
    """推迟后经正常 emit 路径仍能落一条日志(end-to-end,不经流直写)。"""
    target = str(tmp_path / 'log.txt')
    holder = _make_stock_handler(target)
    rotator = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )
    try:
        rotator.rolloverAt = int(time.time()) - 1  # 强制到点
        rotator.emit(logging.LogRecord(
            name='t', level=logging.INFO, pathname=__file__, lineno=1,
            msg='after defer', args=(), exc_info=None,
        ))
        content = (tmp_path / 'log.txt').read_text(encoding='utf-8')
        assert 'after defer' in content
        assert rotator.rolloverAt > time.time()
    finally:
        rotator.close()
        holder.close()


def test_pytest_process_holds_no_file_handler_on_framework_logger() -> None:
    """conftest 日志隔离锁:pytest 进程的框架 logger 不得挂真实文件 handler。

    依据 :测试进程退出共享日志写入方集合(零句柄),从源头消掉与
    sim 批/regen 进程的轮转竞态。本断言跑在 pytest 进程内 = 直接验证默认态;
    设 SR_TEST_LOG_FILE=1 时有意放开(逃生口),此时跳过。
    """
    if os.environ.get('SR_TEST_LOG_FILE'):
        pytest.skip('逃生口开启:有意保留 test.log 文件 handler')
    managed = [
        h for h in framework_log.handlers
        if _handler_belongs_to_logger(h, framework_log)
    ]
    offenders = [
        h for h in managed
        if isinstance(h, logging.FileHandler) and not isinstance(h, logging.NullHandler)
    ]
    assert not offenders, f'pytest 进程框架日志不得落盘,发现: {offenders!r}'
    assert framework_log.name == LOGGER_NAME
