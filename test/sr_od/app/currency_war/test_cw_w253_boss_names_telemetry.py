"""行为锁:outcomes 行补 boss_names/难度/词缀字段(数据欠账)。

结论④:P1 boss Δ 双峰归因被堵在「不知道每局 boss 是谁」——outcomes schema
不记录 boss 身份/难度/affix。修法(battle_loop 局终链之外的单一写入端):
``TelemetryRecorder.record_outcome`` 落行时从 ``ctx.cw_match.session`` 快照

- ``boss_names`` = session.briefing_bosses 全量透传(位面序 3 元素;
  None=该位面徽章态采不到身份,**保位勿滤**——滤掉会让后续位面名字左移错位,
  ADR-0398);
- ``selected_difficulty`` / ``enemy_affixes`` = 同 session 的职级与简报词缀
  (§2 「难度/affix 不可分层」缺口一并补)。

旧行兼容:三个字段都是 schema 末尾追加、可选默认——旧记录无键,读取端须走
``.get``(本文件末尾锁钉死该契约)。record 端快照 best-effort(镜像 r339 板深
快照惯例):session 缺字段/无 ctx 时落默认值,不阻塞记录。

纯桩测试(TelemetryRecorder 指向 tmp_path;set_ctx_match 后 finally 还原,
不写真实 .debug、不污染全局引用)。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_telemetry import (
    OutcomeRecord,
    TelemetryRecorder,
    read_jsonl,
    set_ctx_match,
)


def _rec(tmp_path):
    return TelemetryRecorder(replay_dir=tmp_path, enabled=True)


def test_record_outcome_boss_names_roundtrip(tmp_path) -> None:
    """session.briefing_bosses 有实采真值 → 行带 boss_names,None 徽章态**保位**透传。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None,
        last_state=GameState(),
        briefing_bosses=['浮黎', None, '星期日'],
        selected_difficulty='A4',
        briefing_affixes=['伤害提高', '生命降低'],
    )))
    try:
        rec = _rec(tmp_path)
        rec.record_outcome('r1', RoundOutcome(round_num=9, plane=1, node_type='boss',
                                              comp_tag='c', hp_after=60))
        lines = read_jsonl(tmp_path / 'outcomes.jsonl')
        assert len(lines) == 1
        row = lines[0]
        # 位面序全量 3 元素;None 位面照 None 写在原位(防左移错位)
        assert row['boss_names'] == ['浮黎', None, '星期日']
        assert row['selected_difficulty'] == 'A4'
        assert row['enemy_affixes'] == ['伤害提高', '生命降低']
    finally:
        set_ctx_match(None)


def test_record_outcome_no_session_defaults(tmp_path) -> None:
    """无 ctx match/session 缺字段 → 落默认值(boss_names=None),记录不被阻塞。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None, last_state=GameState(),
    )))   # 无 briefing_bosses/难度/词缀属性
    try:
        rec = _rec(tmp_path)
        # 接管局开局:briefing_bosses 尚空(list 空)也落 None(未采 ≠ 全 None 行)
        rec.record_outcome('r1', RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                                              comp_tag='?', hp_after=100))
        set_ctx_match(None)   # 第二行彻底无 ctx(合成补给路径等)
        rec.record_outcome('r1', RoundOutcome(round_num=2, plane=1, node_type='补给',
                                              comp_tag='?', hp_after=99))
        rows = read_jsonl(tmp_path / 'outcomes.jsonl')
        for row in rows:
            assert row['boss_names'] is None
            assert row['selected_difficulty'] == ''
            assert row['enemy_affixes'] == []
    finally:
        set_ctx_match(None)


def test_record_outcome_empty_briefing_bosses_is_none(tmp_path) -> None:
    """briefing_bosses=[](未采,接管局常态)→ boss_names=None(区分「采到但徽章态」)。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None, last_state=GameState(), briefing_bosses=[],
    )))
    try:
        rec = _rec(tmp_path)
        rec.record_outcome('r1', RoundOutcome(round_num=5, plane=1, node_type='普通战斗',
                                              comp_tag='c', hp_after=80))
        (row,) = read_jsonl(tmp_path / 'outcomes.jsonl')
        assert row['boss_names'] is None
    finally:
        set_ctx_match(None)


# ===== 旧 schema 兼容锁 =====


def test_legacy_row_without_fields_readable(tmp_path) -> None:
    """旧 schema 行(无三新键)读取端容忍:.get 取默认不 KeyError。

    锁的是消费端契约——历史语料(outcomes.jsonl 大量 前旧行)与新代码共存时,
    分层/Δ池生成器等读 side 必须走 .get('/默认'),不得裸下标。
    """
    legacy = {'schema_version': 1, 'ts': '2026-08-26T09:00:00', 'run_id': 'run_old',
              'round_num': 9, 'plane': 1, 'node_type': 'boss', 'comp_tag': '?',
              'hp_after': 46, 'hp_confidence': 1.0}
    p = tmp_path / 'outcomes.jsonl'
    p.open('w', encoding='utf-8').write(json.dumps(legacy, ensure_ascii=False) + '\n')
    rows = read_jsonl(p)
    assert rows[0].get('boss_names') is None          # 旧行无键 → .get 默认容忍
    assert rows[0].get('selected_difficulty') is None
    assert rows[0].get('enemy_affixes') is None
    # 新键存在且默认值正确的 dataclass 正向对拍(构造期无 TypeError)
    rec = OutcomeRecord()
    assert rec.boss_names is None and rec.selected_difficulty == ''
    assert rec.enemy_affixes == []
