"""跨进程窗口运行锁机制测试(one_dragon.base.operation.window_run_mutex)。

覆盖三个面:
1. 互斥语义:空闲可取、他方持锁拒绝(Windows 字节区间锁按句柄冲突,同进程
   不同句柄同样互斥,锁语义与跨进程一致)、释放后可再入;
2. 占用描述与探测:acquire 失败记录占用者(pid)、probe 空闲返 None / 被占返描述;
3. 真·跨进程证明:子进程持锁期间父进程拒绝,子进程退出(锁由操作系统回收)
   后父进程可再入——这是「锁文件 + 区间锁」根治双进程交替操作的直接验收。

设计出处见模块 docstring(2026-08-24 双进程交替操作事故,T-59 根治)。
测试经根 conftest 的 ``_isolate_window_run_mutex`` 把锁目录重定向到 tmp;
子进程不继承 monkeypatch,故跨进程用例把锁目录经 argv 显式传给子进程。
"""

import os
import subprocess
import sys
from pathlib import Path

from one_dragon.base.operation import window_run_mutex
from one_dragon.base.operation.window_run_mutex import (
    DEFAULT_LOCK_KEY,
    WindowRunMutex,
    probe_window_occupancy,
    resolve_lock_key,
    sanitize_lock_key,
)


def _make_mutex(tmp_path: Path, key: str = 'k1') -> WindowRunMutex:
    """构造指向 tmp 锁域的锁实例(每次新实例 = 每次新句柄)。"""
    return WindowRunMutex(tmp_path / 'run_mutex', key)


def test_acquire_free_then_conflict_then_reacquire(tmp_path: Path) -> None:
    """互斥三段:空闲可取 → 他方句柄拒绝 → 释放后可再入(T-59 验收判据)。"""
    first = _make_mutex(tmp_path)
    assert first.acquire() is True

    second = _make_mutex(tmp_path)
    assert second.acquire() is False                      # 他方持锁,拒绝
    assert second.is_holding is False
    desc = second.other_holder_description()
    assert desc is not None and f'pid={os.getpid()}' in desc

    first.release()                                       # 释放后可再入
    assert second.acquire() is True
    second.release()


def test_release_is_idempotent(tmp_path: Path) -> None:
    """未持有/重复释放均为幂等 no-op,不抛异常。"""
    mutex = _make_mutex(tmp_path)
    mutex.release()                                       # 未持有释放 = no-op
    mutex.acquire()
    mutex.release()
    mutex.release()                                       # 重复释放 = no-op
    assert mutex.is_holding is False


def test_probe_reports_none_when_free_and_desc_when_held(tmp_path: Path) -> None:
    """探测:空闲返 None;被占返占用者描述(不改变锁的持有状态)。"""
    lock_dir = tmp_path / 'run_mutex'
    assert probe_window_occupancy(lock_dir, 'k1') is None

    holder = WindowRunMutex(lock_dir, 'k1', owner_source='测试源')
    assert holder.acquire() is True
    try:
        desc = probe_window_occupancy(lock_dir, 'k1')
        assert desc is not None
        assert 'pid=' in desc and '测试源' in desc
    finally:
        holder.release()
    assert probe_window_occupancy(lock_dir, 'k1') is None


def test_sanitize_lock_key_handles_illegal_chars_and_empty() -> None:
    """键净化:非法字符替换、同标题同键(跨进程一致)、异标题异键、空回退默认。"""
    key = sanitize_lock_key('崩坏:星穹铁道')
    assert ':' not in key
    assert key == sanitize_lock_key('崩坏:星穹铁道')
    assert key != sanitize_lock_key('崩坏_星穹铁道')
    assert sanitize_lock_key(None) == DEFAULT_LOCK_KEY
    assert sanitize_lock_key('') == DEFAULT_LOCK_KEY


def test_resolve_lock_key_from_controller_title() -> None:
    """键从控制器窗口标题推导;标题缺失/非字符串(测试替身)回退默认键。"""

    class _GameWin:
        win_title = '崩坏:星穹铁道'

    class _Controller:
        game_win = _GameWin()

    assert resolve_lock_key(_Controller()) == sanitize_lock_key('崩坏:星穹铁道')
    assert resolve_lock_key(object()) == DEFAULT_LOCK_KEY

    class _EmptyWin:
        win_title = None

    class _EmptyController:
        game_win = _EmptyWin()

    assert resolve_lock_key(_EmptyController()) == DEFAULT_LOCK_KEY


_CHILD_HOLD_SECONDS = 0.7

# 子进程脚本:取得锁后打印 LOCK_OK(父进程以此同步),持锁一段时间后退出
# (不显式释放——正是要验证持有进程消失后操作系统自动回收锁)。argv:
# [锁目录, 锁键, src 根路径(供子进程 import one_dragon), 持锁秒数]
_CHILD_SCRIPT = """\
import sys
import time
sys.path.insert(0, sys.argv[3])
from one_dragon.base.operation.window_run_mutex import WindowRunMutex

mutex = WindowRunMutex(sys.argv[1], sys.argv[2], owner_source='子进程')
if not mutex.acquire():
    print('LOCK_FAIL')
    sys.exit(1)
print('LOCK_OK', flush=True)
time.sleep(float(sys.argv[4]))
"""


def test_cross_process_mutex_and_auto_release(tmp_path: Path) -> None:
    """真·跨进程证明:子进程持锁期父进程拒绝;子进程退出后可再入。

    慢桶(2026-09-12 补办流程):本用例是全文件唯一跨进程用例,子进程
    冷启(python 解释器 + import one_dragon)不可省——``window_run_mutex``
    依赖 ``one_dragon.utils``,无法单文件加载;``_CHILD_HOLD_SECONDS``
    是「父进程拒绝检查先行于子进程退出」的安全边际,压小 = 拒绝断言
    假绿风险,不降。实测:热跑 call 0.86s,冷启/高载场景显著上浮
    (全子进程冷启形态,与既有真帧/OCR 重锁同桶);已按实测入
    slow_marks.txt,快速层跳过、全量仍跑。
    """
    # window_run_mutex.py → operation/ → base/ → one_dragon/ → src/
    src_root = str(Path(window_run_mutex.__file__).resolve().parents[3])
    lock_dir = str(tmp_path / 'run_mutex')
    child = subprocess.Popen(  # noqa: S603 固定 argv,无外部输入
        [sys.executable, '-c', _CHILD_SCRIPT, lock_dir, 'cross', src_root,
         str(_CHILD_HOLD_SECONDS)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        # 与子进程同步:读到 LOCK_OK 才说明持锁已成立(不靠固定 sleep)。
        # 逐行读到 LOCK_OK 或流结束——失败时把子进程完整输出带回断言消息。
        assert child.stdout is not None
        lines: list[str] = []
        while True:
            raw = child.stdout.readline()
            if not raw:
                break
            line = raw.decode('utf-8', errors='replace').rstrip()
            lines.append(line)
            if 'LOCK_OK' in line:
                break
        assert any('LOCK_OK' in ln for ln in lines), \
            f'子进程未成功持锁,输出: {lines!r}'

        refused = WindowRunMutex(Path(lock_dir), 'cross').acquire()
        assert refused is False                           # 跨进程占用 → 拒绝

        child.wait(timeout=10)                            # 子进程退出(未显式释放)
        reacquire = WindowRunMutex(Path(lock_dir), 'cross')
        assert reacquire.acquire() is True                # 系统回收锁 → 可再入
        reacquire.release()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
