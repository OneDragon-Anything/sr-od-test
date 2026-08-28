"""rounds 视图判读增强(零行为变更):hp 可信位 `?` 标
+ release 逐帧计数列 + dp 显示规整。

锁契约不锁分布:断言输出行的标记/列形状,不断言统计数值分布。
数据参照(真实 replay):run_20260828_103147 p2r4 帧序 hp=4→100×5→4 且
hp_readable 恒 False(100 物理不可能=兜底)——`?` 标就是防这形态被误读为满血。
"""
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war import cw_telemetry


@pytest.fixture()
def rec(tmp_path: Path, monkeypatch):
    """隔离 recorder(共享模块态一律 monkeypatch,不裸赋值)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w445t')
    monkeypatch.setattr(cw_telemetry, '_CURRENT_DIFFICULTY', 'A8')
    return tmp_path


def _record(rec, plane: int, round_num: int, extra: dict,
            hp: int = 100, hp_readable: bool = True, hp_trusted: bool = True) -> None:
    from sr_od.application.currency_war.cw_state import GameState
    st = GameState()
    st.plane, st.round_num, st.gold = plane, round_num, 50
    st.hp = hp
    st.hp_readable = hp_readable
    st.hp_trusted = hp_trusted
    cw_telemetry.record_decision(st, '', {}, {}, [], extra=extra)


def _line(rec, plane: int, round_num: int) -> str:
    lines = cw_telemetry.query_rounds(rec, 'w445t')
    hits = [ln for ln in lines if ln.strip().startswith(f'p{plane}r{round_num}')]
    assert len(hits) == 1, lines
    return hits[0]


def test_hp_untrusted_gets_question_mark(rec):
    """hp_readable=False 或 hp_trusted=False → hp 后缀 `?`(100 兜底防误读)。"""
    _record(rec, 2, 4, {'strategy_id': 'decision_v2', 'dp_posture': '+D4'},
            hp=100, hp_readable=False, hp_trusted=False)
    assert 'hp=100?' in _line(rec, 2, 4)


def test_hp_trusted_no_mark(rec):
    """双可信位齐 → 无 `?`(真满血不该被打问号)。"""
    _record(rec, 1, 1, {'strategy_id': 'decision_v2', 'dp_posture': '+D4'},
            hp=100, hp_readable=True, hp_trusted=True)
    assert 'hp=100 ' in _line(rec, 1, 1)
    assert 'hp=100?' not in _line(rec, 1, 1)


def test_hp_sim_rows_exempt(rec):
    """sim 账本行 hp 是模拟真值且不带可信位字段 → 豁免不标(锁契约:有 sim 键)。"""
    row = {'run_id': 'w445t', 'plane': 1, 'round_num': 2, 'gold': 30, 'hp': 88,
           'target_comp': '', 'actions': [],
           'state': {'board': {}, 'level': 3},
           'sim': {'depth': 5, 'core_count': 2}}
    with open(Path(rec) / 'decisions.jsonl', 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    ln = _line(rec, 1, 2)
    assert 'hp=88 ' in ln
    assert 'hp=88?' not in ln


def test_release_frame_count_column(rec):
    """release 帧数列:decision_v2 帧 dp=='release' 逐帧计数;载体帧 str(dict)
    与非 v2 策略帧不计(遥测契约:str 相等 + 滤 strategy_id=='decision_v2')。"""
    _record(rec, 1, 3, {'strategy_id': 'decision_v2', 'dp_posture': 'release'})
    _record(rec, 1, 3, {'strategy_id': 'decision_v2', 'dp_posture': 'release'})
    _record(rec, 1, 3, {'strategy_id': 'decision_v2', 'dp_posture': 'hold'})
    _record(rec, 1, 3, {'strategy_id': '', 'dp_posture': 'release'})   # 载体帧 str 形态
    _record(rec, 1, 3, {'strategy_id': 'line_v1', 'dp_posture': 'release'})
    assert 'rl=2' in _line(rec, 1, 3)


def test_release_zero_frames_omitted(rec):
    """无 release 帧 → 列省略(视图不添零噪声)。"""
    _record(rec, 1, 5, {'strategy_id': 'decision_v2', 'dp_posture': 'hold'})
    assert 'rl=' not in _line(rec, 1, 5)


def test_dp_display_normalized(rec):
    """dp 显示规整:决策帧显 tag;载体帧(str(dict) 形态)紧凑占位 dp=?。"""
    _record(rec, 1, 6, {'strategy_id': 'decision_v2', 'dp_posture': '+D4'})
    assert 'dp=+D4' in _line(rec, 1, 6)
    _record(rec, 1, 7, {'strategy_id': '',
                        'dp_posture': {'spend_mode': 'level', 'target_level': 7}})
    ln = _line(rec, 1, 7)
    assert 'dp=?' in ln
    assert 'spend_mode' not in ln   # 原始串不倾倒
