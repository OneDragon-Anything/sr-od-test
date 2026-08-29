# type: ignore
"""W146 锁测试:v3 意向状态(IntentionState)进 decisions 遥测行。

背景(ADR-0336):v2_locked_line/v2_mode 是 v1 遗留恒空键,decision_v2
的锁定真值在 session.v3_intention——此前不落遥测,实机判读锁定时点/目标
只能日志考古。本批把 serialize_intention(session.v3_intention) 以
``v3_intention`` 键写入生产 decisions 行与 sim 账本行(同构)。

锁契约(锁行为不锁分布):
1. 锁定局决策行含 phase='locked' + locked_comp 目标名;
2. 未锁局含明确空态(dict 且 phase='unlocked');session 无意向状态机
   → None(default 栈局与「有意向未锁」显式区分);
3. sim 账本行含同键(形状锁:sim 锁定与否随 seed 分布,不锁分布数值)。
"""
import json

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    serialize_intention,
)

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder


def _record_one(tmp_path, extra):
    """最小 fixture:一条 decisions 落盘并读回(tmp_path,不写真实 .debug/)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('run_w146', 'A2')
    rec.record_decision('run_w146', 'A2', GameState(), 'X',
                        {}, {}, [], extra=extra)
    rows = [json.loads(ln) for ln in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8'
                                                     ).splitlines()]
    assert rows
    return rows[-1]


def test_locked_row_carries_phase_and_comp(tmp_path):
    """①锁定局决策行:v3_intention.phase='locked' 且 locked_comp=目标名。"""
    row = _record_one(tmp_path, {
        'v3_intention': serialize_intention(
            IntentionState(phase='locked', locked_comp='DOT卡芙卡',
                           lock_layer=3, lock_plane=1, lock_round=4)),
    })
    ist = row['v3_intention']
    assert isinstance(ist, dict)
    assert ist['phase'] == 'locked'
    assert ist['locked_comp'] == 'DOT卡芙卡'
    # 锁定时机遥测字段随行(判读锁定时点的直读维度)
    assert ist['lock_plane'] == 1 and ist['lock_round'] == 4


def test_unlocked_row_has_explicit_empty_state(tmp_path):
    """②未锁局:v3_intention 是 dict 且 phase='unlocked'(非缺失/非猜)。"""
    row = _record_one(tmp_path, {
        'v3_intention': serialize_intention(IntentionState()),
    })
    ist = row['v3_intention']
    assert isinstance(ist, dict)
    assert ist['phase'] == 'unlocked'
    assert ist['locked_comp'] == ''
    # 非法输入退 None(不是崩);extra 缺键 → 行缺省 None(旧 schema 兼容)
    assert serialize_intention(None) is None
    assert serialize_intention('junk') is None
    row2 = _record_one(tmp_path, {})
    assert row2['v3_intention'] is None


def test_sim_ledger_rows_carry_same_key():
    """③sim 账本同构:每轮行有 v3_intention 键(形状锁,不锁锁定分布)。"""
    res = simulate_p1(seed=20260827, use_refresh=False)
    assert res.ledger, 'sim 账本非空前提'
    for r in res.ledger:
        ist = r.get('v3_intention')
        assert ist is None or isinstance(ist, dict)
        if isinstance(ist, dict):
            assert ist.get('phase') in ('unlocked', 'locked', 'weak')
            if ist.get('phase') == 'locked':
                # 锁定行必带目标名(sim 分析批分锁定/未锁局的判据)
                assert ist.get('locked_comp')
