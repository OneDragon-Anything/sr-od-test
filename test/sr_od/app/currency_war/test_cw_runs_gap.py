"""cw_runs_gap 哨兵脚本主题锁(journal 收口断流探测,skill scripts/ 真源)。

本文件辖 skills/sr-od-currency-war-dev/scripts/cw_runs_gap.py 的干跑隔离契约:

- **SMOKE 干跑 journal 隔离(三审应修项)**:SMOKE_GAP 注入段 run_20000101_*
  恰配实机段正则 ``^run_\\d{8}_\\d{6}$``,三哨兵的实机段过滤全部采信;若写进
  现役 live journal,假 match_final 行 + 陈旧 ts 可令 cw_sentinel._run_ended()
  判「已终局」→ RUN-ENDED-IDLE 静默退出 / LOOP 报警被抑制(吞报警向量)。
  契约 = 注入必须显式 CW_RUNSGAP_JOURNAL 重定向副本,缺省/指现役一律拒绝
  (exit 2);现役账面只读消费面不变(journal 契约单一源 =
  docs/develop/sr_od/application/currency_war/game_state/journal.md)。
- 既有 SMOKE 功能回归:武装快照(SMOKE=1)与注入报警链(SMOKE_GAP=1)行为
  在重定向态下不变。

测试全部走子进程真入口(操作者武装口径同形),落盘/锁/日志信道经 env 重定向
tmp_path,零真实 .debug/ 触碰(测试纪律 2)。
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

from one_dragon.utils.file_utils import get_project_root

_SCRIPT = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
           / 'scripts' / 'cw_runs_gap.py')


def _run_gap(tmp_path: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    """以干净 CW_RUNSGAP_* 环境跑脚本真入口;锁恒重定向 tmp(不碰真实单实例锁)。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith('CW_RUNSGAP')}
    env['PYTHONUTF8'] = '1'
    env['CW_RUNSGAP_LOCK'] = str(tmp_path / 'runs_gap.lock')
    env.update(extra_env)
    return subprocess.run([sys.executable, str(_SCRIPT)], env=env,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=30)


def test_smoke_gap_default_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """守卫①缺省拒执行:SMOKE_GAP=1 未显式 CW_RUNSGAP_JOURNAL → exit 2,
    且派生缺省账面(含 REP 重定向后的 state/journal.jsonl)零写入——
    注入段恰配实机正则,落账即吞报警向量,故缺省必须硬拒而非安全兜底。"""
    live_like = tmp_path / 'telemetry' / 'live'
    r = _run_gap(tmp_path, {'CW_RUNSGAP_SMOKE_GAP': '1',
                            'CW_RUNSGAP_REP': str(live_like)})
    assert r.returncode == 2, f'缺省未拒执行: {r.stdout} {r.stderr}'
    assert '[RUNSGAP-SMOKE-GUARD]' in r.stdout
    assert 'CW_RUNSGAP_JOURNAL' in r.stdout   # 报错指引给出重定向 env 名
    assert not (live_like / 'state' / 'journal.jsonl').exists(), \
        '守卫拒执行前仍写入了派生缺省账面'


def test_smoke_gap_explicit_live_path_refuses(tmp_path: Path) -> None:
    """守卫②显式指现役拒:env 解析后 == 现役 live journal → exit 2(防复制
    粘贴把重定向指回现役)。

    单一源守卫(测试纪律 20·项目架构裁决):脚本内嵌现役根字面量必须与
    生产遥测根同址(生产根锁定 = test_cw_infra_locks.test_telemetry_roots_
    single_source)——漂移时本断言先红,禁在错位常量下继续注入验证。

    隔离哨(worktree 副本):哨兵真源按设计锚定主检出的单一 live 账面
    (脚本内嵌 _REPO 绝对字面量,操作者武装口径在主检出);worktree 副本
    内 get_project_root() 指向副本根,不是生产遥测根,根字面量守卫在
    副本态不可评估——检测到「脚本的 _REPO 字面量 ≠ 本进程仓库根」时
    诚实跳过,主检出上守卫全量在役(脚本根字面量被误删时正则落空,
    不跳过、照常走断言红)。"""
    src = _SCRIPT.read_text(encoding='utf-8')
    repo_literal = re.search(r"_REPO = Path\(r'([^']+)'\)", src)
    if repo_literal is not None and \
            Path(repo_literal.group(1)).resolve() != get_project_root().resolve():
        pytest.skip('worktree 副本:现役根字面量守卫仅在主检出可验')
    live_root = (get_project_root() / '.debug' / 'currency_war'
                 / 'telemetry' / 'live')
    assert str(live_root).lower() in src.lower(), \
        '脚本现役根字面量与生产遥测根漂移,先对齐再谈注入禁写'
    live_journal = live_root / 'state' / 'journal.jsonl'
    r = _run_gap(tmp_path, {'CW_RUNSGAP_SMOKE_GAP': '1',
                            'CW_RUNSGAP_JOURNAL': str(live_journal)})
    assert r.returncode == 2, f'显式指现役未拒执行: {r.stdout} {r.stderr}'
    assert '[RUNSGAP-SMOKE-GUARD]' in r.stdout
    assert str(live_journal) in r.stdout   # 报错回显命中路径,可定位


def test_smoke_gap_redirect_keeps_alarm_chain_green(tmp_path: Path) -> None:
    """重定向生效 + 既有注入报警链回归:显式 CW_RUNSGAP_JOURNAL 指副本时,
    SMOKE_GAP 注入只落副本,且缩窗后走完 fresh→STALL→日志静默→[RUNS-GAP]
    报警退出(过渡守卫不激活:账面预置已收口段,exit 0)。"""
    journal = tmp_path / 'journal_copy.jsonl'
    seed = {'v': 1, 'ts': datetime.now().isoformat(),
            'run_id': 'run_20260912_000001', 'row': 'write',
            'field': 'match_final', 'after': 1, 'same_value': False,
            'state': {'values': {}}, 'sig': {}, 'note': '',
            'evidence_refs': []}
    journal.write_text(json.dumps(seed) + '\n', encoding='utf-8')
    aged_log = tmp_path / 'aged.log'
    aged_log.write_text('', encoding='utf-8')
    old = time.time() - 3600
    os.utime(aged_log, (old, old))   # 日志信道陈旧 → 静默闸恒开,报警路径可达
    r = _run_gap(tmp_path, {
        'CW_RUNSGAP_SMOKE_GAP': '1',
        'CW_RUNSGAP_JOURNAL': str(journal),
        'CW_RUNSGAP_LOG': str(aged_log),
        'CW_RUNSGAP_INTERVAL': '0.3',
        'CW_RUNSGAP_STALL': '0',
        'CW_RUNSGAP_LOG_AGE': '5',
    })
    assert r.returncode == 0, f'报警链未按预期退出: {r.stdout} {r.stderr}'
    assert '[RUNS-GAP]' in r.stdout
    rows = [json.loads(ln) for ln
            in journal.read_text(encoding='utf-8').splitlines() if ln.strip()]
    rids = [row['run_id'] for row in rows]
    assert rids[-1] == 'run_20000101_000000', rids   # 注入段(gold,未收口)在副本尾
    assert rids.count('run_20000101_000000') == 1    # 注入恰一次,无重放


def test_smoke_arm_snapshot_exits_clean(tmp_path: Path) -> None:
    """既有 SMOKE=1 武装快照回归:武装打印后即退(exit 0),快照干跑对
    重定向账面零写入。"""
    journal = tmp_path / 'journal_copy.jsonl'
    journal.write_text('', encoding='utf-8')
    r = _run_gap(tmp_path, {'CW_RUNSGAP_SMOKE': '1',
                            'CW_RUNSGAP_JOURNAL': str(journal)})
    assert r.returncode == 0, f'SMOKE 快照干跑非零退出: {r.stdout} {r.stderr}'
    assert '[runsgap] armed' in r.stdout
    assert str(journal) in r.stdout   # 武装回显消费账面 = 重定向副本
    assert journal.read_text(encoding='utf-8') == ''   # 快照干跑零写入
