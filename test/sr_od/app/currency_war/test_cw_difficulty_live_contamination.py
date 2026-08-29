# -*- coding: utf-8 -*-
"""批37 新检查 check_difficulty_curve_live_contamination 的 sr-od-test 锁。

来源:压测官批37(报告 sim_压测_批37/报告.md);probe 中 6 断言由
leader 审后转锁(2026-08-24;批39 清死断言 + 补部分污染 note 锁)。
覆盖:污染红/历史 schema 红/全 live 绿/值相交绿(note 披露)/空不
辖/无读数不辖。
"""
from __future__ import annotations

from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_difficulty_curve_live_contamination as chk,
)


def _row(ed: int | None, live: bool | None, rnd: int = 1) -> dict:
    d: dict = {'plane': 1, 'round_num': rnd, 'enemy_difficulty': ed}
    if live is not None:
        d['enemy_difficulty_live'] = live
    return d


class TestDifficultyLiveContamination:
    def test_mixed_disjoint_sets_violation(self) -> None:
        """live 真值集与 non-live 值集不相交并存 → 污染红(全帧口径判废)。"""
        rows = [_row(8, True, i) for i in range(3)] + \
               [_row(108, False, i) for i in range(3, 6)]
        r = chk(rows)
        assert r['violations'] >= 1
        assert any('污染' in v or '判废' in v for v in r['detail'])

    def test_partial_contamination_overlapping_note(self) -> None:
        """批39:live 与 non-live 并存但值集相交 → 不红,但 mixed_note
        必须披露混帧计数与两组值集(部分污染不再静默放行)。"""
        rows = [_row(8, True, i) for i in range(2)] + \
               [_row(108, False, i) for i in range(2, 3)] + \
               [_row(8, False, i) for i in range(3, 5)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['mixed_note'] is not None
        assert 'live 2 帧' in r['mixed_note']
        assert 'non-live 3 帧' in r['mixed_note']
        assert r['live_vals'] == [8]
        assert r['nonlive_vals'] == [8, 108]

    def test_missing_flag_schema_violation(self) -> None:
        """有难度读数但缺保真位 → schema 红(历史局调用方豁免)。"""
        rows = [_row(108, None, i) for i in range(5)]
        r = chk(rows)
        assert r['violations'] >= 1

    def test_all_live_green(self) -> None:
        """全 live 真值帧(即使有爬升)→ 0 红(真爬升合法)。"""
        rows = [_row(8 + i, True, i) for i in range(5)]
        assert chk(rows)['violations'] == 0

    def test_overlapping_values_green(self) -> None:
        """live 与 non-live 值集相交 → 0 红(同值兜底无害)。"""
        rows = [_row(8, True, i) for i in range(3)] + \
               [_row(8, False, i) for i in range(3, 6)]
        assert chk(rows)['violations'] == 0

    def test_empty_rows_not_governed(self) -> None:
        """空行 → 不辖 0 红。"""
        assert chk([])['violations'] == 0

    def test_no_reading_not_governed(self) -> None:
        """无难度读数帧 → 不辖 0 红。"""
        rows = [_row(None, True, i) for i in range(3)]
        assert chk(rows)['violations'] == 0
