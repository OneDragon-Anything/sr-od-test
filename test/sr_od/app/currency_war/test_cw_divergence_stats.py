"""分歧频率统计器测试(12 号预备;fixtures 用临时 jsonl)。

W446 注:dp 姿态语义仅 decision_v2 决策帧携带(statistics 口径要求
strategy_id=='decision_v2'),fixture 行均带该标记。


出处:docs/develop/currency_war/strategy/05_observation.md;docs/develop/currency_war/strategy/README.md(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import json  # noqa: E402

from sr_od.application.currency_war.telemetry.cw_divergence_stats import divergence_stats  # noqa: E402


def test_divergence_stats(tmp_path: Path) -> None:
    """close_call 计数/dp_modes 聚合/run 过滤。"""
    rows = [
        {'run_id': 'r1', 'round_num': 1, 'candidate_scores': {'a': 1.0, 'b': 0.95}, 'strategy_id': 'decision_v2', 'dp_posture': '升级'},
        {'run_id': 'r1', 'round_num': 2, 'candidate_scores': {'a': 1.0, 'b': 0.5}, 'strategy_id': 'decision_v2', 'dp_posture': 'adaptive'},
        {'run_id': 'r2', 'round_num': 1, 'candidate_scores': {}, 'strategy_id': 'decision_v2', 'dp_posture': ''},
    ]
    d = tmp_path / 'decisions.jsonl'
    d.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 3
    assert st['with_candidates'] == 2
    assert st['close_calls'] == 1          # r1 round1 gap 0.05
    assert st['per_run'] == {'r1': [1]}
    assert st['dp_modes'] == {'升级': 1, 'adaptive': 1}
    assert st['with_dp_posture'] == 2      # 空串 tag 不计
    # run 过滤
    st2 = divergence_stats(tmp_path, run_id='r2')
    assert st2['decisions_total'] == 1 and st2['close_calls'] == 0


def test_divergence_missing_file(tmp_path: Path) -> None:
    """文件缺 → 零值不炸。"""
    st = divergence_stats(tmp_path)
    assert st['decisions_total'] == 0
