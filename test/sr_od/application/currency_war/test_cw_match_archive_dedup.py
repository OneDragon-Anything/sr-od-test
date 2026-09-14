"""CW 按局档案跨档段去重锁面(match_archive 跨档归属收敛守卫 + 核验)。

出处 = telemetry/match_archive.py ``_converge_cross_archive_ownership`` /
``find_cross_archive_segment_dups``;口径单一源 = telemetry-reading.md
「决策独有段(零结算段)按段首 ts 归前局」+ 模块 docstring 归局骨架节。

病灶(T-242,实证 run_20260908_210431):旧装配口径时代的存量档案把
续段错误组进了后开的新局(match_g_20260909_084216 段集含该续段),而
该档案常落水位线以下(assemble_pending 永久跳过)、判读直读 JSON 又不
经 load_archive 读端重装配——同一 journal 行集内嵌两个档案,跨档对照
双计。锁四件事:
1. 装配收尾守卫按当前归属口径收敛:源流在的档案整体重装配(派生列
   一并自愈);
2. 源流失的档案定向剪枝(段集+切片摘除、``pruned_segments`` 显影、
   非归属段的孤本条目禁动);
3. ``find_cross_archive_segment_dups`` 对守卫收敛不了的孤立双档(两档
   案持有同段且段源流均已清)仍显影;
4. 水位线以下的双计档案经 assemble_pending 收尾守卫同样收敛(生产
   病灶形态),且收敛幂等(重复装配不重复剪枝)。
"""

from __future__ import annotations

import json
from pathlib import Path

from sr_od.application.currency_war.telemetry import match_archive as ma

_G_A = 'g_20260908_100000'
_G_C = 'g_20260909_080000'
_G_D = 'g_20260908_090000'
_R_A = 'run_20260908_100000'
_R_B = 'run_20260908_120000'
_R_C = 'run_20260909_080000'
_R_D = 'run_20260908_090000'


def _row(rid: str, ts: str, plane: int, round_num: int) -> dict:
    """最小 journal write 行:行型核心字段 + 节点键(段首帧判据消费面)。"""
    return {
        'v': 1, 'ts': ts, 'run_id': rid, 'row': 'write',
        'field': 'hp', 'after': 48,
        'state': {'values': {'node': {'plane': plane, 'round_num': round_num,
                                      'kind': 'prep'},
                             'hp': 48, 'gold': 10}},
    }


def _write_journal(rd: Path, rows: list[dict]) -> None:
    p = rd / 'state' / 'journal.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _write_archive(md: Path, gid: str, seg_rids: list[str],
                   slice_rows: dict[str, list[dict]]) -> None:
    """伪造旧口径存量档案(守卫/核验的最小消费面:game_id+segments+slices)。"""
    md.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema_version': 11,
        'game_id': gid,
        'segments': [{'run_id': rid} for rid in seg_rids],
        'slices': slice_rows,
    }
    (md / f'match_{gid}.json').write_text(
        json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def _read_archive(md: Path, gid: str) -> dict:
    return json.loads((md / f'match_{gid}.json').read_text(encoding='utf-8'))


def _seg_rids(archive: dict) -> list[str]:
    return [s.get('run_id') for s in archive.get('segments') or []]


def _journal_rows(rd: Path) -> list[dict]:
    # A 局 (1,1) 新局;B 续段 (2,6) 段首 ts 落 A 后、C 前 → 归前局 A;
    # C (1,1) 新局(后继新局 = 曾夺段的旧 bug 形态对勒面)
    return [
        _row(_R_A, '2026-09-08T10:00:00', 1, 1),
        _row(_R_A, '2026-09-08T10:05:00', 1, 2),
        _row(_R_B, '2026-09-08T12:00:00', 2, 6),
        _row(_R_B, '2026-09-08T12:01:00', 2, 6),
        _row(_R_C, '2026-09-09T08:00:00', 1, 1),
    ]


def _seed_wrong_archive(md: Path, gid: str, seg_rids: list[str],
                        b_rows: list[dict]) -> None:
    """伪造旧口径错误档案:段集持 B(本档段行在前,续段切片在后)。"""
    own = {'g_20260909_080000': _R_C, 'g_20260908_090000': _R_D}[gid]
    own_rows = [_row(own, '2026-09-08T09:00:00' if own == _R_D
                     else '2026-09-09T08:00:00', 1, 1)]
    _write_archive(md, gid, seg_rids,
                   {'op_journal.jsonl': own_rows + b_rows})


def test_assemble_converges_double_counted_segment(tmp_path: Path):
    """装配收尾守卫收敛双计段:正确归属档案持有、错误档案摘除、核验归零。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    b_rows = [_row(_R_B, '2026-09-08T12:00:00', 2, 6),
              _row(_R_B, '2026-09-08T12:01:00', 2, 6)]
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B], b_rows)
    # 仅错误档案持有时(归属档案尚未入档),单档案不构成双计,核验不误报
    assert ma.find_cross_archive_segment_dups(rd) == []

    assert ma.assemble_game(rd, _G_A) is not None
    # A 档案(正确归属)持有 B 全部行;C 档案切片行级无同段重复
    a_rows = [r for rows in _read_archive(md, _G_A).get('slices', {}).values()
              for r in rows]
    assert {json.dumps(r, sort_keys=True) for r in b_rows} <= {
        json.dumps(r, sort_keys=True) for r in a_rows}
    for rows in _read_archive(md, _G_C).get('slices', {}).values():
        assert all(r.get('run_id') != _R_B for r in rows)
    assert ma.find_cross_archive_segment_dups(rd) == []


def test_rebuild_converges_archive_with_live_source(tmp_path: Path):
    """源流在的错误档案(续段被旧口径组进后开新局)整体重装配收敛。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B],
                        [_row(_R_B, '2026-09-08T12:00:00', 2, 6)])

    assert ma.assemble_game(rd, _G_A) is not None
    arch_c = _read_archive(md, _G_C)
    assert _seg_rids(arch_c) == [_R_C]   # B 摘除,按当前口径只剩本局段
    assert 'pruned_segments' not in arch_c   # 重装配路径不产生剪枝记录


def test_prune_converges_archive_with_lost_source(tmp_path: Path):
    """源流失的错误档案定向剪枝:摘段+切片,显影记录,孤本条目禁动。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_D, [_R_D, _R_B],
                        [_row(_R_B, '2026-09-08T12:00:00', 2, 6)])

    assert ma.assemble_game(rd, _G_A) is not None
    arch_d = _read_archive(md, _G_D)
    # D 无源流(不在分组):B 归属 A → 剪枝;D 段自身为唯一存档,禁动
    assert _seg_rids(arch_d) == [_R_D]
    for rows in arch_d.get('slices', {}).values():
        assert all(r.get('run_id') != _R_B for r in rows)
    pruned = arch_d.get('pruned_segments')
    assert pruned == [{'run_id': _R_B, 'owned_by': _G_A,
                       'reason': ma._PRUNE_REASON}]


def test_orphan_double_archive_still_reported(tmp_path: Path):
    """守卫收敛不了的孤立双档(同段源流失)由核验显影,不静默。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    # journal 无 B 行(源流失):两档案各持 B,守卫无归属判据可依 → 不动
    _write_journal(rd, [_row(_R_A, '2026-09-08T10:00:00', 1, 1)])
    b_row = [_row(_R_B, '2026-09-08T12:00:00', 2, 6)]
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B], b_row)
    _seed_wrong_archive(md, _G_D, [_R_D, _R_B], b_row)

    assert ma.assemble_game(rd, _G_A) is not None
    dups = ma.find_cross_archive_segment_dups(rd)
    # archives 按档案文件名序(守卫无归属判据可依的孤立形态,纯显影)
    assert dups == [{'run_id': _R_B, 'archives': [_G_D, _G_C]}]


def test_assemble_pending_converges_below_watermark(tmp_path: Path):
    """水位线以下的双计档案经 assemble_pending 收尾守卫收敛(生产病灶形态)。"""
    rd = tmp_path / 'live'
    md = ma.matches_dir(rd)
    _write_journal(rd, _journal_rows(rd))
    _seed_wrong_archive(md, _G_C, [_R_C, _R_B],
                        [_row(_R_B, '2026-09-08T12:00:00', 2, 6)])

    done = ma.assemble_pending(rd)   # 首跑落水位线,不装存量局;守卫仍收敛
    assert done == []
    assert _seg_rids(_read_archive(md, _G_C)) == [_R_C]

    # 幂等:重复触发守卫不重复剪枝/重装配
    ma.assemble_pending(rd)
    assert _seg_rids(_read_archive(md, _G_C)) == [_R_C]
    assert ma.find_cross_archive_segment_dups(rd) == []
