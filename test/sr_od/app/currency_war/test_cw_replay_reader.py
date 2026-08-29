"""遥测读端规范 loader 测试(W446;fixtures 用 tmp_path,不碰真实 .debug)。"""
import sys
from dataclasses import is_dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

import json  # noqa: E402

from sr_od.application.currency_war.telemetry.cw_replay_reader import (  # noqa: E402
    DecisionTrace,
    OutcomeRecord,
    from_dict,
    load_decisions,
    load_outcomes,
    posture_tag,
)
from sr_od.application.currency_war.telemetry.cw_divergence_stats import divergence_stats  # noqa: E402
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows),
                    encoding='utf-8')
    return path


def test_load_decisions_current_str_frame(tmp_path: Path) -> None:
    """现行帧(str tag)→ 类型化 DecisionTrace,字段逐一对上。"""
    row = {'schema_version': 1, 'run_id': 'r1', 'round_num': 3, 'plane': 1,
           'strategy_id': 'decision_v2', 'dp_posture': '升级+D6',
           'hp': 40, 'gold_readable': True, 'actions': [{'__type__': 'BuyCard'}]}
    p = _write(tmp_path / 'decisions.jsonl', [row])
    frames = load_decisions(p)
    assert len(frames) == 1
    f = frames[0]
    assert isinstance(f, DecisionTrace) and is_dataclass(f)
    assert (f.run_id, f.round_num, f.plane) == ('r1', 3, 1)
    assert f.dp_posture == '升级+D6'
    assert f.gold_readable is True
    assert f.actions[0]['__type__'] == 'BuyCard'


def test_load_decisions_historical_dict_frame(tmp_path: Path) -> None:
    """历史 dict 帧(dp_posture={'spend_mode','target_level'})容忍加载。"""
    row = {'run_id': 'r0', 'round_num': 2, 'strategy_id': '',
           'dp_posture': {'spend_mode': 'adaptive', 'target_level': 4}}
    p = _write(tmp_path / 'decisions.jsonl', [row])
    frames = load_decisions(p)
    assert len(frames) == 1
    assert frames[0].dp_posture == {'spend_mode': 'adaptive', 'target_level': 4}
    # 未声明字段忽略不炸(写端未来加字段的向前容忍)
    row_unknown = dict(row, some_future_field=42)
    p2 = _write(tmp_path / 'd2.jsonl', [row_unknown])
    assert len(load_decisions(p2)) == 1


def test_load_decisions_missing_new_fields(tmp_path: Path) -> None:
    """历史帧缺新字段(form_ok/phase/dp_posture/handoff)→ dataclass 默认值,不炸。"""
    row = {'run_id': 'r0', 'round_num': 1}   # 只有关键 join 键的最老形态
    p = _write(tmp_path / 'decisions.jsonl', [row])
    f = load_decisions(p)[0]
    assert f.form_ok is False and f.phase == ''
    assert f.dp_posture == '' and f.handoff is None


def test_load_decisions_bad_lines_skipped(tmp_path: Path) -> None:
    """坏行(JSON 解析失败/非 dict)跳过不抛;run_id 过滤。"""
    p = tmp_path / 'decisions.jsonl'
    p.write_text('{"run_id": "r1", "round_num": 1}\n'
                 'NOT JSON\n'
                 '"bare string"\n'
                 '{"run_id": "r2", "round_num": 2}\n', encoding='utf-8')
    frames = load_decisions(p)
    assert [f.round_num for f in frames] == [1, 2]
    assert [f.round_num for f in load_decisions(p, run_id='r2')] == [2]


def test_load_outcomes(tmp_path: Path) -> None:
    """outcomes.jsonl → OutcomeRecord(含 enemy_hp_after=None 死字段容忍)。"""
    row = {'run_id': 'r1', 'round_num': 1, 'hp_after': 38,
           'enemy_hp_after': None, 'killed': True}
    p = _write(tmp_path / 'outcomes.jsonl', [row])
    recs = load_outcomes(p)
    assert len(recs) == 1 and isinstance(recs[0], OutcomeRecord)
    assert recs[0].enemy_hp_after is None and recs[0].killed is True
    assert load_outcomes(tmp_path / 'nope.jsonl') == []


def test_posture_tag_forms() -> None:
    """posture_tag 归一:现行 str tag / 历史 dict / 载体帧 str(dict) / 缺失。"""
    tag_long = "{'spend_mode': 'adaptive', 'target_level': 4}"   # 载体帧长串(实测 42-46 字符)
    cases = [
        # (strategy_id, dp_posture, 期望 tag)
        ('decision_v2', '升级+D6', '升级+D6'),       # 现行 str tag
        ('decision_v2', 'release', 'release'),
        ('decision_v2', {'spend_mode': 'adaptive', 'target_level': 4}, 'adaptive'),  # 历史 dict
        ('decision_v2', {'target_level': 4}, None),   # dict 缺 spend_mode 不猜
        ('decision_v2', '', None),                     # 空 tag
        ('decision_v2', tag_long, None),               # str(dict) 泄漏形态非 tag
        ('decision_v2', None, None),
        ('', '存息', None),                            # 载体帧恒 None
        ('', tag_long, None),
        ('', {'spend_mode': 'x'}, None),
        ('decision_v2', 42, None),                     # 非法形态不炸
    ]
    for sid, dp, expect in cases:
        assert posture_tag({'strategy_id': sid, 'dp_posture': dp}) == expect, (sid, dp)
    # typed 对象与裸 dict 同判
    assert posture_tag(DecisionTrace(strategy_id='decision_v2', dp_posture='存息')) == '存息'
    assert posture_tag(DecisionTrace(strategy_id='', dp_posture=tag_long)) is None
    # 历史帧缺 dp_posture 属性路径(dict 行缺键)
    assert posture_tag({'run_id': 'r'}) is None


def test_posture_tag_matches_real_carrier_shape() -> None:
    """锁契约:载体帧真实形态(实测 long str(dict),以 '{' 开头)不可被误当 tag。"""
    real = str({'spend_mode': 'adaptive', 'target_level': 4})   # 复刻写端 str(dict) 真实产物
    assert real.startswith('{')
    assert posture_tag({'strategy_id': '', 'dp_posture': real}) is None
    assert posture_tag({'strategy_id': 'decision_v2', 'dp_posture': real}) is None


def test_divergence_stats_on_typed_rows(tmp_path: Path) -> None:
    """端到端:混合形态(现行 str/历史 dict/载体帧)下统计口径不变。"""
    rows = [
        {'run_id': 'r1', 'round_num': 1, 'strategy_id': 'decision_v2', 'dp_posture': 'release',
         'candidate_scores': {'a': 1.0, 'b': 0.95}},
        {'run_id': 'r1', 'round_num': 2, 'strategy_id': '',   # 载体帧:长串姿态不计入
         'dp_posture': str({'spend_mode': 'adaptive', 'target_level': 4})},
        {'run_id': 'r1', 'round_num': 3, 'strategy_id': 'decision_v2',
         'dp_posture': {'spend_mode': 'adaptive', 'target_level': 4}},   # 历史 dict 帧计 spend_mode
    ]
    _write(tmp_path / 'decisions.jsonl', rows)
    st = divergence_stats(tmp_path)
    assert st['with_dp_posture'] == 2
    assert st['dp_modes'] == {'release': 1, 'adaptive': 1}
    assert st['close_calls'] == 1 and st['per_run'] == {'r1': [1]}


def test_from_dict_is_write_side_single_source() -> None:
    """from_dict 产物即 cw_telemetry 写端类(单一源,非平行类)。"""

    from sr_od.application.currency_war.telemetry.schema import DecisionTrace as WT
    assert DecisionTrace is WT
    f = from_dict(DecisionTrace, {'run_id': 'r', 'not_a_field': 1})
    assert isinstance(f, WT) and f.run_id == 'r'
