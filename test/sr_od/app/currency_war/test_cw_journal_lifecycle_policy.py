"""journal 寿命策略锁(T-77:实机/非实机分型窗 + 体积兜底窗 + manifest reason 显影)。

正本 = docs/develop/sr_od/application/currency_war/game_state/journal.md
§5「寿命(滚动清理)策略」;契约上位 = r5-migration-plan.md §4-5(retirement.md
§6-5 直迁形态:run 段整体单元 / archived_out 显影 / 保留窗=跨期语料窗 /
清理策略随真实数据积累定)。

真实数据依据(2026-09-12 实测):现役账面 251.6MB 全部段为非实机段且段龄
<2 天——30 天跨期语料窗对其永无效力,分型窗与体积窗是该实测直接产物。

W3 既有锁(段粒度/archive 显影/活跃段保护/缺文件 noop)在
test_cw_w3_journal_only_reads.py §5 延续,本文件不重复。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sr_od.application.currency_war.kernel.cw_state_journal import (
    JOURNAL_MAX_BYTES,
    JOURNAL_NONLIVE_RETENTION_DAYS,
    JOURNAL_RETENTION_DAYS,
    RETIREMENT_MANIFEST_NAME,
    enforce_journal_retention,
)


def _mk_journal(tmp_path: Path, segs: list[tuple[str, str, int]]) -> Path:
    """造一份多段 journal(段 = (run_id, 全行同一 ts, 行数);行 = 自足快照行)。"""
    jp = tmp_path / 'state' / 'journal.jsonl'
    jp.parent.mkdir(parents=True, exist_ok=True)
    with jp.open('w', encoding='utf-8') as f:
        for rid, ts, n in segs:
            for i in range(n):
                f.write(json.dumps({
                    'v': i + 1, 'ts': ts, 'run_id': rid, 'row': 'write',
                    'field': 'gold', 'after': 1, 'state': {},
                    'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
                    'note': '', 'evidence_refs': []}, ensure_ascii=False)
                    + '\n')
    return jp


def _kept_run_ids(jp: Path) -> set[str]:
    out: set[str] = set()
    for ln in jp.read_text(encoding='utf-8').strip().splitlines():
        row = json.loads(ln)
        rid = row.get('run_id') if isinstance(row, dict) else None
        if rid:
            out.add(str(rid))
    return out


def _read_manifest(tmp_path: Path) -> list[dict]:
    man = tmp_path / 'state' / RETIREMENT_MANIFEST_NAME
    return [json.loads(ln) for ln in
            man.read_text(encoding='utf-8').strip().splitlines()]


# ============================================================ 常量单一源

def test_policy_constants() -> None:
    """三窗常量单一源(kernel/cw_state_journal;数值依据见各常量注)。

    30 = 跨期语料窗(实机段);3 = 非实机段短窗(批后隔日复查);
    192MB = 体积兜底上界(3 天正常积累 + 一个压测段余量,真实积累实测)。"""
    assert JOURNAL_RETENTION_DAYS == 30
    assert JOURNAL_NONLIVE_RETENTION_DAYS == 3
    assert JOURNAL_MAX_BYTES == 192 * 1024 * 1024


def test_real_run_id_re_consistency_with_archive_reader() -> None:
    """实机段分型正则与判读装配端同源(各自持字面量,一致性由本锁钉住):
    kernel 禁依 telemetry、哨兵是跨仓独立脚本,三方无共享 import 面——
    字面量漂移 = 清理面与判读面对「实机段」的判定分叉(清理误删判读语料
    或判读采信已清段),一致性是分型窗安全的结构性前提。"""
    import re

    from sr_od.application.currency_war.kernel.cw_state_journal import (
        REAL_RUN_ID_RE,
    )
    from sr_od.application.currency_war.telemetry.match_archive import (
        _JOURNAL_RUN_ID_RE,
    )
    assert REAL_RUN_ID_RE.pattern == _JOURNAL_RUN_ID_RE.pattern
    # 形态语义抽验:实机铸造形态收,非实机段形态拒
    assert REAL_RUN_ID_RE.match('run_20260912_101010')
    assert not REAL_RUN_ID_RE.match('fake_20260911')
    assert not REAL_RUN_ID_RE.match('run_dt_test')


# ============================================================ 分型天窗边界

def test_split_age_windows_boundary(tmp_path: Path) -> None:
    """分型窗边界:实机段 31 天清 / 29 天留(跨期语料窗);非实机段 4 天清 /
    2 天留(短窗)——两窗边界各侧一笔,变异(删分型/换窗值)必红。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        # 实机形态段:31 天(超 30 天窗)清 / 29 天留
        ('run_20260810_000000',
         (now - timedelta(days=31)).isoformat(timespec='seconds'), 1),
        ('run_20260812_000000',
         (now - timedelta(days=29)).isoformat(timespec='seconds'), 1),
        # 活跃段(段末行最新)永不清理
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
        # 非实机段:4 天(超 3 天窗)清 / 2 天留
        ('fake_old', (now - timedelta(days=4)).isoformat(timespec='seconds'), 1),
        ('fake_fresh', (now - timedelta(days=2)).isoformat(timespec='seconds'), 1),
    ])
    r = enforce_journal_retention(jp, now=now)
    assert r['checked'] == 5
    assert set(r['retired']) == {'run_20260810_000000', 'fake_old'}
    assert _kept_run_ids(jp) == {
        'run_20260812_000000', 'run_20260912_000000', 'fake_fresh'}


def test_non_real_window_keeps_fresh_segment_for_review(tmp_path: Path) -> None:
    """短窗内非实机段保留 = 批后隔日复查窗(短窗的存在语义):
    1 天非实机段留;清段判据只认段龄,不认段大小(小段也照清,防「小段
    永远留着」的体积暗积)。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('fake_yesterday',
         (now - timedelta(days=1)).isoformat(timespec='seconds'), 1),
        ('fake_tiny',
         (now - timedelta(days=10)).isoformat(timespec='seconds'), 1),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    r = enforce_journal_retention(jp, now=now)
    assert r['retired'] == ['fake_tiny']
    assert 'fake_yesterday' in _kept_run_ids(jp)


# ============================================================ 体积兜底窗

def test_size_budget_retires_oldest_first_cross_type(tmp_path: Path) -> None:
    """体积窗:天窗清完后仍超 → 从最老段继续淘汰(**不分型**,天窗内实机段
    也在淘汰序内——容量约束优先于语料窗承诺,manifest reason 显影归因);
    活跃段保护;达标即停。"""
    now = datetime.now()
    # 4 段各 ~50 行小行,总 ~200 行;max_bytes 传 120 行等价字节量
    jp = _mk_journal(tmp_path, [
        ('fake_a', (now - timedelta(days=1)).isoformat(timespec='seconds'), 50),
        ('run_20260911_000000',
         (now - timedelta(days=2)).isoformat(timespec='seconds'), 50),
        ('fake_b', (now - timedelta(days=0, hours=5)).isoformat(
            timespec='seconds'), 50),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    r = enforce_journal_retention(jp, now=now, max_bytes=1)
    # 天窗零清段 → 体积窗从最老(fake_a)逐段清:fake_a → 实机段
    # run_20260911 → fake_b 达「只剩活跃段」下限
    assert set(r['retired']) == {'fake_a', 'run_20260911_000000', 'fake_b'}
    assert _kept_run_ids(jp) == {'run_20260912_000000'}, \
        '活跃段永不清理(体积窗也不破)'
    reasons = {m['run_id']: m['reason'] for m in _read_manifest(tmp_path)}
    assert reasons['fake_a'] == 'size_budget'
    assert reasons['run_20260911_000000'] == 'size_budget', \
        '体积窗不分型:天窗内实机段也被容量回收(reason 显影归因)'


def test_size_budget_stops_at_budget_and_keeps_order(tmp_path: Path) -> None:
    """体积窗达标即停(不是清到只剩活跃段):逐段从最老清,累计到 ≤ 上限
    停手,更年轻的段保留。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('fake_a', (now - timedelta(days=2)).isoformat(timespec='seconds'), 30),
        ('fake_b', (now - timedelta(days=1)).isoformat(timespec='seconds'), 30),
        ('fake_c', (now - timedelta(hours=1)).isoformat(timespec='seconds'), 30),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    r = enforce_journal_retention(jp, now=now, max_bytes=1)
    assert set(r['retired']) == {'fake_a', 'fake_b', 'fake_c'}, \
        '上限 1 字节 = 全部可清段都在淘汰序(活跃段兜底保)'
    # 上限放宽到「清最老一段后即达标」:fake_b/fake_c 保留(阈值 = 清 a 后
    # 的账面字节,按 kernel 同口径从文件行实测,不猜行大小)
    jp2 = _mk_journal(tmp_path / 'b', [
        ('fake_a', (now - timedelta(days=2)).isoformat(timespec='seconds'), 30),
        ('fake_b', (now - timedelta(days=1)).isoformat(timespec='seconds'), 30),
        ('fake_c', (now - timedelta(hours=1)).isoformat(timespec='seconds'), 30),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    seg_bytes: dict[str, int] = {}
    for ln in jp2.read_text(encoding='utf-8').strip().splitlines():
        row = json.loads(ln)
        rid = str(row.get('run_id'))
        seg_bytes[rid] = seg_bytes.get(rid, 0) + len(json.dumps(
            row, ensure_ascii=False)) + 1
    budget_after_one = jp2.stat().st_size - seg_bytes['fake_a']
    r2 = enforce_journal_retention(jp2, now=now, max_bytes=budget_after_one)
    assert set(r2['retired']) == {'fake_a'}
    assert {'fake_b', 'fake_c'} <= _kept_run_ids(jp2), '达标即停,年轻段保留'


def test_size_budget_floor_keeps_undroppable_segments(tmp_path: Path) -> None:
    """只剩不可清段(活跃段 + 无 ts 段)时如实超上限保留(段整体单元禁切
    半段——超窗是段整体性的必然边界,宁超不切)。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 50),
    ])
    # 追加一段无 ts 行(不可判龄不可清)
    with jp.open('a', encoding='utf-8') as f:
        f.write(json.dumps({
            'v': 1, 'run_id': 'fake_nots', 'row': 'write', 'field': 'gold',
            'after': 1, 'state': {},
            'sig': {'family': 'obs', 'actor': 'X', 'mode': 'read'},
            'note': '', 'evidence_refs': []}, ensure_ascii=False) + '\n')
    r = enforce_journal_retention(jp, now=now, max_bytes=1)
    assert r['retired'] == [], '无可清段:如实超上限,不切半段'
    assert jp.stat().st_size > 1


# ============================================================ manifest 显影

def test_manifest_reason_keys_cover_all_gates(tmp_path: Path) -> None:
    """manifest reason 键覆盖三道闸(判读考古辨「哪道闸清的」):
    天窗两型 + 体积窗各一行,archived_out 语义延续(W3 既有锁)。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('run_20260801_000000',
         (now - timedelta(days=40)).isoformat(timespec='seconds'), 1),
        ('fake_ancient',
         (now - timedelta(days=10)).isoformat(timespec='seconds'), 1),
        ('fake_big', (now - timedelta(days=1)).isoformat(timespec='seconds'), 20),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    enforce_journal_retention(jp, now=now, max_bytes=1)
    reasons = {m['run_id']: m['reason'] for m in _read_manifest(tmp_path)}
    assert reasons['run_20260801_000000'] == 'age_real'
    assert reasons['fake_ancient'] == 'age_non_real'
    assert reasons['fake_big'] == 'size_budget'
    for m in _read_manifest(tmp_path):
        assert m['archived_out'] is True
        assert {'run_id', 'reason', 'rows', 'retired_at'} <= set(m)


# ============================================================ 幂等(体积窗后)

def test_idempotent_after_size_budget_pass(tmp_path: Path) -> None:
    """体积窗大清后二跑零增量(天窗幂等 = W3 既有锁,体积窗路径补锁):
    清后账面 ≤ 上限,二跑不再清。"""
    now = datetime.now()
    jp = _mk_journal(tmp_path, [
        ('fake_a', (now - timedelta(days=2)).isoformat(timespec='seconds'), 30),
        ('fake_b', (now - timedelta(hours=1)).isoformat(timespec='seconds'), 30),
        ('run_20260912_000000', now.isoformat(timespec='seconds'), 1),
    ])
    r1 = enforce_journal_retention(jp, now=now, max_bytes=1)
    assert r1['retired'], '首跑触发体积窗回收'
    r2 = enforce_journal_retention(jp, now=now, max_bytes=1)
    assert r2 == {'checked': r2['checked'], 'retired': [], 'rows_dropped': 0}, \
        '幂等:清后二跑零增量'
