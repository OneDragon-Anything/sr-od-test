"""T-113(ADR-0579)op_journal 薄流测试:逐动作回执行/非决策 op 行/守卫族。

锁面与方案对齐(.debug/temp/currency_war/t112_deep_telemetry/方案.md):
- flatten_diff 全量叶级 diff 零漏报(投影外真实变化必现)+ 对称差/列表整替/截断分型;
- record_action_journal 行形态(seq/frame_seq/gold/exec_ok/expected_delta);
- run_id 门控(局外零行)+ 行帽截断 _trunc;行数不设上限
  (原每局 500 行软上限已由用户裁定 2026-09-07 删除,墓碑锁钉退役面);
- 非决策 op enter/exit 成对 + 装配端孤儿 enter 行 outcome='orphan' 容缺;
- 守卫:①_telemetry_last_candidate_scores 命中点计数锁(src 树恰 3 文件,
  声明/写点/读点,第 4 文件=红);②op_journal 键族禁入 decisions 写路径。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame, LevelUp
from sr_od.application.currency_war.telemetry import op_journal
from sr_od.application.currency_war.telemetry.match_archive import (
    _annotate_orphan_op_rows,
)


@pytest.fixture()
def journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """journal 落盘重定向 tmp_path + 局外态复位(测试纪律 1/2)。"""
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(op_journal, '_JOURNAL', out)
    monkeypatch.setattr(op_journal, '_frame_seq_by_run', {})
    monkeypatch.setattr(op_journal, 'current_run_id', lambda: 'run_test')
    return out


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]


def test_flatten_diff_full_leaf_coverage():
    """全量展平叶级 diff 零漏报:投影外真实变化(任意叶)必现 delta。"""
    before = {'gold': 10, 'deployed': [{'slot': 1}], 'nested': {'a': 1, 'b': 2}}
    after = {'gold': 14, 'deployed': [{'slot': 1}], 'nested': {'a': 1, 'b': 9}}
    delta = op_journal.flatten_diff(before, after, cap=12)
    assert delta == {'~gold': 14, '~nested.b': 9}


def test_flatten_diff_symmetric_and_trunc():
    """对称差(-/+)语义 + 超帽截断置 _trunc(读端分型依据)。"""
    delta = op_journal.flatten_diff({'gone': 1, 'keep': 2},
                                    {'new': 3, 'keep': 2}, cap=1)
    assert '_trunc' in delta
    full = op_journal.flatten_diff({'gone': 1}, {'new': 3}, cap=100)
    assert full == {'-gone': 1, '+new': 3}
    # 列表叶 = 整列表替换计一条(不逐元素对位)
    lst = op_journal.flatten_diff({'l': [1, 2]}, {'l': [1, 3]}, cap=10)
    assert lst == {'~l': [1, 3]}


def test_action_row_shape_and_frame_seq(journal: Path):
    """动作行:seq/frame_seq/exec_ok/gold/expected_delta 全落;段序推进生效。"""
    assert op_journal.advance_frame_seq() == 1
    pre = CwWorkFrame(plane=2, round_num=3, gold=10)
    post = CwWorkFrame(plane=2, round_num=3, gold=6)
    op_journal.record_action_journal(
        match=None, action=LevelUp(cost=4), seq=2, exec_ok=True,
        pre_frame=pre, post_frame=post)
    rows = _rows(journal)
    assert len(rows) == 1
    r = rows[0]
    assert r['kind'] == 'action' and r['seq'] == 2
    assert r['frame_seq'] == 1 and r['exec_ok'] is True
    assert r['gold'] == 6 and r['run_id'] == 'run_test'
    assert any(k.startswith('~') for k in r['expected_delta'])


def test_no_run_id_writes_nothing(tmp_path: Path, monkeypatch):
    """局外门控:run_id 空 → 零行(obs_conflict 同规,不写假键)。"""
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(op_journal, '_JOURNAL', out)
    monkeypatch.setattr(op_journal, '_frame_seq_by_run', {})
    monkeypatch.setattr(op_journal, 'current_run_id', lambda: '')
    op_journal.record_action_journal(None, LevelUp(cost=4), 1, True,
                                     CwWorkFrame(), CwWorkFrame())
    assert op_journal.record_op_enter('战斗等待', 1, 1) is None
    assert not out.exists()


def test_row_count_soft_cap_retired():
    """墓碑(退役背书):每局行数软上限已整条删除(用户裁定 2026-09-07)。

    为什么删:病态决策循环的停线防护由哨兵层 STALL/LOOP 承接;journal
    静默触顶停写 = 长局尾段 op 行无感丢失,复盘盲区代价(T-121 深局
    实测单 run 690 行越旧顶)远大于流体积风险。删除面 = 模块常量
    _MATCH_ROWS_SOFT_CAP 与 _row_counts 计数表;复活任一 = 红。
    """
    assert not hasattr(op_journal, '_MATCH_ROWS_SOFT_CAP')
    assert not hasattr(op_journal, '_row_counts')


def test_row_cap_truncates(journal: Path, monkeypatch):
    """行帽截断:delta 超 12 条 → 精简行 + _trunc 分型标记。"""
    monkeypatch.setattr(op_journal, '_ROW_CAP', 200)
    pre = CwWorkFrame()
    post = CwWorkFrame(plane=1, round_num=1, gold=5, hp=90, level=3)
    op_journal.record_action_journal(None, LevelUp(cost=4), 1, True,
                                     pre, post)
    rows = _rows(journal)
    assert len(rows) == 1 and rows[0].get('_trunc') is True
    assert 'expected_delta' not in rows[0]


def test_op_enter_exit_pair_and_orphan(journal: Path):
    """非决策 op 成对行;装配端孤儿 enter 行 outcome='orphan' 容缺。"""
    tok = op_journal.record_op_enter('位面过渡', 2, 5)
    op_journal.record_op_exit(tok, outcome='ok')
    tok2 = op_journal.record_op_enter('战斗等待', 2, 6)
    rows = _rows(journal)
    assert [r['event'] for r in rows if r['kind'] == 'op'] == \
        ['enter', 'exit', 'enter']
    # 装配端:无 exit 配对的 enter 行 → orphan;已配对行不动
    _annotate_orphan_op_rows(rows)
    by_event = [(r['event'], r.get('outcome')) for r in rows
                if r['kind'] == 'op']
    assert by_event == [('enter', None), ('exit', 'ok'), ('enter', 'orphan')]
    assert tok2 is not None


# ===== 守卫族(ADR-0571 §2.3 范式)=====

_SRC = Path(__file__).resolve().parents[5] / 'src' / 'sr_od'


def test_telemetry_field_hit_count_lock():
    """命中点计数锁(删除波 1 重写):基名 `_telemetry_last_candidate_scores`
    的生产树命中收缩到 mandate_state.py 单文件(字段载体禁碰面,候其归属
    批清理);写入点(flow.py 供数块)与读点(店内决策行披露构造)已随
    decisions 流写入端退役删除。命中重新扩散 = 有代码开始消费死字段,锁红。"""
    hits = {p.name for p in _SRC.rglob('*.py')
            if '_telemetry_last_candidate_scores' in p.read_text(encoding='utf-8')}
    assert hits == {'mandate_state.py'}, (
        f'死遥测字段命中面漂移:{hits}(写点/读点已退役,禁复活)')


def test_op_journal_keys_confined():
    """键族禁入 decisions 写路径:'expected_delta' 在 src 只允许出现在
    op_journal 模块本体与 match_archive 装配/切片;出现他处 = 红线破。"""
    allowed = {'op_journal.py', 'match_archive.py'}
    leaks = {p.name for p in _SRC.rglob('*.py')
             if 'expected_delta' in p.read_text(encoding='utf-8')}
    assert leaks <= allowed
