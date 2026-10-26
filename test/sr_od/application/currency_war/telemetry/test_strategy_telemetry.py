"""策略遥测落盘 sink 锁面(run_id 补齐 / 局外零写 / 句柄缓存键含根)。

被测 = src/sr_od/application/currency_war/telemetry/strategy_telemetry.py;
设计出处 = changes/2026-10-24-strategy-telemetry/details/capture-store.md §4。
测试零真实副作用:recorder 根重定向 tmp_path,teardown 收句柄复位槽。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.telemetry import strategy_telemetry as st
from sr_od.application.currency_war.telemetry.state import (
    current_run_id,
    reset_run_state,
    set_recorder_replay_dir,
    start_run,
)


def _record(strategy_id: str = 's_test', dseq: int = 1) -> dict:
    """信封不含 run_id 的最小记录(wrapper 交付形态;补齐归 sink)。"""
    return {'envelope': {'strategy_id': strategy_id, 'dseq': dseq,
                         'dtag': f'{strategy_id}:{dseq}'},
            'payload': {}}


def _strategy_file(root: Path, strategy_id: str, run_id: str) -> Path:
    return root / 'strategy' / f'{strategy_id}_{run_id}.jsonl'


@pytest.fixture
def telemetry_root(tmp_path: Path):
    """recorder 根重定向 tmp + 开局(run 态簇前后复位,防模块级残留)。"""
    reset_run_state()
    set_recorder_replay_dir(tmp_path)
    start_run()
    yield tmp_path
    st.close_strategy_telemetry_handles()
    set_recorder_replay_dir(None)
    reset_run_state()


def test_outside_run_zero_write(tmp_path: Path) -> None:
    """局外(run_id 空)= 零写:连 strategy/ 目录都不建(回执域同语义)。"""
    reset_run_state()
    set_recorder_replay_dir(tmp_path)
    try:
        assert current_run_id() == ''
        st.strategy_telemetry_sink(_record())
        assert not (tmp_path / 'strategy').exists()
    finally:
        st.close_strategy_telemetry_handles()
        set_recorder_replay_dir(None)
        reset_run_state()


def test_run_id_filled_and_appended(telemetry_root: Path) -> None:
    """sink 补 envelope.run_id 并追加到 <strategy_id>_<run_id>.jsonl,
    多次调用同文件追加(逐行自足)。"""
    run_id = current_run_id()
    st.strategy_telemetry_sink(_record(dseq=1))
    st.strategy_telemetry_sink(_record(dseq=2))
    f = _strategy_file(telemetry_root, 's_test', run_id)
    rows = [json.loads(line)
            for line in f.read_text(encoding='utf-8').splitlines()]
    assert [r['envelope']['dseq'] for r in rows] == [1, 2]
    assert all(r['envelope']['run_id'] == run_id for r in rows)


def test_handle_cache_follows_root_redirect(telemetry_root: Path) -> None:
    """句柄缓存键含 recorder 根:换根后落新根文件,旧根零追加
    (换根重建单例语义对齐 set_recorder_replay_dir)。"""
    run_id = current_run_id()
    st.strategy_telemetry_sink(_record())
    new_root = telemetry_root / 'redirected'
    set_recorder_replay_dir(new_root)
    try:
        st.strategy_telemetry_sink(_record(dseq=2))
        old_rows = (_strategy_file(telemetry_root, 's_test', run_id)
                    .read_text(encoding='utf-8').splitlines())
        new_rows = (_strategy_file(new_root, 's_test', run_id)
                    .read_text(encoding='utf-8').splitlines())
        assert len(old_rows) == 1
        assert len(new_rows) == 1
        assert json.loads(new_rows[0])['envelope']['dseq'] == 2
    finally:
        set_recorder_replay_dir(telemetry_root)
