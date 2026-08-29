# -*- coding: utf-8 -*-
"""W103(ADR-0342)锁:策略失活检测三件。

件1:dead_streak_transition 状态机(备上一轮/同轮不重计/live 复位);
件1 查询端:strategy_round_live(mtime 缓存失效);
件2:check_strategy_live_streak(W98 两局形态必报/健康局不报/短段不报)
    + run_checks_on_replay 失活行接线。
"""
from __future__ import annotations

import json
from pathlib import Path
from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import state
from sr_od.application.currency_war.telemetry import query, recorder



def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def test_dead_streak_transition_state_machine() -> None:
    """同 key 重入不计数;换 key 时 live 复位 / dead 递增。"""
    t = query.dead_streak_transition
    # 首轮(prev None):不结算
    assert t(None, (1, 1), 0, True) == 0
    assert t(None, (1, 1), 2, False) == 2
    # 同轮重入(过渡帧/重试):不结算
    assert t((1, 1), (1, 1), 1, False) == 1
    # 换轮:live 复位
    assert t((1, 1), (1, 2), 1, True) == 0
    # 换轮:dead 递增
    assert t((1, 1), (1, 2), 0, False) == 1
    assert t((1, 2), (1, 3), 1, False) == 2   # 连击到 2 = loop 侧停局线


def test_strategy_round_live_with_cache(tmp_path, monkeypatch) -> None:
    """mtime 缓存:写入后重查可见;不同 run 互不串。"""
    rec = recorder.TelemetryRecorder(
        replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    query._STRATEGY_LIVE_CACHE.clear()
    f = tmp_path / 'decisions.jsonl'
    _write_rows(f, [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1, 'strategy_id': ''},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2, 'strategy_id': 'decision_v2'},
    ])
    assert query.strategy_round_live('r1', (1, 1)) is False
    assert query.strategy_round_live('r1', (1, 2)) is True
    # 追加(新 mtime)后缓存失效重扫:r1 r1 也变 live
    _write_rows(f, [{'run_id': 'r1', 'plane': 1, 'round_num': 1,
                     'strategy_id': 'decision_v2'}])
    assert query.strategy_round_live('r1', (1, 1)) is True


def test_check_strategy_live_streak_w98_shape() -> None:
    """W98 两局形态(整局恒空)必报;健康局不报;孤立短段不报。"""
    c = query.check_strategy_live_streak
    # W98 形态:P1 全轮 strategy_id 恒空(003757: 57 行实录形状)
    dead_rows = [
        {'plane': 1, 'round_num': rn, 'strategy_id': ''}
        for rn in range(1, 10)
    ]
    v = c(dead_rows)
    assert v and '9 轮' in v[0] and 'W98' in v[0]
    # 健康局:每轮都有 live 行
    ok_rows = [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'decision_v2'}
        for rn in range(1, 10)
    ]
    assert c(ok_rows) == []
    # 混合行投影:同轮任一行带 strategy_id 即 live
    mixed = [{'plane': 1, 'round_num': 1, 'strategy_id': ''},
             {'plane': 1, 'round_num': 1, 'strategy_id': 'decision_v2'}]
    assert c(mixed) == []
    # 孤立 2 轮空段(< 阈值 3)不报
    short = [{'plane': 1, 'round_num': rn, 'strategy_id': ''}
             for rn in (1, 2)] + [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'decision_v2'}
        for rn in (3, 4)]
    assert c(short) == []
    # P2 空轮不辖(只辖 P1)
    p2 = [{'plane': 2, 'round_num': rn, 'strategy_id': ''}
          for rn in range(1, 5)]
    assert c(p2) == []


def test_run_checks_reports_dead_run(tmp_path, monkeypatch) -> None:
    """run_checks_on_replay 对失活局出「[策略失活]」行(不被判栈跳过)。"""
    rec = recorder.TelemetryRecorder(
        replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    _write_rows(tmp_path / 'decisions.jsonl', [
        {'run_id': 'dead1', 'plane': 1, 'round_num': rn, 'strategy_id': '',
         'actions': [{'__type__': 'EnsureShopClosed'}]}
        for rn in range(1, 6)
    ])
    _write_rows(tmp_path / 'outcomes.jsonl', [
        {'run_id': 'dead1', 'plane': 1, 'round_num': rn} for rn in range(1, 6)
    ])
    lines = ledger_hooks.run_checks_on_replay(tmp_path, recent=5)
    assert any('[策略失活]' in x and 'dead1' in x for x in lines), lines


