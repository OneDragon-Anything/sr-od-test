"""runs 流局终收口退役锁(删除波 1;用户 2026-09-10 直迁裁定)。

本文件原锁 runs.jsonl 局终汇总多路径兜底(ADR-0273,批⑧ F2)。删除波 1:
runs 流 = 收编 9 流之一,写入端(正常局终/收口补写/崩溃兜底回填)整段
退役;runs.jsonl 冻结为存量语料,读侧检查(check_summary_write_path_
coverage)继续可判存量档案。锁语义重推(锁的存在性纪律:锁红 ≠ 改动错,
旧锁钉的是已退役语义,随裁定重写):

- recover_dangling_run_summaries = no-op 兼容桩(恒空表,零写行);
- 局终收口位(telemetry.state.close_run)零落盘,只置跨局 run_id 重铸位;
- start_run(经 ensure_run_started)不再触发兜底回填,不产任何 runs 行;
- 读侧检查项双向对存量档案仍可判(缺行 ⚠ 带 run_id / 全覆盖 ✓)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.sim.ledger_hooks import (
    check_summary_write_path_coverage,
    recover_dangling_run_summaries,
)
from sr_od.application.currency_war.telemetry import state as tel_state
from sr_od.application.currency_war.telemetry.query import read_jsonl


@pytest.fixture()
def _run_lifecycle(tmp_path):
    """落盘根指 tmp + journal 不装(本文件不涉账本);teardown 复位。"""
    tel_state.set_recorder_replay_dir(tmp_path / 'replay')
    tel_state.reset_run_state()
    yield tmp_path / 'replay'
    tel_state.reset_run_state()
    tel_state.set_recorder_replay_dir(None)


def _write(path: Path, rows: list[dict]) -> None:
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def test_recover_is_retired_noop(tmp_path) -> None:
    """兜底回填 = 退役 no-op 桩:任何存量档案形态都不再补行(零写端)。"""
    d = tmp_path / 'replay'
    d.mkdir(parents=True)
    _write(d / 'outcomes.jsonl', [
        {'run_id': 'rDangle', 'plane': 1, 'round_num': 1, 'hp_after': 80,
         'hp_confidence': 1.0, 'ts': '2026-08-24T00:01:00'}])
    assert recover_dangling_run_summaries(d) == []
    assert not (d / 'runs.jsonl').exists(), '退役桩不得写 runs 行'
    assert not hasattr(ledger_hooks, 'build_recovered_summary'), \
        '重算器已随 runs 写入端删除(防半删)'
    assert not hasattr(ledger_hooks, '_regenerate_delta_pool_after_run'), \
        'Δ池局终自动再生触发已随 runs 写入端删除(池再生本体保留手动/sim 批口)'


def test_start_run_produces_zero_runs_rows(_run_lifecycle) -> None:
    """start_run(局起点)不再触发兜底回填:有悬空存量局也不写 runs 行。"""
    d = _run_lifecycle
    d.mkdir(parents=True, exist_ok=True)
    _write(d / 'outcomes.jsonl', [
        {'run_id': 'rOld', 'plane': 1, 'round_num': 1, 'hp_after': 80,
         'hp_confidence': 1.0, 'ts': '2026-08-24T00:01:00'}])
    rid = tel_state.ensure_run_started(object(), 'mandate_v1')
    assert rid
    assert not (d / 'runs.jsonl').exists(), '局起点零 runs 产出(写入端已退役)'


def test_close_run_sets_marker_without_writing(_run_lifecycle,
                                               monkeypatch) -> None:
    """close_run = 收口位:置 _RUN_CLOSED 驱动跨局重铸,零文件产出。"""
    d = _run_lifecycle
    d.mkdir(parents=True, exist_ok=True)
    match = object()
    rid1 = tel_state.ensure_run_started(match, 'mandate_v1')
    tel_state.close_run(result='win', plane_reached=3, rounds_survived=9,
                        final_hp=88, notes='auto')
    assert tel_state._RUN_CLOSED is True, '收口位在(跨局重铸承接口)'
    assert not (d / 'runs.jsonl').exists(), '收口零落盘(runs 写入端已退役)'

    # run_id = 秒级时间戳:推进假时钟使两次铸造不同秒(证明重铸,非同 id 复用)
    import datetime as _dt

    class _FakeDt:
        _cur = _dt.datetime(2026, 9, 10, 23, 0, 0)

        @classmethod
        def now(cls):
            cls._cur = cls._cur + _dt.timedelta(seconds=1)
            return cls._cur

    monkeypatch.setattr(tel_state, 'datetime', _FakeDt)
    rid2 = tel_state.ensure_run_started(match, 'mandate_v1')
    assert rid2 != rid1, '收口后下一局重铸新段(journal 行归属承接口)'


def test_coverage_check_still_judges_frozen_archive(tmp_path) -> None:
    """读侧检查项对存量档案双向可判:缺行 ⚠ 带 run_id;补齐(历史档案形态)✓。"""
    d = tmp_path / 'replay'
    d.mkdir(parents=True)
    _write(d / 'outcomes.jsonl', [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1, 'hp_after': 90,
         'hp_confidence': 1.0, 'ts': '2026-08-24T00:01:00'},
        {'run_id': 'r2', 'plane': 1, 'round_num': 1, 'hp_after': 80,
         'hp_confidence': 1.0, 'ts': '2026-08-24T00:02:00'},
    ])
    out = check_summary_write_path_coverage(d)
    assert len(out) == 1 and '⚠' in out[0] and 'r1' in out[0] and 'r2' in out[0]
    # 存量档案补上 summary 行(模拟冻结语料的完整形态)→ ✓
    _write(d / 'runs.jsonl', [
        {'run_id': 'r1', 'result': 'loss'}, {'run_id': 'r2', 'result': 'loss'}])
    out = check_summary_write_path_coverage(d)
    assert len(out) == 1 and '✓' in out[0] and '100%' in out[0]
    assert len(read_jsonl(d / 'runs.jsonl')) == 2
