"""W494 执行层 spend_ledger:购买单元金账记账(纯观测)。

测三类:plan_gold_flow 逐项期望金流 / classify_spend_unit 三态判定(含
读数缺失/半单元边界)/ query_spend_ledger 读端 join(三态计数+大额失配
清单+历史局伪单元回退)。锁契约不锁分布:只断言判定与行形状,不断言
统计数值分布。数据口径参照 W489 审计(高金单元金零下降形态)。
"""
import json
from pathlib import Path

from sr_od.application.currency_war import cw_telemetry

# ===== plan_gold_flow(逐项期望金流)=====

def test_flow_mixed_plan():
    """买+升+刷(无cost退2)+卖入混合;DeployMove 零金流不入 items。"""
    plan = [
        {'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 2}},
        {'__type__': 'BuyCard', 'card': {'x': 500, 'name': '', 'cost': 1}},
        {'__type__': 'LevelUp', 'cost': 4},
        {'__type__': 'RefreshShop', 'cost': 0},
        {'__type__': 'SellBench', 'bench_idx': 2, 'income': 3},
        {'__type__': 'DeployMove', 'bench_idx': 0, 'to_row': 'front', 'to_slot': 1},
    ]
    f = cw_telemetry.plan_gold_flow(plan)
    assert f['planned_spend'] == 2 + 1 + 4 + 2
    assert f['planned_income'] == 3
    assert f['net'] == 3 - 9
    assert f['has_refresh'] is True
    assert f['income_unknown'] is False
    assert len(f['items']) == 5   # DeployMove 零金流不计
    assert f['items'][0] == {'type': 'BuyCard', 'target': '卡芙卡', 'cost': 2,
                             'direction': 'spend'}


def test_flow_sell_income_unknown_flag():
    """income=None 记 0 并标 income_unknown(读数缺失不硬猜)。"""
    f = cw_telemetry.plan_gold_flow([{'__type__': 'SellBench', 'bench_idx': 0,
                                      'income': None}])
    assert f['planned_income'] == 0
    assert f['income_unknown'] is True


def test_flow_refresh_explicit_cost_and_fallback():
    """RefreshShop 有 cost 用 cost;缺省退 refresh_cost 参数(=审计 or 2 口径)。"""
    a = cw_telemetry.plan_gold_flow([{'__type__': 'RefreshShop', 'cost': 1}])
    b = cw_telemetry.plan_gold_flow([{'__type__': 'RefreshShop', 'cost': 0}],
                                    refresh_cost=3)
    assert a['planned_spend'] == 1
    assert b['planned_spend'] == 3


# ===== classify_spend_unit(三态判定+边界)=====

def _buy(cost=5):
    return [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': 'X', 'cost': cost}}]


def test_classify_effective():
    """planned_spent & 金按计划移动 = 生效。"""
    r = cw_telemetry.classify_spend_unit(_buy(5), 50, 45)
    assert r['verdict'] == 'effective'
    assert (r['actual_delta'], r['gap']) == (-5, 0)


def test_classify_effective_within_tolerance():
    """差值恰在 ±2 容差内(与 shop 审计同源)→ 生效。"""
    assert cw_telemetry.classify_spend_unit(_buy(5), 50, 47)['verdict'] == 'effective'


def test_classify_not_effective_gold_frozen():
    """planned_spent & 金零下降(W489 病灶形态)= 执行未生效。"""
    r = cw_telemetry.classify_spend_unit(_buy(5), 125, 125)
    assert r['verdict'] == 'not_effective'
    assert r['gap'] == 5


def test_classify_partial_mismatch():
    """金动了但对不上账(部分成交/口径差/未观收入)≠ 全灭,单列一格。"""
    r = cw_telemetry.classify_spend_unit(_buy(5), 50, 20)
    assert r['verdict'] == 'partial_mismatch'


def test_classify_unplanned_spend():
    """no_plan & gold_moved = 计划外花销。"""
    r = cw_telemetry.classify_spend_unit([], 50, 30)
    assert r['verdict'] == 'unplanned_spend'


def test_classify_no_spend_quiet():
    """无计划且金未动 = 健康静默单元。"""
    assert cw_telemetry.classify_spend_unit([], 50, 51)['verdict'] == 'no_spend_quiet'


def test_classify_unknown_missing_close_reading():
    """关店金读数缺失 → unknown 不猜(无冲突行 ≠ 对拍通过,read 失败也不写行)。"""
    r = cw_telemetry.classify_spend_unit(_buy(5), 50, None)
    assert r['verdict'] == 'unknown'
    assert 'gold_reading_missing' in r['reason']


def test_classify_unknown_half_unit_boundary():
    """半单元/中断单元(aborted)即使读数齐也不判——执行链不完整。"""
    r = cw_telemetry.classify_spend_unit(_buy(5), 50, 45, boundary='aborted')
    assert r['verdict'] == 'unknown'
    assert 'boundary' in r['reason']


# ===== query_spend_ledger(读端 join)=====

def _append(rec: Path, name: str, row: dict) -> None:
    cw_telemetry.append_jsonl(rec / name, row)


def _seed_three_stream(rec: Path) -> None:
    """三流样本:1 个生效单元 + 1 个中断单元 + 1 个大额失配单元。"""
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:00:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 1, 'unit_seq': 1, 'boundary': 'closed',
        'progressed': True, 'duration_s': 8.0, 'detail': 'ok',
        'gold_before': None, 'gold_before_trusted': False,
        'gold_close': None, 'gold_close_trusted': False})
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:05:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 2, 'unit_seq': 2, 'boundary': 'aborted',
        'progressed': False, 'duration_s': 2.0, 'detail': '执行异常',
        'gold_close': None, 'gold_close_trusted': False})
    _append(rec, 'spend_ledger.jsonl', {
        'schema_version': 1, 'ts': '2026-08-28T12:10:00', 'run_id': 'w494t',
        'plane': 1, 'round_num': 3, 'unit_seq': 3, 'boundary': 'closed',
        'progressed': True, 'duration_s': 9.0, 'detail': 'ok',
        'gold_close': None, 'gold_close_trusted': False})
    # shop plan 行(eval_breakdown 无 prep_step 判别式)+ director 步进行(带 prep_step,不作 plan)
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:00:05', 'plane': 1, 'round_num': 1,
        'gold': 50, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 5}}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T11:59:00', 'plane': 1, 'round_num': 1,
        'gold': 48, 'gold_readable': False, 'eval_breakdown': {'prep_step': 1.0},
        'actions': [{'__type__': 'LevelUp', 'cost': 4}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:05:05', 'plane': 1, 'round_num': 2,
        'gold': 60, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '乱破', 'cost': 3}}]})
    _append(rec, 'decisions.jsonl', {
        'run_id': 'w494t', 'ts': '2026-08-28T12:10:05', 'plane': 1, 'round_num': 3,
        'gold': 50, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '椒丘', 'cost': 5}}]})
    # 关店实读金冲突行(仅 r1 对拍通过形态:old=45 new=45;r3 大额失配 20)
    _append(rec, 'obs_conflicts.jsonl', {
        'ts': '2026-08-28T12:00:20', 'field': 'gold_delta', 'old': 45, 'new': 45,
        'verdict': '留证', 'source': 'shop_spend_audit', 'plane': 1, 'round_num': 1,
        'spend': 5})
    _append(rec, 'obs_conflicts.jsonl', {
        'ts': '2026-08-28T12:10:20', 'field': 'gold_delta', 'old': 45, 'new': 20,
        'verdict': '留证', 'source': 'shop_spend_audit', 'plane': 1, 'round_num': 3,
        'spend': 5})


def test_query_spend_ledger_counts_and_large_gap(tmp_path: Path):
    _seed_three_stream(tmp_path)
    lines = cw_telemetry.query_spend_ledger(tmp_path, 'w494t')
    text = '\n'.join(lines)
    assert '共3' in text
    assert 'effective×1' in text
    assert 'unknown×1' in text           # aborted 中断单元:boundary 门 → unknown
    # r3:开金50(plan 行)关金20(冲突行)Δ=-30,计划花5 → 金动了但对不上账
    # (partial_mismatch),差 25 > 10 → 必入大额失配清单
    assert 'partial_mismatch×1' in text
    assert '大额失配' in text
    assert 'p1r3' in text


def test_query_spend_ledger_plan_row_discriminates_prep_step(tmp_path: Path):
    """同轮 shop plan 行与 director 步进行并存:plan 取无 prep_step 的行(金50 非 48)。"""
    _seed_three_stream(tmp_path)
    lines = cw_telemetry.query_spend_ledger(tmp_path, 'w494t')
    r1 = next(ln for ln in lines if 'u1 p1r1' in ln)
    assert '开金=50' in r1
    assert '花费=5' in r1


def test_query_spend_ledger_fallback_pseudo_units(tmp_path: Path):
    """无 ledger 行(历史局):按 shop plan 行重建伪单元,判定恒 unknown。"""
    _append(tmp_path, 'decisions.jsonl', {
        'run_id': 'old', 'ts': '2026-08-28T09:00:00', 'plane': 1, 'round_num': 5,
        'gold': 125, 'gold_readable': True, 'eval_breakdown': {},
        'actions': [{'__type__': 'BuyCard', 'card': {'x': 300, 'name': '卡芙卡', 'cost': 2}}]})
    lines = cw_telemetry.query_spend_ledger(tmp_path, 'old')
    text = '\n'.join(lines)
    assert 'unknown×1' in text
    assert '(伪单元)' in text
    assert '花费=2' in text


def test_record_spend_unit_noop_without_run_id(tmp_path: Path, monkeypatch):
    """run_id 空 → no-op(与 record_exogenous 同门控)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', '')
    cw_telemetry.record_spend_unit(1, 1, 1, 'closed', True, 1.0)
    assert not (tmp_path / 'spend_ledger.jsonl').exists()


def test_record_spend_unit_appends(tmp_path: Path, monkeypatch):
    """有 run_id → 落一行且 schema 字段齐(gold_close 预留恒 None)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w494t')
    cw_telemetry.record_spend_unit(2, 7, 3, 'failed', False, 12.345,
                                   detail='x' * 500, gold_before=88)
    row = json.loads((tmp_path / 'spend_ledger.jsonl').read_text(encoding='utf-8').splitlines()[0])
    assert row['run_id'] == 'w494t'
    assert (row['plane'], row['round_num'], row['unit_seq']) == (2, 7, 3)
    assert row['boundary'] == 'failed'
    assert row['duration_s'] == 12.35
    assert len(row['detail']) == 240   # 截断防刷屏
    assert row['gold_before'] == 88 and row['gold_before_trusted'] is False
    assert row['gold_close'] is None
