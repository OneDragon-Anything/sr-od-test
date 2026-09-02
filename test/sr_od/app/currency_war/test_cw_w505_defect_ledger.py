"""W505 B1/B2:统一缺陷台账(defect_ledger.jsonl)+ 金面收口(纯观测)。

测四类:①台账 schema 锁(逐字段,新流不扩旧流)②分级纯函数 judge_severity
真值表(三级判据链)③旁路接线锁(obs_conflict / record_exec_event 写入 →
台账同行出现,调用方零改动)④gold_close 流锁(shop 暂存 → spend_ledger 行
充实;无暂存 → unknown 不猜;读端行内优先)。契约锁形状不锁分布;
全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.telemetry import defects, query, recorder, schema, state
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w505t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    # 复现计数是进程内状态,逐测试清空防串
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    # L0 安灯副作用链隔离:handler 桩化(缺省 None 会惰性接真停线——gc 扫描命中
    # 测试 ctx → 写真实仓根 flag + stop_running 毒 session 级 fixture 的
    # last_run_result,全集后续 execute 全撞 W209j 刹车);闩锁同批清空,
    # 防 rid 残留让后续测试的 L0 判级场景静默不触发。
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_FIRED_RUNS', set())
    # 分包期 4:obs_conflict 的旁路/run_id 出口走 kernel.cw_telemetry_exit 钩子位,
    # 注入真实现(monkeypatch 槽位,自动还原)
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_bypass_obs_conflict_to_defect',
                        defects.bypass_obs_conflict_to_defect)
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        state.current_run_id)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① 台账 schema 锁(逐字段)=====

def test_defect_ledger_schema_field_lock(tmp_path: Path, monkeypatch):
    """落一行并逐字段锁 schema(字段名/形状=设计 §3.2;新字段末尾追加原则)。"""
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_defect(
        'gold', 'invariant_break', 'gold∈[0,400]', '405', gap=5.0,
        plane=1, round_num=3, unit_seq=2, verdict='待研',
        shot='obs_conflict_gold.png',
        refs=[{'stream': 'spend_ledger', 'key': 'plane=1|round=3|unit_seq=2'}],
        reader_source='shop_spend_audit', note='测试行')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(rows) == 1
    r = rows[0]
    # W512 追加可选末尾字段 confidence(§2.10;旧记录缺省 None 兼容)
    assert set(r) == {'schema_version', 'ts', 'run_id', 'plane', 'round_num',
                      'unit_seq', 'surface', 'kind', 'expected', 'observed',
                      'gap', 'severity', 'verdict', 'evidence', 'reader_source',
                      'note', 'confidence'}
    assert r['confidence'] is None   # 未传 → None(无置信度语义面)
    assert r['schema_version'] == schema.SCHEMA_VERSION
    assert r['run_id'] == 'w505t'
    assert (r['plane'], r['round_num'], r['unit_seq']) == (1, 3, 2)
    assert r['surface'] == 'gold' and r['kind'] == 'invariant_break'
    assert r['expected'] == 'gold∈[0,400]' and r['observed'] == '405'
    assert r['gap'] == 5.0
    assert r['severity'] == 'L2_record'   # 显式 gap_large=False → 保守 L2
    assert r['verdict'] == '待研'
    assert r['evidence'] == {'shot': 'obs_conflict_gold.png',
                             'refs': [{'stream': 'spend_ledger',
                                       'key': 'plane=1|round=3|unit_seq=2'}]}
    assert r['reader_source'] == 'shop_spend_audit' and r['note'] == '测试行'


def test_defect_ledger_noop_without_run_id(tmp_path: Path, monkeypatch):
    """run_id 空 → no-op(与其他便捷入口同门控)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', '')
    defects.record_defect('gold', 'perception_conflict', 'a', 'b')
    assert not (tmp_path / 'defect_ledger.jsonl').exists()


# ===== ② 分级纯函数真值表(判据链:①关键面 ②大gap ③复现)=====

def test_judge_severity_truth_table():
    """L0=关键∧大gap∧复现∧非自动;L1=关键∧大gap 单次,或中面∧大gap∧复现;
    L2=自动裁决/非关键/小 gap。"""
    j = defects.judge_severity
    # 决策关键面
    assert j('gold', gap_large=True, reproduced=True) == 'L0_andon'
    assert j('gold', gap_large=True, reproduced=False) == 'L1_alert'
    assert j('gold', gap_large=False, reproduced=True) == 'L2_record'
    # 裁决已自动 → 恒 L2(即使关键面+大gap+复现)
    assert j('gold', gap_large=True, reproduced=True,
             auto_resolved=True) == 'L2_record'
    # 中相关面:大gap∧复现 → L1;单次 → L2
    assert j('hp', gap_large=True, reproduced=True) == 'L1_alert'
    assert j('hp', gap_large=True, reproduced=False) == 'L2_record'
    # 非关键非中面 → L2
    assert j('confidence', gap_large=True, reproduced=True) == 'L2_record'


def test_critical_surface_domain_lock():
    """关键面/中面枚举锁(分级判据①的域;扩面必须显式改此处)。"""
    assert frozenset(
        {'gold', 'bench', 'deployed', 'level_xp', 'shop_refresh', 'phase_round'}) \
        == defects.DECISION_CRITICAL_SURFACES
    assert frozenset({'hp', 'equip', 'strategy', 'node_seq', 'streak'}) \
        == defects.MEDIUM_CRITICAL_SURFACES


def test_reproduction_counter_upgrades_second_occurrence(tmp_path: Path, monkeypatch):
    """同特征第 2 次 = 复现:金面大 gap 单次 L1 → 再犯升 L0(判据③防抖)。"""
    _setup_recorder(monkeypatch, tmp_path)
    for _ in range(2):
        defects.record_defect('gold', 'perception_conflict',
                                   'gold_delta: 45', '20', gap=-25.0,
                                   gap_large=True)
    sevs = [r['severity'] for r in _rows(tmp_path, 'defect_ledger.jsonl')]
    assert sevs == ['L1_alert', 'L0_andon']


# ===== ③ 旁路接线锁(obs_conflict / exec_event 写入 → 台账同行出现)=====

def test_obs_conflict_bypass_appends_ledger_row(tmp_path: Path, monkeypatch):
    """obs_conflict 写入 → obs_conflicts 原流行 + defect_ledger 同行出现
    (refs 指回原行;gold_delta 大 gap → 关键面单次 = L1)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL', tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('gold_delta', 45, 20, None,
                            verdict='留证-动作账vs读数不等',
                            source='shop_spend_audit', plane=1, round_num=3,
                            spend=5)
    conflicts = _rows(tmp_path, 'obs_conflicts.jsonl')
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(conflicts) == 1 and len(defects) == 1
    c, d = conflicts[0], defects[0]
    # 原流行原样(field/old/new 在),台账是归一映射(refs 指回)
    assert (c['field'], c['old'], c['new']) == ('gold_delta', 45, 20)
    assert d['surface'] == 'gold' and d['kind'] == 'perception_conflict'
    assert d['expected'] == 'gold_delta: 45' and d['observed'] == '20'
    assert d['gap'] == -25.0
    assert d['severity'] == 'L1_alert'   # 关键面+大gap(>10)+单次
    assert d['run_id'] == 'w505t'        # 台账补齐旧流缺的 join key
    assert d['reader_source'] == 'shop_spend_audit'
    assert d['evidence']['refs'][0]['stream'] == 'obs_conflicts'
    assert f"ts={c['ts']}" in d['evidence']['refs'][0]['key']


def test_obs_conflict_bypass_auto_resolved_and_text_field(tmp_path: Path, monkeypatch):
    """裁决已自动面(deployed_align)恒 L2;未映射文本字段原样落 surface、
    gap 不硬猜(None)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL', tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('deployed_align', 4, 5, None,
                            verdict='采新-paddle锚', source='align')
    cw_observe.obs_conflict('back_layout_channel_conflict', {'a': 1}, {'b': 2}, None,
                            verdict='留证')
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert defects[0]['surface'] == 'deployed'
    assert defects[0]['severity'] == 'L2_record'   # 自动裁决 → L2
    assert defects[1]['surface'] == 'back_layout_channel_conflict'   # 未映射原样
    assert defects[1]['gap'] is None               # 文本面不填 gap
    assert defects[1]['severity'] == 'L2_record'


def test_exec_event_bypass_fail_only(tmp_path: Path, monkeypatch):
    """record_exec_event 写入 → fail 类事件台账同行出现;success 类不进台账。"""
    _setup_recorder(monkeypatch, tmp_path)
    rec = state.get_recorder()
    rec.record_exec_event('w505t', 7, 'BuyCard', 'battle_prep',
                          'fail', reason='识别MISS', retry_count=2)
    rec.record_exec_event('w505t', 7, 'LevelUp', 'battle_prep',
                          'success_uncharged', reason='x')
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert len(defects) == 1
    d = defects[0]
    assert d['surface'] == 'bench' and d['kind'] == 'exec_fail'
    assert d['expected'] == 'BuyCard 动作生效'
    assert d['observed'] == 'fail: 识别MISS'
    assert d['severity'] == 'L2_record'   # 执行失败写端恒初判 L2(安灯归既有钩子)
    assert d['evidence']['refs'][0]['stream'] == 'exec_events'
    assert 'family=BuyCard' in d['evidence']['refs'][0]['key']


def test_exec_event_bypass_surface_mapping(tmp_path: Path, monkeypatch):
    """动作族 → surface 映射锁(LevelUp→level_xp / Refresh→shop_refresh)。"""
    _setup_recorder(monkeypatch, tmp_path)
    rec = state.get_recorder()
    rec.record_exec_event('w505t', 2, 'LevelUp', 'battle_prep', 'blocked', reason='x')
    rec.record_exec_event('w505t', 3, 'RefreshShop', 'battle_prep', 'bail', reason='y')
    surfaces = [d['surface'] for d in _rows(tmp_path, 'defect_ledger.jsonl')]
    assert surfaces == ['level_xp', 'shop_refresh']


# ===== ④ gold_close 流锁(shop 暂存 → spend_ledger 充实 / unknown 不猜)=====

def test_gold_close_slot_fills_spend_ledger(tmp_path: Path, monkeypatch):
    """shop 侧 set_unit_gold_close → 单元关闭落账行 gold_close/trusted 充实;
    消费即清(下一单元无暂存恒 None,不串)。"""
    _setup_recorder(monkeypatch, tmp_path)
    state.set_unit_gold_close(45)
    recorder.record_spend_unit(1, 1, 1, 'closed', True, 1.0)
    recorder.record_spend_unit(1, 2, 2, 'closed', True, 1.0)
    rows = _rows(tmp_path, 'spend_ledger.jsonl')
    assert (rows[0]['gold_close'], rows[0]['gold_close_trusted']) == (45, True)
    assert (rows[1]['gold_close'], rows[1]['gold_close_trusted']) == (None, False)


def test_gold_close_read_failure_recorded_not_silent(tmp_path: Path, monkeypatch):
    """read_gold 失读(None)照记 trusted=False——「对拍通过」与「失读」
    离线可分,unknown 占比降到读失败率而非静默缺失。"""
    _setup_recorder(monkeypatch, tmp_path)
    state.set_unit_gold_close(None)
    recorder.record_spend_unit(1, 1, 1, 'closed', True, 1.0)
    row = _rows(tmp_path, 'spend_ledger.jsonl')[0]
    assert (row['gold_close'], row['gold_close_trusted']) == (None, False)


def test_query_prefers_ledger_gold_close_over_conflict(tmp_path: Path):
    """读端:行内 gold_close 优先(无冲突行也判 effective——unknown 面消除);
    旧行(无该字段,gold_close 槽挂上前的历史局)回退冲突行;两者皆缺 →
    unknown 不猜。带字段读失败行(None+trusted=False)**不回退**——回退
    = 把陈旧冲突行 join 面(同轮上一单元误吃,ADR-0514)挪进读失败路径,
    该语义锁在 test_cw_economy resolve_gold_close 新锁。"""
    schema.append_jsonl(tmp_path / 'spend_ledger.jsonl', {
        'ts': '2026-08-28T12:00:00', 'run_id': 't', 'plane': 1, 'round_num': 1,
        'unit_seq': 1, 'boundary': 'closed', 'gold_close': 45,
        'gold_close_trusted': True})
    # r2 = legacy 行(无 gold_close 字段)——冲突行回退的唯一合法形态
    schema.append_jsonl(tmp_path / 'spend_ledger.jsonl', {
        'ts': '2026-08-28T12:05:00', 'run_id': 't', 'plane': 1, 'round_num': 2,
        'unit_seq': 2, 'boundary': 'closed'})
    schema.append_jsonl(tmp_path / 'spend_ledger.jsonl', {
        'ts': '2026-08-28T12:10:00', 'run_id': 't', 'plane': 1, 'round_num': 3,
        'unit_seq': 3, 'boundary': 'closed', 'gold_close': None,
        'gold_close_trusted': False})
    for rnd, ts in ((1, '12:00:05'), (2, '12:05:05'), (3, '12:10:05')):
        schema.append_jsonl(tmp_path / 'decisions.jsonl', {
            'run_id': 't', 'ts': f'2026-08-28T{ts}', 'plane': 1, 'round_num': rnd,
            'gold': 50, 'gold_readable': True, 'eval_breakdown': {},
            'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': 'X', 'cost': 5}}]})
    # 仅 r2 有冲突行(旧口径的唯一金源);r1/r3 无
    schema.append_jsonl(tmp_path / 'obs_conflicts.jsonl', {
        'ts': '2026-08-28T12:05:20', 'field': 'gold_delta', 'old': 45, 'new': 45,
        'verdict': '留证', 'source': 'shop_spend_audit', 'plane': 1, 'round_num': 2})
    lines = '\n'.join(query.query_spend_ledger(tmp_path, 't'))
    # r1:仅行内 gold_close=45 → effective(旧口径下无冲突行会记 unknown)
    r1 = next(ln for ln in lines.splitlines() if 'u1 p1r1' in ln)
    assert 'effective' in r1
    # r2:行内 None → 回退冲突行 45 → effective(旧行为保持)
    r2 = next(ln for ln in lines.splitlines() if 'u2 p1r2' in ln)
    assert 'effective' in r2
    # r3:全缺 → unknown 不猜
    r3 = next(ln for ln in lines.splitlines() if 'u3 p1r3' in ln)
    assert 'unknown' in r3


def test_shop_close_audit_wiring_lock():
    """shop.py 关店对拍段接线锁(静态):spend_audit 点在 mismatch 分支之外
    无条件调 set_unit_gold_close(_final_gold)(失读 None 也照记);
    锁「落点在对拍段内且无条件」,防后续重构静默断链。"""
    import sr_od.application.currency_war.operations.prep.shop as shop
    src = Path(shop.__file__).read_text(encoding='utf-8')
    assert 'set_unit_gold_close(_final_gold)' in src
    # 无条件性:调用必须位于 read_gold 之后、mismatch 判定(if _final_gold is not None)之前
    tail = src[src.index('_final_gold = read_gold'):]
    unconditional = tail.split('if _final_gold is not None')[0]
    assert 'set_unit_gold_close' in unconditional


from sr_od.application.currency_war.telemetry import state
