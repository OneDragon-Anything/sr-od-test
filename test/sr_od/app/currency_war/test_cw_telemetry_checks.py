# -*- coding: utf-8 -*-
"""决策项 1 锁:生产遥测接 checks(栈判别+coldstart 适配)。"""
from __future__ import annotations

import json
from pathlib import Path


def _write_replay(d: Path, runs: list[dict]) -> None:
    """runs=[{run_id, strategy_id, plane, round, actions}] → 两流 jsonl。"""
    d.mkdir(parents=True, exist_ok=True)
    with (d / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(json.dumps({
                'run_id': r['run_id'], 'plane': r.get('plane', 1),
                'round_num': r['round'], 'ts': str(r['round']),
                'strategy_id': r.get('strategy_id', ''),
                'target_comp': r.get('target_comp', ''),
                'gold': 10, 'state': {},
                'actions': r['actions'],
            }, ensure_ascii=False) + '\n')
    with (d / 'outcomes.jsonl').open('w', encoding='utf-8') as f:
        for r in runs:
            f.write(json.dumps({
                'run_id': r['run_id'], 'plane': 1,
                'round_num': r['round'], 'node_type': '普通战斗',
                'hp_after': 80,
            }, ensure_ascii=False) + '\n')


def _buy(name: str, reason: str) -> dict:
    return {'__type__': 'BuyCard', 'card': {'name': name, 'cost': 1},
            'reason': reason}


def test_default_stack_skipped(tmp_path: Path) -> None:
    """default 栈(cw_plan,reason='plan')跳过 coldstart(不辖 r368)。"""
    from sr_od.application.currency_war.cw_telemetry import (
        run_checks_on_replay,
    )
    _write_replay(tmp_path, [{
        'run_id': 'run_t1', 'strategy_id': 'default', 'round': 1,
        'actions': [_buy('翡翠', 'plan')],   # plan 开局买=生产 default 合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert '跳过' in out and '⚠' not in out


def test_v2_stack_violation_detected(tmp_path: Path) -> None:
    """v2 栈违规(开局轮 reason=off=局49 形态)被检出+run_id 溯源。"""
    from sr_od.application.currency_war.cw_telemetry import (
        run_checks_on_replay,
    )
    _write_replay(tmp_path, [{
        'run_id': 'run_t2', 'strategy_id': 'line_v2', 'round': 1,
        'actions': [_buy('翡翠', 'off')],
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t2' in out and '⚠ 1 条' in out and '翡翠' in out


def test_stack_inferred_from_reason_vocab(tmp_path: Path) -> None:
    """strategy_id 缺失时按开局 reason 词表判栈(v2 词→v2 栈跑检查)。"""
    from sr_od.application.currency_war.cw_telemetry import (
        run_checks_on_replay,
    )
    _write_replay(tmp_path, [{
        'run_id': 'run_t3', 'strategy_id': '', 'round': 2,
        'actions': [_buy('丹恒·饮月', 'bridge_seed')],   # v2 词表=合法
    }])
    out = '\n'.join(run_checks_on_replay(tmp_path))
    assert 'run_t3' in out and '✓ 无违规' in out
