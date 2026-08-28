"""回归锁:同路径双 handler 的轮转互斥与换名后旧流强制置换。

实证背景(离线取证):跨零点换名偶发成功后,另一份仍存活的旧 handler
继续向已改名的归档文件写实时行,单文件读出「延迟数分钟的重放流混入
实时流」的错乱时间线。既有占用退避+推迟降级断掉的是「换名被占用」
主路径;本文件锁的是换名成功侧的进程内一致性:

1. 换名成功后,同路径其他 handler 的存活流必须被强制关闭置空 —— 后续
   emit 按路径重开,落到换名后的新文件,而不是继续写进归档。
2. 同路径两个 handler 的 doRollover 由路径锁串行化,不得交叠执行。
3. handler 关闭后从同路径登记表注销,不留悬挂引用。

跨进程对端的句柄在本进程内关不掉,由既有占用退避+推迟降级兜底;
本文件只锁进程内可达的部分。
"""

import logging
import os
import threading
import time
from pathlib import Path

import pytest

import one_dragon.utils.log_utils as log_utils_mod
from one_dragon.utils.log_utils import (
    SafeTimedRotatingFileHandler,
    _norm_path_key,
    _path_handlers,
)

_NT_ONLY = pytest.mark.skipif(os.name != 'nt', reason='换名句柄语义是 Windows 行为')


def _rec(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name='t', level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )


def _make_handler(path: str, delay: bool) -> SafeTimedRotatingFileHandler:
    return SafeTimedRotatingFileHandler(
        path, when='midnight', backupCount=0, encoding='utf-8', delay=delay,
    )


@_NT_ONLY
def test_rename_success_replaces_sibling_stream(tmp_path, monkeypatch) -> None:
    """换名成功 + 旧 handler 存活:旧流被强制置换,后续写落新文件而非归档。

    真实 OS 上同进程打开句柄会阻塞换名(走的是占用退避路径),这里用
    monkeypatch 注入「换名成功但旧流仍存活」的时序窗口 —— 与跨进程场景
    中对端进程在我们流关闭的窗口完成换名同型。
    """
    target = str(tmp_path / 'log.txt')
    sibling = _make_handler(target, delay=False)
    sibling.emit(_rec('from-sibling'))
    assert sibling.stream is not None and not sibling.stream.closed

    rotator = _make_handler(target, delay=True)

    def _fake_rename(src: str, dst: str) -> None:
        # 以「复制到归档名 + 假成功」重放换名:不移动源文件不影响断言,
        # 断言目标是对端 handler 的流置换行为,不是 OS 文件状态。
        Path(dst).write_bytes(Path(src).read_bytes())

    monkeypatch.setattr(log_utils_mod.os, 'rename', _fake_rename)
    try:
        rotator.rolloverAt = int(time.time())  # 强制到点
        rotator.doRollover()

        assert sibling.stream is None, '换名成功后同路径旧流必须被强制关闭置空'
        sibling.emit(_rec('post-roll'))
        assert 'post-roll' in (tmp_path / 'log.txt').read_text(encoding='utf-8'), \
            '置换后旧 handler 应按路径重开,落在新文件'
        archives = [p for p in tmp_path.iterdir() if p.name.startswith('log.txt.20')]
        assert archives, '换名应已产生归档'
        assert all('post-roll' not in p.read_text(encoding='utf-8') for p in archives), \
            '归档文件不得混入换名后的实时行(重放流)'
    finally:
        rotator.close()
        sibling.close()


@_NT_ONLY
def test_same_path_rollovers_serialized_by_path_lock(tmp_path, monkeypatch) -> None:
    """同路径两个 handler 的 doRollover 由路径锁串行:B 不得在 A 换名期间启动。"""
    target = str(tmp_path / 'log.txt')
    # 预建文件:delay=True 且从未 emit 时目标文件不存在,标准库 rotate 的
    # exists 守卫会静默跳过 rename,串行化场景无从发生。
    Path(target).write_text('current\n', encoding='utf-8')
    a = _make_handler(target, delay=True)
    b = _make_handler(target, delay=True)

    started = threading.Event()
    release = threading.Event()
    calls = {'n': 0}

    def _slow_rename(src: str, dst: str) -> None:
        # 纯观察钩子,不真实移动文件:若真的换名,第二个 handler 会撞上
        # 标准库「归档已存在 → 提前 return」分支,收不到第二次 rename 调用。
        calls['n'] += 1
        if calls['n'] == 1:
            started.set()
            assert release.wait(5.0), '测试死锁防护:换名释放事件超时'
        else:
            assert release.is_set(), '第二个换名必须等第一个完成后才能开始(路径锁)'

    monkeypatch.setattr(log_utils_mod.os, 'rename', _slow_rename)
    a_done = threading.Event()
    b_done = threading.Event()

    def _run(handler: SafeTimedRotatingFileHandler, done: threading.Event) -> None:
        try:
            handler.rolloverAt = int(time.time())
            handler.doRollover()
        finally:
            done.set()

    try:
        thread_a = threading.Thread(target=_run, args=(a, a_done))
        thread_b = threading.Thread(target=_run, args=(b, b_done))
        thread_a.start()
        assert started.wait(5.0), 'A 的换名未开始'
        thread_b.start()
        time.sleep(0.3)
        assert not b_done.is_set(), 'B 的轮转必须被路径锁挡在 A 之后'
        release.set()
        thread_a.join(5.0)
        thread_b.join(5.0)
        assert a_done.is_set() and b_done.is_set(), '两轮转都应正常完成'
        assert calls['n'] == 2, '两个 handler 都应走到各自的成功换名分支'
    finally:
        release.set()
        a.close()
        b.close()


def test_close_unregisters_from_path_registry(tmp_path) -> None:
    """handler 关闭后从同路径登记表注销:不留悬挂引用,登记表可作单写者断言面。"""
    target = str(tmp_path / 'log.txt')
    key = _norm_path_key(target)
    h1 = _make_handler(target, delay=True)
    h2 = _make_handler(target, delay=True)
    try:
        registered = _path_handlers(key)
        assert h1 in registered and h2 in registered and len(registered) == 2
    finally:
        h1.close()
    assert h1 not in _path_handlers(key)
    h2.close()
    assert _path_handlers(key) == []
