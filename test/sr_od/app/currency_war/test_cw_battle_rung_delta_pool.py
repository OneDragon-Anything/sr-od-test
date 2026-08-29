# -*- coding: utf-8 -*-
"""ADR-0279(批⑬):battle Δ池按 rung 一维分桶锁。

批⑬ F1/F2/F4:battle r0 n=26/-11.5、r1 n=24/-6.3 双主桶达标且
梯度真实;depth-only 池对 d9 成型局高估战损 ~6.4hp/场(sim
hp_ge_60 4% vs 实机 32% 裂口的最大已定量化分量)。
"""
from __future__ import annotations

import inspect
import json
import random
from pathlib import Path

from sr_od.application.currency_war import cw_delta_pool_data
from sr_od.application.currency_war import cw_sim as _sim
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib
from sr_od.application.currency_war.cw_sim_checks import (
    BATTLE_RUNG_TRUTH,
    check_battle_rung_pool_bucket_lock,
)


def test_snapshot_battle_buckets_are_rung_domain() -> None:
    """快照 battle 桶键全落 rung 域(0-4);depth 域键(≥6)= 未生效。
    (ADR-0362:消费 plane=1 视图;P2 桶另辖。)"""
    m, _, _ = _sim.resolve_pool('snapshot')
    m = _sim.plane_view(m)
    battle = m['battle']
    assert battle, 'battle 池缺失'
    assert all(int(b) <= 4 for b in battle), \
        f'battle 桶键落 depth 域: {sorted(battle)}'
    # 双主桶存在(批⑬ F1:r0=26/r1=24 达标)
    assert len(battle.get(0, [])) >= 10
    assert len(battle.get(1, [])) >= 10


def test_snapshot_battle_rung_means_match_b13_truth() -> None:
    """双主桶均值符合批⑬量级(r0≈-11.5 / r1≈-6.3,漂移 ≤3hp;
    ADR-0362:plane=1 视图口径)。"""
    m, _, _ = _sim.resolve_pool('snapshot')
    m = _sim.plane_view(m)
    for rg, truth in BATTLE_RUNG_TRUTH.items():
        v = m['battle'][rg]
        mean = sum(v) / len(v)
        assert abs(mean - truth) <= 3.0, \
            f'battle rung{rg} 均值 {mean:+.1f} 距批⑬真值 {truth:+.1f} 漂移>3hp'


def test_snapshot_encounter_rung_keyed_v11() -> None:
    """v11(ADR-0407):encounter 桶键已迁 rung——桶键全落 0-4 域
    且主桶(rung0/rung1)达标(批⑬ F1 的「暂 depth 分桶」边界声明
    已被扩容+键查证解禁取代)。"""
    m, _, _ = _sim.resolve_pool('snapshot')
    m = _sim.plane_view(m)
    enc = m.get('encounter') or {}
    assert enc, 'encounter 池缺失'
    depth_like = sorted(b for b in enc if int(b) >= 6)
    assert not depth_like, f'encounter 桶键落 depth 域: {depth_like}'
    assert len(enc.get(0, [])) >= 10, 'encounter rung0 主桶饥饿'
    assert len(enc.get(1, [])) >= 10, 'encounter rung1 主桶饥饿'


def test_snapshot_boss_pool_domain_covers_extremes() -> None:
    """批⑬ F7:boss 池域不缩(重生成不丢失既有极值样本 min≤-36)。

    F7 原始读数 -42 是决策帧口径(run154910 attach 局);outcomes
    差分口径下该局 boss Δ=71→58=-13 已入池——差分不可达 -42,
    扩域诉求兑现为「域不缩」(ADR-0279 Considered Options)。
    """
    m, _, _ = _sim.resolve_pool('snapshot')
    m = _sim.plane_view(m)
    boss_vals = [d for v in m['boss'].values() for d in v]
    assert min(boss_vals) <= -36


def test_check_battle_rung_pool_bucket_lock_unit() -> None:
    """检查双向锁:depth 键池/缺主桶/漂移>3hp/encounter depth 化 → 报。"""
    # 旧 depth 键池(未重生成)→ 报
    old = {'battle': {6: [-7] * 10, 9: [-6] * 10},
           'encounter': {9: [-13] * 5}, 'boss': {12: [-25] * 5}}
    rep = check_battle_rung_pool_bucket_lock(old)
    assert rep['violations'] >= 1
    assert any('rung 分桶未生效' in i for i in rep['issues'])
    # 缺 rung0 主桶 → 报
    miss = {'battle': {1: [-6] * 10}}
    assert check_battle_rung_pool_bucket_lock(miss)['violations'] == 1
    # 均值漂移>3hp → 报(r0 真值 -11.5,给 -5)
    drift = {'battle': {0: [-5] * 10, 1: [-6] * 10}}
    rep_d = check_battle_rung_pool_bucket_lock(drift)
    assert any('漂移' in i for i in rep_d['issues'])
    # encounter 意外 depth 化(≥6)→ 报(v11/ADR-0407 辖域反转)
    bad_enc = {'battle': {0: [-11] * 10, 1: [-6] * 10},
               'encounter': {9: [-13] * 5}, 'boss': {12: [-42] * 5}}
    rep_e = check_battle_rung_pool_bucket_lock(bad_enc)
    assert any('rung 分桶未生效' in i for i in rep_e['issues'])
    # 健康池(真值表量级 + encounter rung 键 + boss 域覆盖)→ 0 违规
    good = {'battle': {0: [-11] * 26, 1: [-6] * 24, 2: [-5] * 9},
            'encounter': {0: [-13] * 5}, 'boss': {12: [-36] * 5}}
    assert check_battle_rung_pool_bucket_lock(good)['violations'] == 0
    # 空池(fallback)不辖
    rep_n = check_battle_rung_pool_bucket_lock({})
    assert rep_n['violations'] == 0 and '不辖' in rep_n['note']


def test_live_delta_battle_rung_sampling_paths() -> None:
    """battle 采样:rung 桶命中 / 高 rung 下探 / 键截幅入 rung 域
    (ADR-0362:合成池带 plane 层 {1: {桶: [Δ]}})。"""
    pool = {'battle': {1: {0: [-10] * 5, 1: [-5] * 5}}}
    rng = random.Random(0)
    assert all(_sim.live_delta_for('battle', 0, rng, pool_map=pool) == -10
               for _ in range(10))
    assert all(_sim.live_delta_for('battle', 1, rng, pool_map=pool) == -5
               for _ in range(10))
    # rung2 桶缺 → 下探 rung1(信息最接近的可及桶)
    assert all(_sim.live_delta_for('battle', 2, rng, pool_map=pool) == -5
               for _ in range(10))
    # 超 rung 域键(如误传 depth)截幅入 0-4 后下探
    assert all(_sim.live_delta_for('battle', 9, rng, pool_map=pool) == -5
               for _ in range(10))
    # 池空 → None(调用方旧模型)
    assert _sim.live_delta_for('battle', 1, random.Random(1),
                               pool_map={}) is None


def test_live_delta_battle_guard_merges_adjacent_rungs() -> None:
    """battle 防饥饿守卫:薄 rung 桶与相邻 rung(±1)合并采样。"""
    pool = {'battle': {1: {1: [-3] * 6, 2: [-6]}}}   # rung2 n=1 饥饿
    rng = random.Random(0)
    drawn = [_sim.live_delta_for('battle', 2, rng, pool_map=pool)
             for _ in range(200)]
    # 唯一样本 -6 以 1/7 权重参与(合并非剔除),远非恒定
    assert drawn.count(-6) <= 60
    assert -3 in drawn


def test_pool_from_replay_battle_rung_keys(tmp_path: Path) -> None:
    """auto 池构建:battle 桶键 = rung(board_before + deployed join)。"""
    def _dec(rn: int, board: dict, deployed: list[dict]) -> str:
        return json.dumps({
            'run_id': 'r1', 'plane': 1, 'round_num': rn,
            'state': {'board': board, 'deployed': deployed}},
            ensure_ascii=False)

    dep_seele = [{'char_id': '希儿', 'faction': '贝洛伯格'},
                 {'char_id': '', 'faction': '量子同频'},
                 {'char_id': '', 'faction': '量子同频'}]
    (tmp_path / 'decisions.jsonl').write_text('\n'.join([
        _dec(1, {'散': 1}, []),
        _dec(2, {'仙舟': 3}, []),
        _dec(3, {'持续伤害': 2, '列车同行': 2, '量子同频': 2}, dep_seele),
        _dec(4, {'散': 7}, []),
    ]) + '\n', encoding='utf-8')

    def _out(rn: int, nt: str, hp: int, board: dict) -> str:
        return json.dumps({
            'run_id': 'r1', 'plane': 1, 'round_num': rn,
            'node_type': nt, 'hp_after': hp, 'board_before': board},
            ensure_ascii=False)

    (tmp_path / 'outcomes.jsonl').write_text('\n'.join([
        _out(1, '奖励', 100, {}),
        _out(2, '普通战斗', 90, {'仙舟': 3}),           # rung1 → 桶1
        _out(3, '普通战斗', 75, {'持续伤害': 2, '列车同行': 2,
                                 '量子同频': 2}),        # rung3 → 桶3
        _out(4, '遭遇', 60, {'散': 7}),                  # depth 桶6
    ]) + '\n', encoding='utf-8')

    _sim.reset_resolved_cache()
    pool, meta = _sim._pool_from_replay(tmp_path)
    # ADR-0362:桶挂 plane=1 层(差分归属后行位面)
    # v11/ADR-0407:encounter 桶键=rung(board_before {'散':7} 无
    # 四体系 → rung0;encounter 意为该节点从 75→60 的差分 -15)
    assert pool['battle'] == {1: {1: [-10], 3: [-15]}}
    assert pool['encounter'] == {1: {0: [-15]}}
    assert meta['runs'] == {'r1': 4}


def test_settle_wiring_battle_rung_single_source() -> None:
    """结算接线:simulate_p1 battle 走 _settle_rung(rung 定义单一源
    = _engines_count;ADR-0308 起 boss 回退胜负面换 W31 阶梯,boss
    侧不再 rung 键)。"""
    src = inspect.getsource(_sim.simulate_p1)
    assert '_settle_rung' in src
    assert "live_delta_for('battle', _settle_rung(st)" in src
    boss_src = inspect.getsource(_calib.boss_settle_delta)
    assert 'node_win_p' in boss_src   # ADR-0308 胜负面单一取值口
    assert '_engines_count' not in boss_src   # 单一源收口,不散落内联


def test_batch_report_embeds_battle_rung_lock() -> None:
    """simulate_p1_batch 内嵌 battle_rung_pool_bucket_lock(批⑬ 检查项)。"""
    rep = _sim.simulate_p1_batch(3, pool='fallback', ledger=False)
    cv = rep['checks_violations']
    assert 'battle_rung_pool_bucket_lock' in cv
    assert cv['battle_rung_pool_bucket_lock']['violations'] == 0


def test_snapshot_meta_carries_battle_rung_table() -> None:
    """生成器把 battle rung 真值表锁进 META(批⑬检查项设计表原文)。"""
    table = cw_delta_pool_data.META.get('battle_rung')
    assert isinstance(table, dict) and table
    assert {'0', '1'} <= set(table)
    for row in table.values():
        assert {'n', 'mean'} <= set(row)
