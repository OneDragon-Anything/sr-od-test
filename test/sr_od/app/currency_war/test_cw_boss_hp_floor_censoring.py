# -*- coding: utf-8 -*-
"""批39 新检查 check_boss_hp_floor_censoring 的 sr-od-test 锁。

来源:压测官批39(报告 sim_压测_批39/报告.md);r9 boss 语料判读口径
守卫。覆盖:删失披露 note/killed 断裂红/败局 hp 未降红/胜局不辖/
无 boss 行不辖/显式 hp_before 键优先。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_boss_hp_floor_censoring as chk,
)


def _row(nt: str = 'boss', killed: bool | None = False,
         hp_after: int = 30, hp_before: int | None = None,
         rnd: int = 9) -> dict:
    d: dict = {'run_id': 'run_x', 'round_num': rnd, 'node_type': nt,
               'killed': killed, 'hp_after': hp_after}
    if hp_before is not None:
        d['hp_before'] = hp_before
    return d


class TestBossHpFloorCensoring:
    def test_censored_disclosure(self) -> None:
        """killed=False 且 hp_after==1 → 不红但 censor_note 披露行号。"""
        rows = [_row(hp_after=1)]  # 上一行缺省,i=0 无 hp_before
        rows = [{'run_id': 'run_x', 'round_num': 8, 'node_type': '普通战斗',
                 'killed': False, 'hp_after': 20}, _row(hp_after=1)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['censored_rows'] == 1
        assert r['censored_idx'] == [1]
        assert r['censor_note'] is not None and '右删失' in r['censor_note']

    def test_bad_label_violation(self) -> None:
        """boss killed=None → 采集断裂红(批㊲同型)。"""
        rows = [_row(killed=None, hp_after=5, hp_before=50)]
        r = chk(rows)
        assert r['violations'] >= 1
        assert any('采集断裂' in v for v in r['detail'])

    def test_hp_jump_violation(self) -> None:
        """killed=False 但 hp 未降(3→58)→ 跳变红(接管帧错值)。"""
        rows = [{'run_id': 'run_x', 'round_num': 8, 'node_type': '奖励',
                 'killed': False, 'hp_after': 3},
                _row(killed=False, hp_after=58, rnd=9)]
        r = chk(rows)
        assert r['violations'] >= 1
        assert any('未降' in v for v in r['detail'])

    def test_win_not_governed(self) -> None:
        """killed=True 的 boss 行 → 不辖(胜局 hp 变化合法)。"""
        rows = [{'run_id': 'run_x', 'round_num': 8, 'node_type': '奖励',
                 'killed': False, 'hp_after': 3},
                _row(killed=True, hp_after=60, rnd=9)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['censored_rows'] == 0
        assert r['censor_note'] is None

    def test_no_boss_rows(self) -> None:
        """无 boss 行 → 不辖。"""
        rows = [_row(nt='普通战斗', hp_after=50)]
        assert chk(rows)['violations'] == 0

    def test_explicit_hp_before_key(self) -> None:
        """显式 hp_before 键优先于上一行 hp_after。"""
        rows = [{'run_id': 'run_x', 'round_num': 8, 'node_type': '奖励',
                 'killed': False, 'hp_after': 99},
                _row(hp_before=50, hp_after=20)]
        # 显式 50→20 降 30,合法非删失
        r = chk(rows)
        assert r['violations'] == 0
        assert r['censored_rows'] == 0

    def test_missing_hp_after_violation(self) -> None:
        """批40 补:killed=False 但 hp_after 缺失 → 采集缺口红。"""
        rows = [_row(hp_after=None, hp_before=50)]  # type: ignore[arg-type]
        r = chk(rows)
        assert r['violations'] == 1
        assert 'hp_after 缺失' in r['detail'][0]

    def test_hp_after_zero_censored_disclosure(self) -> None:
        """批41 改判:killed=False 且 hp_after==0 = 合法团灭形态 → 不红,
        与 ==1 同族按删失披露(note 级)。批40 原判「写端矛盾」语义倒置
        (killed=玩家击败对手,团灭 killed=False 恰正确;写端失败屏
        hp=0 是 ground truth,HP_MIN=0 可解析真 0)。"""
        rows = [_row(hp_after=0, hp_before=50)]
        r = chk(rows)
        assert r['violations'] == 0
        assert r['censored_rows'] == 1
        assert r['censored_idx'] == [0]
        assert r['censor_note'] is not None and '团灭' in r['censor_note']

    def test_hp_before_no_cross_run_backfill(self) -> None:
        """批41 补:hp_before 缺省回填上一行须同 run_id——上一局末 hp
        不是本局 boss 前值,跨 run 回填会产出伪「hp 未降」违规。"""
        rows = [
            {'run_id': 'run_a', 'round_num': 9, 'node_type': '普通战斗',
             'killed': False, 'hp_after': 80},
            # run_b 首行 boss,无显式 hp_before:不得继承 run_a 的 80
            _row(hp_after=90, rnd=9),
        ]
        rows[1]['run_id'] = 'run_b'
        r = chk(rows)
        assert r['violations'] == 0   # 跨 run:hp_before=None,不比不红

    def test_hp_before_same_run_backfill_still_works(self) -> None:
        """批41 守卫不误伤:同 run 内上一行回填照常(掉血合法不红)。"""
        rows = [
            {'run_id': 'run_x', 'round_num': 8, 'node_type': '普通战斗',
             'killed': False, 'hp_after': 95},
            _row(hp_after=70, rnd=9),
        ]
        r = chk(rows)
        assert r['violations'] == 0
