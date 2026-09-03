"""decisions.jsonl expected_paths 字段单测(期望态 infra 遥测批,用户确认推进)。

三态语义:旧行无键 = 迁移前数据;新行 [] = 无挂起;新行非空 = 决策基于含
期望推进值的画面。覆盖:①决策行含键;②无挂起=[];③挂起摘要正确(BuyCard
后 tracked star 推进场景);④旧格式行读端兼容。
(写法对齐 test_cw_telemetry.py:生产 set_ctx_match + try/finally 还原。)
"""
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture()
def rec(tmp_path: Path) -> Any:
    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    return TelemetryRecorder(replay_dir=tmp_path, enabled=True)


def _decisions(rec: Any) -> list[dict]:
    return [json.loads(ln) for ln in
            (Path(rec.replay_dir) / 'decisions.jsonl').open(encoding='utf-8')]


def _state():
    from sr_od.application.currency_war.kernel.cw_state import GameState
    return GameState(gold=30, plane=1, round_num=3)


# ==================== ①② 决策行含键 / 无挂起=[] ====================

def test_decision_row_always_has_expected_paths_key(rec) -> None:
    """新行恒写 expected_paths 键;无 match 注册(离线/sim)→ []。"""
    rec.start_run('r1', '')
    rec.record_decision('r1', '', _state(), 't', {}, {}, [], gold_point=False)
    rows = _decisions(rec)
    assert len(rows) == 1
    assert 'expected_paths' in rows[0]
    assert rows[0]['expected_paths'] == []


def test_decision_row_no_pending_expected_empty_list(rec) -> None:
    """session 在、expected_state 空容器 → [] (三态之「无挂起」)。"""
    from sr_od.application.currency_war.telemetry.state import set_ctx_match
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(expected_state={})))
    try:
        rec.start_run('r1', '')
        rec.record_decision('r1', '', _state(), 't', {}, {}, [],
                            gold_point=False)
    finally:
        set_ctx_match(None)
    assert _decisions(rec)[0]['expected_paths'] == []


# ==================== ③ 挂起摘要正确 ====================

def test_decision_row_carries_pending_summaries(rec) -> None:
    """BuyCard 合成后 tracked star 推进挂起 → 行内摘要
    (path/value/produced_by/at_round/kind)逐字段正确;value 标量保真。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        ExpectedEntry,
    )
    from sr_od.application.currency_war.telemetry.state import set_ctx_match
    sess = SimpleNamespace(expected_state={
        'tracked_bench_chars[2].star': ExpectedEntry(
            path='tracked_bench_chars[2].star', value=2,
            produced_by='BuyCard', at_round='p2-r3', kind='merge_group'),
    })
    set_ctx_match(SimpleNamespace(session=sess))
    try:
        rec.start_run('r1', '')
        rec.record_decision('r1', '', _state(), 't', {}, {}, [],
                            gold_point=False)
    finally:
        set_ctx_match(None)
    ep = _decisions(rec)[0]['expected_paths']
    assert ep == [{'path': 'tracked_bench_chars[2].star', 'value': 2,
                   'produced_by': 'BuyCard', 'at_round': 'p2-r3',
                   'kind': 'merge_group'}]


def test_expected_paths_non_scalar_value_stringified(rec) -> None:
    """非标量 value(BuyExpect 载体等)str 化——序列化不炸,判读可辨来源。"""
    from sr_od.application.currency_war.kernel.cw_expected_state import (
        ExpectedEntry,
    )
    from sr_od.application.currency_war.telemetry.state import set_ctx_match
    sess = SimpleNamespace(expected_state={
        'buy_expect': ExpectedEntry(path='buy_expect', value=object(),
                                    produced_by='PrepActionExecutor',
                                    at_round='p1-r2', kind='buy_expect'),
    })
    set_ctx_match(SimpleNamespace(session=sess))
    try:
        rec.start_run('r1', '')
        rec.record_decision('r1', '', _state(), 't', {}, {}, [],
                            gold_point=False)
    finally:
        set_ctx_match(None)
    ep = _decisions(rec)[0]['expected_paths']
    assert len(ep) == 1
    assert isinstance(ep[0]['value'], str) and ep[0]['value']


# ==================== ④ 旧格式行读端兼容 ====================

def test_query_rounds_tolerates_legacy_rows_without_key(tmp_path) -> None:
    """旧行(无 expected_paths 键)过 rounds 视图不炸、不显示 exp= 段;
    新行非空挂起 → exp=N 段显示。"""
    from sr_od.application.currency_war.telemetry.query import query_rounds
    (tmp_path / 'outcomes.jsonl').write_text('', encoding='utf-8')
    legacy = {'run_id': 'r1', 'plane': 1, 'round_num': 2, 'ts': 't2',
              'strategy_id': 'decision_v2', 'dp_posture': 'normal',
              'state': {}, 'actions': [{'__type__': 'BuyCard'}]}
    fresh = dict(legacy, round_num=3, ts='t3',
                 expected_paths=[{'path': 'tracked_bench_chars[2].star',
                                  'value': 2, 'produced_by': 'BuyCard',
                                  'at_round': 'p1-r3', 'kind': 'merge_group'}])
    (tmp_path / 'decisions.jsonl').write_text(
        json.dumps(legacy, ensure_ascii=False) + '\n'
        + json.dumps(fresh, ensure_ascii=False) + '\n', encoding='utf-8')
    lines = query_rounds(tmp_path, 'r1')
    assert len(lines) == 2
    legacy_line = next(ln for ln in lines if 'p1r2' in ln)
    fresh_line = next(ln for ln in lines if 'p1r3' in ln)
    assert 'exp=' not in legacy_line          # 旧行容缺省,不显示
    assert 'exp=1(BuyCard:tracked_bench_chars[2].star)' in fresh_line
