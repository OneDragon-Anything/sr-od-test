"""件1(ADR-0273):runs.jsonl 局终汇总多路径兜底锁测试。

批⑧ F2:8/22 起 16/18 局缺汇总——r363 兜底只盖 stop 信号路径,FAIL/崩溃/重启
杀局漏写。锁:
- build_recovered_summary 从 outcomes/decisions 重算(loss=hp0 / abandoned;
  plane_reached=max;gold 轨迹按 (plane,round) 去重;pivot=target 序列转移;
  source='recovered')。
- recover_dangling_run_summaries 幂等(只补缺行,已 summaried 不重复;二次调空)。
- 无 outcomes 的 run(开局失败/假局守卫)→ 留缺口不造伪值。
- check_summary_write_path_coverage 检查项双向(缺行 ⚠ 带 run_id / 全覆盖 ✓)。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sr_od.application.currency_war.telemetry.cw_telemetry import (
    append_jsonl,
    build_recovered_summary,
    check_summary_write_path_coverage,
    read_jsonl,
    recover_dangling_run_summaries,
)


def _write(path: Path, rows: list[dict]) -> None:
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _mk_dir(tmp: str) -> Path:
    d = Path(tmp) / 'replay'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _outcome(rid: str, plane: int, rnd: int, hp: int, conf: float = 1.0) -> dict:
    return {'run_id': rid, 'plane': plane, 'round_num': rnd, 'hp_after': hp,
            'hp_confidence': conf, 'ts': f'2026-08-24T00:0{rnd}:00'}


def _decision(rid: str, plane: int, rnd: int, gold: int, target: str = '') -> dict:
    return {'run_id': rid, 'plane': plane, 'round_num': rnd, 'gold': gold,
            'target_comp': target, 'difficulty': 'A8',
            'ts': f'2026-08-24T00:0{rnd}:00'}


def test_build_recovered_summary_loss_and_fields() -> None:
    """hp=0 末条真值 → loss;字段从逐轮行重算;source=recovered。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _outcome('rA', 1, 1, 90), _outcome('rA', 1, 2, 70),
            _outcome('rA', 2, 1, 0),
        ])
        _write(d / 'decisions.jsonl', [
            _decision('rA', 1, 1, 50, '仙舟'),
            _decision('rA', 1, 1, 48, '仙舟'),      # 同轮步进值(去重)
            _decision('rA', 1, 2, 60, '列车'),       # pivot 1 次
            _decision('rA', 2, 1, 55, '列车'),
        ])
        s = build_recovered_summary(d, 'rA')
        assert s is not None
        assert s.result == 'loss'                    # 末条真值 hp=0
        assert s.plane_reached == 2
        assert s.rounds_survived == 1                # 末条 (2,1) 位面内编号
        assert s.final_hp == 0
        assert s.gold_trajectory == [50, 60, 55]     # 同轮去重
        assert s.comps_committed == ['仙舟', '列车']
        assert s.pivot_count == 1
        assert s.difficulty == 'A8'
        assert s.source == 'recovered'


def test_build_recovered_summary_abandoned_and_conf_gate() -> None:
    """非零末真值 → abandoned;final_hp 取 conf≥0.9 末条(低置信 100 兜底不毒化)。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _outcome('rB', 1, 3, 26),
            _outcome('rB', 1, 4, 100, conf=0.0),    # 死局读不到的 100 兜底(低置信)
        ])
        s = build_recovered_summary(d, 'rB')
        assert s is not None
        assert s.result == 'abandoned'
        assert s.final_hp == 26                      # conf≥0.9 真值优先于末条兜底


def test_recover_dangling_idempotent() -> None:
    """只补缺行(已 summaried 不动);二次调用幂等空回。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _outcome('rOK', 1, 1, 90), _outcome('rOK', 1, 2, 100),
            _outcome('rDangle', 1, 1, 80),
        ])
        append_jsonl(d / 'runs.jsonl', {
            'run_id': 'rOK', 'result': 'win', 'plane_reached': 3,
            'final_hp': 100, 'gold_trajectory': [50], 'comps_committed': [],
        })
        got = recover_dangling_run_summaries(d)
        assert got == ['rDangle']
        rows = read_jsonl(d / 'runs.jsonl')
        assert len(rows) == 2
        assert rows[-1]['run_id'] == 'rDangle'
        assert rows[-1]['source'] == 'recovered'
        assert rows[-1]['result'] == 'abandoned'
        # 幂等:二次调用无新行
        assert recover_dangling_run_summaries(d) == []
        assert len(read_jsonl(d / 'runs.jsonl')) == 2


def test_recover_skips_no_outcome_runs() -> None:
    """无 outcomes 的 run(开局失败/假局守卫)→ 留缺口不造伪值。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'decisions.jsonl', [_decision('rGhost', 1, 1, 50)])
        # outcomes 无 rGhost 行 → 不在扫描域;decisions-only run 不回填
        assert build_recovered_summary(d, 'rGhost') is None
        assert recover_dangling_run_summaries(d) == []
        assert not (d / 'runs.jsonl').exists()


def test_coverage_check_both_directions() -> None:
    """检查项双向:缺行 ⚠ 带 run_id 溯源;补齐后 ✓。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _outcome('r1', 1, 1, 90), _outcome('r2', 1, 1, 80),
        ])
        out = check_summary_write_path_coverage(d)
        assert len(out) == 1 and '⚠' in out[0] and 'r1' in out[0] and 'r2' in out[0]
        recover_dangling_run_summaries(d)
        out = check_summary_write_path_coverage(d)
        assert len(out) == 1 and '✓' in out[0] and '100%' in out[0]
