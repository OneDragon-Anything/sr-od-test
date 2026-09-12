"""cw_early_stop 哨兵主题锁(skill scripts/ 真源;v4.1 短持周期读)。

v4.1(T-77)把 watch 主循环从 tail-f 长持句柄(with 块内 while True)改为
短持周期读——病灶 = Windows 上 Python 文件句柄无 FILE_SHARE_DELETE,长持
让 kernel 寿命策略的原子改名(os.replace)恒被共享冲突拒绝(WinError 5),
purge 永不落地(2026-09-12 实测 5 轮连败)。本文件锁:

- **句柄短持(病灶机制化)**:watch 进程存活期间 journal 仍可被原子改名
  ——长持句柄回归 = 本锁红;
- **读新行端到端**:短持轮询下新追加的行照常可达,判据/报警契约不变
  (P1 出口金 < 阈值 → [EARLY-STOP-ALERT])。

测试全部走子进程真入口(操作者武装口径同形),账面/锁经 env 重定向
tmp_path,零真实 .debug/ 触碰(测试纪律 2)。
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from one_dragon.utils.file_utils import get_project_root

_SCRIPT = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
           / 'scripts' / 'cw_early_stop.py')


def _row(rid: str, plane: int, hp: int, gold: int) -> str:
    """journal 自足快照行(state.values.node.plane/hp/gold 取值链见 _parse)。"""
    return json.dumps({
        'v': 1, 'ts': datetime.now().isoformat(timespec='seconds'),
        'run_id': rid, 'row': 'write', 'field': 'gold', 'after': gold,
        'same_value': False,
        'state': {'values': {'hp': hp, 'gold': gold, 'streak': 0,
                             'node': {'plane': plane, 'round_num': 1}}},
        'sig': {}, 'note': '', 'evidence_refs': []}) + '\n'


def _spawn(journal: Path, lock: Path) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('CW_EARLYSTOP')}
    env.update({'PYTHONUTF8': '1',
                'CW_EARLYSTOP_JSONL': str(journal),
                'CW_EARLYSTOP_LOCK': str(lock)})
    return subprocess.Popen([sys.executable, str(_SCRIPT)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding='utf-8', errors='replace')


def test_watch_holds_no_long_lived_journal_handle(tmp_path: Path) -> None:
    """v4.1 病灶锁:watch 进程存活期间 journal 可被原子改名——tail-f 长持
    句柄回归(WinError 5 恒拒)时本锁红,寿命策略 purge 被永久阻塞。"""
    journal = tmp_path / 'state' / 'journal.jsonl'
    journal.parent.mkdir(parents=True)
    journal.write_text(_row('run_20260912_000001', 1, 100, 60),
                       encoding='utf-8')
    proc = _spawn(journal, tmp_path / 'earlystop.lock')
    try:
        time.sleep(2.0)   # 覆盖武装 + 至少一轮短持轮询窗
        assert proc.poll() is None, 'watch 提前退出: stdout 见 communicate'
        moved = tmp_path / 'state' / 'journal.moved.jsonl'
        os.replace(journal, moved)   # 长持句柄在场 = WinError 5 红
    finally:
        proc.terminate()
        out, _ = proc.communicate(timeout=10)
    assert '[earlystop] armed v4' in out, out


def test_watch_reads_appended_rows_alert_path(tmp_path: Path) -> None:
    """短持轮询读新行端到端:武装后追加 P1 行(出口金 30 < 50)+ P2 行 →
    P1 评估走 [EARLY-STOP-ALERT](判据/报警契约 v4.1 不变)。"""
    journal = tmp_path / 'state' / 'journal.jsonl'
    journal.parent.mkdir(parents=True)
    journal.write_text('', encoding='utf-8')
    proc = _spawn(journal, tmp_path / 'earlystop.lock')
    try:
        time.sleep(1.5)   # 武装(锚尾 = 空文件头)
        with journal.open('a', encoding='utf-8') as f:
            f.write(_row('run_20260912_000002', 1, 100, 30))
            f.write(_row('run_20260912_000002', 2, 90, 30))
        # 轮询间隔 10s,留足两轮
        deadline = time.time() + 25
        out = ''
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            time.sleep(1)
    finally:
        if proc.poll() is None:
            proc.terminate()
        out, _ = proc.communicate(timeout=10)
    assert '[EARLY-STOP-ALERT]' in out and '出口金=30' in out, out
