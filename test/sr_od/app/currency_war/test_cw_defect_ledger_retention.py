"""defect_ledger 寿命联动锁(T-91:台账 run 段清理随 journal 三道闸联动)。

契约(recorder.enforce_defect_ledger_retention + kernel
cw_state_journal.set_retirement_follower 槽):台账段随 journal run 段
生命周期同窗清理/同 manifest 显影,禁另起独立清理周期(双源漂移禁令)。
段裁决两分:

- 共享段(journal 段名册内)= 严格跟随 journal 归因,**禁台账自评段龄**
  (台账行止于末次缺陷,段末 ts 恒早于 journal 段末,自评会把 journal
  仍保留段的索引行先清掉——证据还在索引先丢,比双留更坏);
- 孤儿段(journal 常开化前历史段,册外)= 同常量同窗自评补判
  (2026-09-12 实测现役台账 141 段全为册外段,纯跟随对其零作用)。

底稿 = T-6-r1 §⑤-1「寿命联动随 run 段同批淘汰」;框架 = T-77 三道闸
(锁面 test_cw_journal_lifecycle_policy / test_cw_w3_journal_only_reads §5,
本文件不重复 kernel 闸语义,只锁联动半边)。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_state_journal
from sr_od.application.currency_war.kernel.cw_state_journal import (
    JOURNAL_NONLIVE_RETENTION_DAYS,
    JOURNAL_RETENTION_DAYS,
    enforce_journal_retention,
)
from sr_od.application.currency_war.telemetry.recorder import (
    DEFECT_LEDGER_RETIREMENT_MANIFEST_NAME,
    enforce_defect_ledger_retention,
)

_LEDGER_ROW = {
    'schema_version': 1, 'plane': 0, 'round_num': 0,
    'surface': 'gold', 'kind': 'perception_conflict', 'expected': 'e',
    'observed': 'o', 'gap': None, 'severity': 'L2_record',
    'verdict': '', 'evidence': {'refs': []},
    'reader_source': '', 'note': '',
}


def _mk_ledger(tmp_path: Path, segs: list[tuple[str, list[str]]]) -> Path:
    """造一份多段台账(段 = (run_id, 行 ts 列表);生产同构布局 =
    telemetry 根下 defect_ledger.jsonl)。"""
    lp = tmp_path / 'defect_ledger.jsonl'
    with lp.open('w', encoding='utf-8') as f:
        for rid, ts_list in segs:
            for ts in ts_list:
                row = dict(_LEDGER_ROW, ts=ts, run_id=rid)
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return lp


def _mk_journal(tmp_path: Path, segs: list[tuple[str, str]]) -> Path:
    """造一份多段 journal(段 = (run_id, 段末 ts);生产同构布局 =
    telemetry 根下 state/journal.jsonl)。"""
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True, exist_ok=True)
    with jp.open('w', encoding='utf-8') as f:
        for rid, ts in segs:
            f.write(json.dumps({
                'v': 1, 'ts': ts, 'run_id': rid, 'row': 'write',
                'field': 'gold', 'after': 1, 'state': {},
                'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
                'note': '', 'evidence_refs': []}, ensure_ascii=False) + '\n')
    return jp


def _ledger_run_ids(lp: Path) -> set[str]:
    out: set[str] = set()
    for ln in lp.read_text(encoding='utf-8').strip().splitlines():
        row = json.loads(ln)
        rid = row.get('run_id') if isinstance(row, dict) else None
        if rid:
            out.add(str(rid))
    return out


def _read_manifest(tmp_path: Path) -> list[dict]:
    man = tmp_path / DEFECT_LEDGER_RETIREMENT_MANIFEST_NAME
    if not man.exists():
        return []
    return [json.loads(ln) for ln in
            man.read_text(encoding='utf-8').strip().splitlines()]


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).isoformat(timespec='seconds')


# ============================================================ 共享段:严格跟随

def test_shared_segment_follows_journal_decision(tmp_path: Path) -> None:
    """共享段裁决 = journal 归因逐段镜像:journal 淘汰的(age_real/
    size_budget 两闸各一)台账整段同去且 manifest reason 同值;journal
    保留段台账行原位。"""
    lp = _mk_ledger(tmp_path, [
        ('run_20260801_000000', [_days_ago(40)]),
        ('fake_by_size', [_days_ago(10)]),
        ('run_20260910_000000', [_days_ago(2)]),
        ('run_20260912_000000', [_days_ago(0)]),
    ])
    # journal 裁决:40 天实机段超语料窗 / fake_by_size 走体积兜底窗
    summary = {
        'checked': 4,
        'retired': ['run_20260801_000000', 'fake_by_size'],
        'rows_dropped': 2,
        'segments': ['run_20260801_000000', 'fake_by_size',
                     'run_20260910_000000', 'run_20260912_000000'],
        'reasons': {'run_20260801_000000': 'age_real',
                    'fake_by_size': 'size_budget'},
    }
    r = enforce_defect_ledger_retention(lp, journal_retirement=summary)
    assert set(r['retired']) == {'run_20260801_000000', 'fake_by_size'}
    assert r['rows_dropped'] == 2
    assert _ledger_run_ids(lp) == {'run_20260910_000000',
                                   'run_20260912_000000'}
    reasons = {m['run_id']: m['reason'] for m in _read_manifest(tmp_path)}
    assert reasons == {'run_20260801_000000': 'age_real',
                       'fake_by_size': 'size_budget'}, \
        'manifest reason 与 journal 归因逐段同值(同显影)'


def test_shared_segment_never_self_retire_before_journal(tmp_path: Path) -> None:
    """反漂移核心锁:共享段台账行再老(journal 保留 = 册内无归因)也不得
    自评淘汰——台账行段末 ts 恒早于 journal 段末,自评会把 journal 仍保留
    段的索引行先清掉(证据还在索引先丢)。变异(共享段改自评判龄)必红。"""
    lp = _mk_ledger(tmp_path, [
        # 台账行 40 天前(超实机窗自评会清),journal 段仍保留
        ('run_20260801_000000', [_days_ago(40)]),
    ])
    summary = {'checked': 1, 'retired': [], 'rows_dropped': 0,
               'segments': ['run_20260801_000000'], 'reasons': {}}
    r = enforce_defect_ledger_retention(lp, journal_retirement=summary)
    assert r['retired'] == [], '共享段禁台账自评:journal 保留即保留'
    assert _ledger_run_ids(lp) == {'run_20260801_000000'}
    assert _read_manifest(tmp_path) == []


# ============================================================ 孤儿段:同窗自评

def test_orphan_segments_same_windows(tmp_path: Path) -> None:
    """册外段(常开化前历史段)按 kernel 同常量同窗自评:实机形态
    JOURNAL_RETENTION_DAYS+1 清 / -1 留;非实机形态
    JOURNAL_NONLIVE_RETENTION_DAYS+1 清 / -1 留;reason 承 RETIRE_REASONS
    值域。边界值随 kernel 常量走(常量改窗本锁自适应,语义 = 与 journal
    同窗),变异(换窗值/删分型)必红。"""
    lp = _mk_ledger(tmp_path, [
        ('run_20260701_000000', [_days_ago(JOURNAL_RETENTION_DAYS + 1)]),
        ('run_20260901_000000', [_days_ago(JOURNAL_RETENTION_DAYS - 1)]),
        ('fake_old', [_days_ago(JOURNAL_NONLIVE_RETENTION_DAYS + 1)]),
        ('fake_fresh', [_days_ago(JOURNAL_NONLIVE_RETENTION_DAYS - 1)]),
    ])
    r = enforce_defect_ledger_retention(
        lp, journal_retirement={'segments': [], 'reasons': {}})
    assert set(r['retired']) == {'run_20260701_000000', 'fake_old'}
    assert _ledger_run_ids(lp) == {'run_20260901_000000', 'fake_fresh'}
    reasons = {m['run_id']: m['reason'] for m in _read_manifest(tmp_path)}
    assert reasons == {'run_20260701_000000': 'age_real',
                       'fake_old': 'age_non_real'}


def test_whole_segment_unit_no_partial_drop(tmp_path: Path) -> None:
    """整段单元锁:被淘汰段内新旧 ts 混行(段末行仍在窗内)也整段去,
    禁按行龄切半段(段 = run_id 归属整体,同 kernel 契约)。"""
    lp = _mk_ledger(tmp_path, [
        # 段内 2 行超窗 + 1 行窗内:run_id 整段淘汰,不按行龄切
        ('run_20260801_000000',
         [_days_ago(40), _days_ago(39), _days_ago(0)]),
        ('run_20260912_000000', [_days_ago(0)]),
    ])
    summary = {'checked': 2, 'retired': ['run_20260801_000000'],
               'rows_dropped': 3,
               'segments': ['run_20260801_000000', 'run_20260912_000000'],
               'reasons': {'run_20260801_000000': 'age_real'}}
    r = enforce_defect_ledger_retention(lp, journal_retirement=summary)
    assert r['retired'] == ['run_20260801_000000']
    assert r['rows_dropped'] == 3, '整段单元:窗内行随段同行淘汰'
    kept = [json.loads(ln) for ln in
            lp.read_text(encoding='utf-8').strip().splitlines()]
    assert len(kept) == 1 and kept[0]['run_id'] == 'run_20260912_000000'
    man = _read_manifest(tmp_path)
    assert len(man) == 1 and man[0]['rows'] == 3
    assert man[0]['last_ts'] == _days_ago(0), \
        'manifest first/last_ts 取段内台账行 ts 范围'


# ============================================================ 显影与幂等

def test_manifest_schema_and_idempotent(tmp_path: Path) -> None:
    """manifest 显影同构(journal.retirement.jsonl 同 schema,archived_out
    语义延续)+ 幂等:清后二跑零增量、manifest 零新增、保留行逐字节不变。"""
    lp = _mk_ledger(tmp_path, [
        ('run_20260801_000000', [_days_ago(40), _days_ago(35)]),
        ('run_20260912_000000', [_days_ago(0)]),
    ])
    summary = {'checked': 2, 'retired': ['run_20260801_000000'],
               'rows_dropped': 2,
               'segments': ['run_20260801_000000', 'run_20260912_000000'],
               'reasons': {'run_20260801_000000': 'age_real'}}
    enforce_defect_ledger_retention(lp, journal_retirement=summary)
    man_rows = _read_manifest(tmp_path)
    assert len(man_rows) == 1
    m = man_rows[0]
    assert {'run_id', 'archived_out', 'reason', 'rows', 'first_ts',
            'last_ts', 'retired_at'} <= set(m)
    assert m['archived_out'] is True and m['rows'] == 2
    assert m['first_ts'] == _days_ago(40) and m['last_ts'] == _days_ago(35)
    kept_before = lp.read_text(encoding='utf-8')
    r2 = enforce_defect_ledger_retention(lp, journal_retirement=summary)
    assert r2 == {'checked': r2['checked'], 'retired': [], 'rows_dropped': 0}
    assert len(_read_manifest(tmp_path)) == 1, '幂等:manifest 只增不重复'
    assert lp.read_text(encoding='utf-8') == kept_before, \
        '幂等:保留行逐字节不变'


def test_noop_paths_no_side_effect(tmp_path: Path) -> None:
    """零清理路径零副作用:无可清段不重写不落 manifest;坏行/无 run_id 行
    原样保留(宽容契约);台账缺席 no-op 且不造 manifest。"""
    lp = _mk_ledger(tmp_path, [
        ('run_20260912_000000', [_days_ago(0)]),
        ('', [_days_ago(100)]),   # 无 run_id 行:永不归属任何段,原样保留
    ])
    with lp.open('a', encoding='utf-8') as f:
        f.write('{bad half line\n')
    before = lp.read_text(encoding='utf-8')
    r = enforce_defect_ledger_retention(
        lp, journal_retirement={'segments': ['run_20260912_000000'],
                                'reasons': {}})
    assert r['retired'] == [] and r['checked'] == 1
    assert lp.read_text(encoding='utf-8') == before, \
        '零清理:文件逐字节不动(不重写不折腾)'
    assert _read_manifest(tmp_path) == []
    # 坏行/无 run_id 行在真清理趟也原样保留
    summary = {'checked': 2, 'retired': ['run_20260912_000000'],
               'rows_dropped': 1, 'segments': ['run_20260912_000000'],
               'reasons': {'run_20260912_000000': 'size_budget'}}
    enforce_defect_ledger_retention(lp, journal_retirement=summary)
    text = lp.read_text(encoding='utf-8')
    assert '{bad half line' in text
    assert '"run_id": ""' in text, '无 run_id 行原样保留'
    assert len([ln for ln in text.strip().splitlines()
                if not ln.startswith('{bad')]) == 1
    r_missing = enforce_defect_ledger_retention(
        tmp_path / 'nope' / 'defect_ledger.jsonl',
        journal_retirement={'segments': ['x'], 'reasons': {'x': 'age_real'}})
    assert r_missing == {'checked': 0, 'retired': [], 'rows_dropped': 0}
    assert not (tmp_path / 'nope' / DEFECT_LEDGER_RETIREMENT_MANIFEST_NAME) \
        .exists(), '台账缺席:no-op 且不造 manifest'


# ============================================================ 装配联动接线

def test_journal_summary_carries_follower_contract(tmp_path: Path) -> None:
    """kernel 段账契约(跟随者输入半边):segments = 全部段名册;reasons
    键集 == retired 集;缺席/空账路径两键恒空(与 retired 同生死)。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('fake_old', (now - timedelta(days=4)).isoformat(timespec='seconds')),
        ('run_20260912_000000', now.isoformat(timespec='seconds')),
    ])
    r = enforce_journal_retention(jp, now=now)
    assert set(r['segments']) == {'fake_old', 'run_20260912_000000'}
    assert set(r['reasons']) == set(r['retired']) == {'fake_old'}
    r_none = enforce_journal_retention(tmp_path / 'nope' / 'journal.jsonl')
    assert r_none['segments'] == [] and r_none['reasons'] == {}


def test_install_exit_hooks_arms_retirement_follower(monkeypatch) -> None:
    """生产武装点锁:defects.install_exit_hooks 把台账跟随清理接进 kernel
    槽(monkeypatch 槽注入器防进程级残留;装配序 = 本点先于
    install_state_telemetry,清理趟触发时槽已就位)。"""
    from sr_od.application.currency_war.telemetry import defects, recorder
    armed: list[object] = []
    monkeypatch.setattr(cw_state_journal, 'set_retirement_follower',
                        lambda fn: armed.append(fn))
    defects.install_exit_hooks()
    assert armed == [recorder.follow_journal_retirement], \
        '武装实现 = recorder.follow_journal_retirement(台账文件名单一源在本域)'


def test_assembly_cleanup_fires_follower_end_to_end(tmp_path: Path) -> None:
    """端到端联动:journal 装配趟(生产唯一触发点)→ 段裁决 summary →
    跟随者 → 台账段清理 + manifest。共享段跟随 + 孤儿段自评同趟各验。"""
    from sr_od.application.currency_war.telemetry.recorder import (
        follow_journal_retirement,
    )
    now = datetime.now()
    # journal:fake_old(4 天,超短窗,journal 侧淘汰)/ 活跃实机段(留)
    jp = _mk_journal(tmp_path, [
        ('fake_old', (now - timedelta(days=4)).isoformat(timespec='seconds')),
        ('run_20260912_000000', now.isoformat(timespec='seconds')),
    ])
    # 台账:fake_old(共享,跟随去)/ 40 天实机孤儿段(自评去)/ 活跃段(留)
    lp = _mk_ledger(tmp_path, [
        ('fake_old', [_days_ago(4)]),
        ('run_20260701_000000', [_days_ago(40)]),
        ('run_20260912_000000', [_days_ago(0)]),
    ])
    cw_state_journal.set_retirement_follower(follow_journal_retirement)
    try:
        cw_state_journal.install_state_telemetry(
            jp, flush_every=1, run_id_provider=lambda: '')
        assert _ledger_run_ids(lp) == {'run_20260912_000000'}, \
            '装配趟联动:共享段(fake_old)跟随去 + 孤儿段(40 天实机)自评去'
        reasons = {m['run_id']: m['reason'] for m in _read_manifest(tmp_path)}
        assert reasons == {'fake_old': 'age_non_real',
                           'run_20260701_000000': 'age_real'}
    finally:
        cw_state_journal.reset_state_telemetry()
        cw_state_journal.set_retirement_follower(None)
