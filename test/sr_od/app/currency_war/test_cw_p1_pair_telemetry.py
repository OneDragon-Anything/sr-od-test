"""P1 配方对平铺遥测(sess_p1_pair)回归锁。

背景(W473 复盘,P1 观测盲区):决策层 P1 锁定的「配方对」产物
(IntentionState.p1_pair / transition_pair 过渡体系键二元组)在 P1
活路径(PrepDirector 步进行 decisions 行)不落任何平铺遥测字段——
target_comp 恒空、sess_framework 恒空,判读看不到 P1 锁了哪个配方对,
「终局线何时锁」在 P1 段不可答;该字段是后续配对完成度买牌信号 A/B
的关键度量上游。

本锁钉死:
- ``schema.p1_pair_label`` 派生口径(配方锁 p1_pair 优先,
  ①锁局 transition_pair 次选;空窗/无意向 = '');
- record 站点:extra 透传 → DecisionTrace.sess_p1_pair 落盘;
  缺 extra 时空串(纯遥测,决策行为零变化);
- prep_director._record_step 接线(session.v3_intention 来源);
- 旧台账兼容:无 sess_p1_pair 键的历史行经 cw_replay_reader 读取
  不炸(dataclass 已知字段过滤 + 缺省 '')。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_intention import serialize_intention
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.telemetry.cw_replay_reader import from_dict

from sr_od.application.currency_war.telemetry.schema import DecisionTrace
from sr_od.application.currency_war.telemetry import recorder, schema


# ===== 派生口径:p1_pair_label =====


def test_label_recipe_lock_pair() -> None:
    """配方锁局:p1_pair 二元组 → 'A+B' 体系键串。"""
    ist = IntentionState(phase='locked', p1_pair=('仙舟', '列车同行'))
    assert schema.p1_pair_label(ist) == '仙舟+列车同行'


def test_label_transition_pair_fallback() -> None:
    """①资格锁局:p1_pair 空、transition_pair 非空 → 取副方向。"""
    ist = IntentionState(phase='locked', transition_pair=('持续伤害', '贝洛伯格'))
    assert schema.p1_pair_label(ist) == '持续伤害+贝洛伯格'


def test_label_empty_when_unlocked_or_absent() -> None:
    """空窗(未锁)/空意向状态机/None/非 dataclass 一律空串(纯观测不阻塞)。"""
    assert schema.p1_pair_label(IntentionState()) == ''
    assert schema.p1_pair_label(None) == ''
    assert schema.p1_pair_label(object()) == ''


# ===== record 站点:extra 透传 → decisions 行 =====


def _write_and_read(rec: recorder.TelemetryRecorder, tmp_path: Path,
                    extra: dict | None = None) -> dict:
    rec.record_decision('p1pair', 'A8', GameState(gold=10, round_num=1, plane=1),
                        '', {}, {}, [], extra=extra)
    rows = [json.loads(r) for r in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    return rows[-1]


def test_record_row_carries_pair_when_locked(tmp_path) -> None:
    """锁定帧:extra 透传 → 行内 sess_p1_pair 非空且值正确。"""
    rec = recorder.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    row = _write_and_read(rec, tmp_path,
                          extra={'sess_p1_pair': '仙舟+列车同行'})
    assert row['sess_p1_pair'] == '仙舟+列车同行'


def test_record_row_empty_without_extra(tmp_path) -> None:
    """未锁/无 extra(旧调用方):行内 sess_p1_pair 空串。"""
    rec = recorder.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    row = _write_and_read(rec, tmp_path)
    assert row['sess_p1_pair'] == ''
    row = _write_and_read(rec, tmp_path, extra={'formed_stop': True})
    assert row['sess_p1_pair'] == ''


# ===== prep_director._record_step 接线 =====


def test_director_record_step_passes_pair_from_session(monkeypatch) -> None:
    """P1 活路径步进行:session.v3_intention 配方对 → record extra。"""


    from sr_od.application.currency_war.prep_director import PrepDirector

    captured: dict = {}

    def _fake_record(state, target_comp, candidate_scores, eval_breakdown,
                     actions, extra=None, gold_point=True) -> None:
        captured['extra'] = extra

    monkeypatch.setattr(recorder, 'record_decision', _fake_record)
    director = object.__new__(PrepDirector)   # 免 ctx(纯遥测接线测试)
    director._steps = 0
    fake_sess = SimpleNamespace(
        v3_formed_stop=False,
        v3_intention=IntentionState(phase='locked', p1_pair=('仙舟', '列车同行')),
        last_owned_equips=[], target_comp=None)
    director._session = lambda: fake_sess   # 实例属性遮蔽方法
    obs = SimpleNamespace(state=GameState())
    director._record_step(obs, action=None)  # type: ignore[arg-type]
    assert captured['extra']['sess_p1_pair'] == '仙舟+列车同行'
    assert captured['extra']['formed_stop'] is False


def test_director_record_step_empty_pair_without_intention(monkeypatch) -> None:
    """session 无意向状态机(v3_intention=None)→ extra 空串。"""


    from sr_od.application.currency_war.prep_director import PrepDirector

    captured: dict = {}

    def _fake_record(state, target_comp, candidate_scores, eval_breakdown,
                     actions, extra=None, gold_point=True) -> None:
        captured['extra'] = extra

    monkeypatch.setattr(recorder, 'record_decision', _fake_record)
    director = object.__new__(PrepDirector)
    director._steps = 0
    fake_sess = SimpleNamespace(v3_formed_stop=False, v3_intention=None,
                                last_owned_equips=[], target_comp=None)
    director._session = lambda: fake_sess
    director._record_step(SimpleNamespace(state=GameState()), action=None)  # type: ignore[arg-type]
    assert captured['extra']['sess_p1_pair'] == ''


# ===== 旧台账兼容(cw_replay_reader 已知字段过滤)=====


def test_old_ledger_row_without_key_reads_fine() -> None:
    """历史行(无 sess_p1_pair 键)→ DecisionTrace 缺省空串,不炸。"""
    old_row = {'schema_version': 1, 'run_id': 'legacy', 'round_num': 3,
               'plane': 1, 'target_comp': ''}
    trace = from_dict(DecisionTrace, old_row)
    assert isinstance(trace, DecisionTrace)
    assert trace.sess_p1_pair == ''


def test_new_ledger_row_with_key_preserved() -> None:
    """新行(带键)读回不丢值——读端过滤是「滤未知」不是「滤新增」。"""
    new_row = {'run_id': 'r', 'sess_p1_pair': '仙舟+列车同行',
               'unknown_future_key': 1}   # 未知键被滤,新增键保留
    trace = from_dict(DecisionTrace, new_row)
    assert trace.sess_p1_pair == '仙舟+列车同行'


@pytest.mark.parametrize('pair', [('仙舟', '列车同行'), ()])
def test_label_matches_intention_serialization_source(pair: tuple) -> None:
    """标签与 serialize_intention 全量序列化中的 p1_pair 同源同值。"""
    ist = IntentionState(phase='locked' if pair else 'unlocked', p1_pair=pair)
    d = serialize_intention(ist)
    assert schema.p1_pair_label(ist) == '+'.join(d['p1_pair'])


from sr_od.application.currency_war.telemetry import state
