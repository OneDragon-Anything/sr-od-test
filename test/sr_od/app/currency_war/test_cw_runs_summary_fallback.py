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

import pytest

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.sim.ledger_hooks import (
    build_recovered_summary,
    check_summary_write_path_coverage,
    recover_dangling_run_summaries,
)
from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry.schema import append_jsonl


@pytest.fixture(autouse=True)
def _no_pool_regen(monkeypatch: pytest.MonkeyPatch) -> None:
    """桩掉局终 Δ池再生钩(recover 补行成功即触发,ledger_hooks 模块内
    自持引用;它读生产 live 根并重写跟踪中的 data/cw_delta_pool_data.py
    ——测试零真实副作用,纪律 2:2026-09-08 快层实测本文件每次运行都
    重写该文件)。快照内容红归池锚重推批(语料推进 vs 提交锚),与本
    文件锁语义无关。"""
    monkeypatch.setattr(ledger_hooks,
                        '_regenerate_delta_pool_after_run', lambda: None)


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


def _terminal_outcome(rid: str, plane: int, rnd: int,
                      match_result: str) -> dict:
    """收口终局行(T-185 生产形状,消费键集对账锚 =
    test_cw_telemetry_archive.test_stopped_game_last_round_outcome_in_archive)。"""
    return {'run_id': rid, 'plane': plane, 'round_num': rnd,
            'hp_after': None, 'hp_confidence': 0.0, 'killed': False,
            'source': 'terminal_closure', 'match_result': match_result,
            'ts': f'2026-08-24T00:0{rnd}:00'}


def test_build_recovered_summary_terminal_only_run_not_fake_loss() -> None:
    """唯一 outcome 行=收口终局行的局不产伪 loss(T-185 落地审建议-3):
    旧法终局行 hp_confidence=0.0 不入可信行 → last=终局行 →
    final_hp=int(None or 0)=0 → result='loss'——stopped 局在 runs.jsonl
    变战败局,且档案 hp 真值链终局腿(match_archive,result=='loss' 门)
    被连带触发。修后 result 从行内 match_result 读收口形态(行内真值,
    RunSummary.result 合法枚举);final_hp 0 兜底与 cw_loop 正常收口路径
    int(_final_hp or 0) 同款(hp 不可读时写 0,非战败语义,判读按 result
    分型);rounds_survived 取收口轮号(冻结值,与 settlement_gap 的
    claimed 同源合法)。触发窗 = 终局行已写、runs 行未写之间崩溃(窄窗,
    该路径本就是为崩溃窗设计)。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _terminal_outcome('rT1', 2, 6, 'stopped'),
            _terminal_outcome('rT2', 1, 2, 'abandoned'),
        ])
        _write(d / 'decisions.jsonl', [
            _decision('rT1', 2, 6, 50), _decision('rT2', 1, 2, 48)])
        s1 = build_recovered_summary(d, 'rT1')
        assert s1 is not None
        assert s1.result == 'stopped'            # 收口形态真值,非伪 loss
        assert s1.final_hp == 0                  # 无 hp 真值,0 兜底(非战败语义)
        assert s1.rounds_survived == 6           # 收口轮号
        assert s1.source == 'recovered'
        s2 = build_recovered_summary(d, 'rT2')
        assert s2 is not None and s2.result == 'abandoned'
        # 行内 match_result 缺失/未知(写端漂移防御)→ 退 'abandoned',不猜
        _write(d / 'outcomes.jsonl', [
            _terminal_outcome('rT3', 1, 1, 'stopped')
            | {'match_result': ''}])
        s3 = build_recovered_summary(d, 'rT3')
        assert s3 is not None and s3.result == 'abandoned'


def test_build_recovered_summary_mixed_run_result_from_terminal_row() -> None:
    """混合局(早轮可信结算 + 收口终局行):result 同样从终局行读——收口
    形态是行内真值,不走 hp 推断;final_hp 维持既有 conf≥0.9 末条真值
    优先(早轮可信结算入可信行,不受终局行污染)。"""
    with tempfile.TemporaryDirectory(prefix='cw_r412_') as tmp:
        d = _mk_dir(tmp)
        _write(d / 'outcomes.jsonl', [
            _outcome('rM', 1, 1, 40),
            _terminal_outcome('rM', 1, 2, 'stopped'),
        ])
        _write(d / 'decisions.jsonl', [_decision('rM', 1, 2, 50)])
        s = build_recovered_summary(d, 'rM')
        assert s is not None
        assert s.result == 'stopped'
        assert s.final_hp == 40                  # 早轮可信真值优先
        assert s.rounds_survived == 2


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
