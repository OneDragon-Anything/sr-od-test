"""回归锁:SafeTimedRotatingFileHandler 轮转占用的 copytruncate 兜底。

背景(W456,WinError 32 五度实证的终点修):
rename 是 Windows 上唯一要求「目标文件无任何打开句柄」的操作 —— 任何外部
进程(哨兵尾随/日志查看器)在午夜轮转瞬间哪怕只持一个**只读句柄**,标准库
``TimedRotatingFileHandler.rotate`` 的 ``os.rename`` 都必然失败。2026-08-26
的丢失事故里,持有者=旧版哨兵脚本长持的尾随句柄(v3.8 已改短开轮询),肇事
handler=当时的标准库实现(无兜底,rolloverAt 不推进 → 整天每条日志重试、
失败行只以无时间戳 dump 落 stderr,整批永久丢失)。

本文件锁兜底行为本身:
1. rename 被只读句柄挡住 → copytruncate 当场完成归档:归档含全部旧内容、
   当前文件被截空、后续日志继续写当前文件(数据零丢失)。
2. 只读持有者的句柄在兜底后仍可从头读归档(观察者不被破坏)。
3. rename 与 copytruncate 均被阻断 → 走推迟降级(数据不丢、不产生半截归档)。

判定标准:三路径都不抛异常、归档内容与写入流一一对应。
"""

import logging
import os
import time
from contextlib import suppress

import pytest

from one_dragon.utils.log_utils import SafeTimedRotatingFileHandler

_NT_ONLY = pytest.mark.skipif(os.name != 'nt', reason='rename 占用报错是 Windows 行为')


@_NT_ONLY
def test_rename_blocked_by_read_holder_falls_back_to_copytruncate(tmp_path) -> None:
    """只读句柄挡 rename:copytruncate 当场归档全部内容,当前文件截空续写。"""
    target = str(tmp_path / 'log.txt')
    with open(target, 'w', encoding='utf-8') as f:
        f.write('line-1\nline-2\n')
    # 只读长持句柄 = 哨兵尾随/日志查看器的形状(读写打开互不阻塞 rename 才是旧症结)
    holder = open(target, 'rb')  # noqa: SIM115 刻意长持:被测对象就是「外部持有者」
    handler = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )
    try:
        handler.rolloverAt = int(time.time())  # 强制到点
        handler.doRollover()

        archives = [p.name for p in tmp_path.iterdir() if p.name.startswith('log.txt.2')]
        assert len(archives) == 1, f'兜底应产生恰一个归档: {archives}'
        assert (tmp_path / archives[0]).read_text(encoding='utf-8') == 'line-1\nline-2\n', \
            '归档必须携带占用时刻的全部内容'
        assert (tmp_path / 'log.txt').stat().st_size == 0, '当前文件应被截空'
        assert handler.rolloverAt > time.time(), '兜底成功视作轮转完成,时点正常推进'

        # 后续日志继续写当前文件(delay=True → emit 惰性重开)
        handler.emit(logging.LogRecord(
            name='t', level=logging.INFO, pathname=__file__, lineno=1,
            msg='post-rotate', args=(), exc_info=None,
        ))
        assert 'post-rotate' in (tmp_path / 'log.txt').read_text(encoding='utf-8')

        # 观察者句柄不坏:持有者从 0 读归档名仍能拿到完整旧内容(经归档路径)
        holder.close()
        reopened = open(tmp_path / archives[0], 'rb')  # noqa: SIM115 测试内短持
        try:
            assert b'line-1' in reopened.read()
        finally:
            reopened.close()
    finally:
        handler.close()
        with suppress(Exception):
            holder.close()


@_NT_ONLY
def test_copytruncate_and_rename_both_blocked_defers_without_archive(tmp_path, monkeypatch) -> None:
    """rename 与兜底复制都被阻断:推迟降级,不产生半截归档,数据不丢。"""
    target = str(tmp_path / 'log.txt')
    with open(target, 'w', encoding='utf-8') as f:
        f.write('precious\n')
    holder = open(target, 'rb')  # noqa: SIM115 刻意长持:被测对象就是「外部持有者」

    import one_dragon.utils.log_utils as log_utils_mod

    def _blocked(*_args, **_kwargs):
        raise PermissionError(13, '模拟归档名也被占用')

    monkeypatch.setattr(log_utils_mod.shutil, 'copyfile', _blocked)
    handler = SafeTimedRotatingFileHandler(
        target, when='midnight', backupCount=3, encoding='utf-8', delay=True,
    )
    try:
        handler.rolloverAt = int(time.time())
        handler.doRollover()

        assert not any(p.name.startswith('log.txt.2') for p in tmp_path.iterdir()), \
            '兜底失败时不得留下半截归档'
        assert handler.rolloverAt > time.time(), '应推迟到冷却期后再试'
        assert (tmp_path / 'log.txt').read_text(encoding='utf-8') == 'precious\n', \
            '降级路径数据必须原样保留'
    finally:
        handler.close()
        with suppress(Exception):
            holder.close()
