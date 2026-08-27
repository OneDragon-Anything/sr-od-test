"""回归锁:SafeTimedRotatingFileHandler 轮转占用路径的两个残留缺陷(W360)。

背景:.debug/sr_od_mcp/main_server.log 里 3149 条 WinError 32 轮转失败的
traceback,栈里没有 log_utils 帧、目标归档名恒为 ``.2026-08-25`` —— 证明
肇事进程跑的是标准库 handler(失败时 ``rolloverAt`` 不推进 → 每条日志重试
换名,重试窗口内换名偶发成功会把其他写入流甩进已改名归档,离线读出
"延迟重放流混入实时流"的错乱时间线)。SafeTimedRotatingFileHandler 的
退避+推迟已断主路径;本文件锁它自身的两个残留占用路径:

1. 换名成功、但其后的旧归档清理(os.remove 撞外部句柄)被占用 → 必须视作
   轮转完成只推进时点;若按占用重试,会对已不存在的源文件再 rename,
   抛 FileNotFoundError 逃逸,handler 停在流空+时点过期态(丢日志风暴)。
2. 全败降级重开流时,并发 emit 可能已在重试期间重开流 → 必须守卫,
   否则同进程出现两个写句柄(与跨进程双写同症状)。

判定标准:两路径都不抛异常、时点推进、且全程单流单归档。
"""

import logging
import os
import time
from contextlib import suppress

import pytest

from one_dragon.utils.log_utils import (
    _ROTATE_RETRY_COUNT,
    SafeTimedRotatingFileHandler,
)

_NT_ONLY = pytest.mark.skipif(os.name != 'nt', reason='rename/删除占用报错是 Windows 行为')


def _make_holder(path: str):
    """保持打开句柄的持有者(与被测 handler 不同进程同型:句柄即阻塞源)。"""
    holder = logging.handlers.TimedRotatingFileHandler(
        path, when='midnight', backupCount=0, encoding='utf-8',
    )
    holder.stream.write('held\n')
    holder.stream.flush()
    return holder


@_NT_ONLY
def test_rename_succeeded_cleanup_blocked_completes_rollover(tmp_path) -> None:
    """换名成功但旧归档删除被占用:不抛、时点推进、流交 emit 惰性重开。"""
    target = str(tmp_path / 'log.txt')
    with open(target, 'w', encoding='utf-8') as f:
        f.write('current\n')
    # 两个旧归档:新者会被清理成功,旧者被外部句柄占住 → 删除撞 WinError 32
    (tmp_path / 'log.txt.2020-01-02').write_text('old2\n', encoding='utf-8')
    blocked = (tmp_path / 'log.txt.2020-01-01').open('w', encoding='utf-8')
    try:
        blocked.write('blocked\n')
        blocked.flush()

        handler = SafeTimedRotatingFileHandler(
            target, when='midnight', backupCount=1, encoding='utf-8', delay=True,
        )
        try:
            handler.rolloverAt = int(time.time())  # 强制到点
            handler.doRollover()  # 修前:FileNotFoundError 逃逸

            archives = sorted(p.name for p in tmp_path.iterdir()
                              if p.name.startswith('log.txt.20'))
            assert any(a.startswith('log.txt.2') and a != 'log.txt.2020-01-01'
                       and a != 'log.txt.2020-01-02' for a in archives), \
                f'换名应已产生今日归档: {archives}'
            assert handler.rolloverAt > time.time(), '应视作完成并推进轮转时点'
            assert handler.stream is None, 'delay=True 时流应交由 emit 惰性重开'
        finally:
            handler.close()
    finally:
        blocked.close()


@_NT_ONLY
def test_defer_reopen_guard_keeps_live_stream(tmp_path, monkeypatch) -> None:
    """全败降级时若并发 emit 已重开流,降级路径不得把它替换成第二个句柄。"""
    target = str(tmp_path / 'log.txt')
    holder = _make_holder(target)
    handler = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )

    import one_dragon.utils.log_utils as log_utils_mod

    live = None
    calls = {'n': 0}
    real_rename = os.rename

    def _rename_then_concurrent_reopen(src: str, dst: str):
        # 模拟并发窗口:在【最后一次】super().doRollover 的 rename 失败返回、
        # 降级重开执行之前,另一线程 emit → shouldRollover 因流为 None 重开流。
        # (更早窗口的重开会被下一次 super().doRollover 入口关流关掉,那是基类
        # 契约,不是降级守卫要管的窗口。)
        nonlocal live
        calls['n'] += 1
        try:
            return real_rename(src, dst)
        finally:
            if calls['n'] == _ROTATE_RETRY_COUNT and handler.stream is None:
                live = handler._open()
                handler.stream = live

    monkeypatch.setattr(log_utils_mod.os, 'rename', _rename_then_concurrent_reopen)
    try:
        handler.rolloverAt = int(time.time())  # 强制到点
        handler.doRollover()  # 换名被 holder 阻塞,重试全败走降级

        assert live is not None, '前置失效:退避期间应已发生并发重开'
        assert handler.stream is live, '降级必须保留并发重开的活流,不得另开第二句柄'
        assert not live.closed
        assert handler.rolloverAt > time.time(), '全败后应推迟下一个轮转时点'
        assert not any(p.name.startswith('log.txt.') for p in tmp_path.iterdir()), \
            '被占用期间不得产生归档(换了名就会把活流甩进改名文件)'
    finally:
        handler.close()
        holder.close()


@_NT_ONLY
def test_double_rollover_occupied_then_free_single_stream(tmp_path) -> None:
    """跨零点场景:第一次轮转被占用降级续写旧文件,释放后第二次轮转成功
    —— 全程单 handler、单归档、流唯一。"""
    target = str(tmp_path / 'log.txt')
    holder = _make_holder(target)
    handler = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )
    try:
        # 第一次到点:被占用 → 降级
        handler.rolloverAt = int(time.time())
        handler.doRollover()
        assert handler.rolloverAt > time.time()
        assert not any(p.name.startswith('log.txt.') for p in tmp_path.iterdir())

        # 占用释放,冷却期后再到点:轮转成功
        holder.close()
        handler.rolloverAt = int(time.time())
        handler.doRollover()

        archives = [p.name for p in tmp_path.iterdir() if p.name.startswith('log.txt.20')]
        assert len(archives) == 1, f'两次轮转后应恰有一个归档: {archives}'
        # delay=True:轮转后流为 None,经正常 emit 路径惰性重开并落盘(单流验证)
        handler.emit(logging.LogRecord(
            name='t', level=logging.INFO, pathname=__file__, lineno=1,
            msg='post-second', args=(), exc_info=None,
        ))
        assert handler.stream is not None and not handler.stream.closed
        assert 'post-second' in (tmp_path / 'log.txt').read_text(encoding='utf-8')
    finally:
        handler.close()
        with suppress(Exception):
            holder.close()
