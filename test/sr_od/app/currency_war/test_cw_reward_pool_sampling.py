"""ADR-0292 reward/supply Δ池采样锁(批㉗ F3/F4;EARLY_WIN_DELTA 真值化)。

批㉗ F4 断言的奖励轮「右胖尾 mean 9.15/p90+39」经语料复核为**跨 run
配对伪影**(同 run 差分 n=43 全 +2;胖尾/负值样本只出现在跨 run 相邻
行)——本批落地的是诚实真值化:reward/supply 结算由恒 EARLY_WIN_DELTA
改 Δ池经验分布采样,池缺回退常数。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from sr_od.application.currency_war.data import cw_battle_tables as tables
from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim import pool as sim_pool
from sr_od.application.currency_war.sim import runner
from sr_od.application.currency_war.sim.checks.pool import (
    REWARD_POOL_TRUTH_MEAN,
    check_reward_delta_pool_bucket_lock,
)


def _reward_snap(tmp_path: Path, reward_buckets: dict) -> Path:
    """构造含自定义 reward 池的 JSON 快照(resolve_pool Path 模式;
    ADR-0362 起池形状 {节点:{位面:{桶:[Δ]}}},构造带 plane=1 层)。"""
    pool = {'battle': {1: {0: [-11] * 6, 1: [-6] * 6}},
            'reward': {1: {int(b): list(v)
                           for b, v in reward_buckets.items()}}}
    fp = sim_pool.pool_fingerprint(pool)
    p = tmp_path / 'snap.json'
    p.write_text(json.dumps(
        {'meta': {'fingerprint': fp}, 'snapshot': {
            n: {str(pl): {str(b): v for b, v in bs.items()}
                for pl, bs in planes.items()} for n, planes in pool.items()}},
        ensure_ascii=False), encoding='utf-8')
    return p


def test_reward_deltas_sampled_from_pool(tmp_path: Path) -> None:
    """结算接线:reward 轮 Δ 来自池经验分布(含胖尾/负值可采样)。"""
    buckets = {6: [2] * 8 + [17, 25], 9: [2] * 6 + [-3]}
    snap = _reward_snap(tmp_path, buckets)
    vals = set()
    for seed in range(12):
        r = cw_sim.simulate_p1(seed, pool=snap)
        for _, nt, d, _ in r.hp_events:
            if nt == 'reward':
                vals.add(d)
                assert d in (2, 17, 25, -3)
    # 池的非常数样本确实可达(采样生效,非恒常数)
    assert vals & {17, 25, -3}, f'池胖尾/负值样本不可达: {vals}'


def test_reward_full_pool_fallback_shallow_depth(tmp_path: Path) -> None:
    """浅板深(r1-r2)缺桶 → 全池兜底采样(不退恒常数;ADR-0292)。"""
    # 只给深桶 9:r1 depth∈[3,5] → 桶 3 缺、浅回退 0 缺 → 全池兜底
    # (ADR-0362:合成池带 plane 层 {1: {9: [...]}})
    pool = {'reward': {1: {9: [2] * 5 + [11]}}}
    rng = random.Random(0)
    drawn = {sim_pool.live_delta_for('reward', 4, rng, pool_map=pool)
             for _ in range(30)}
    assert drawn <= {2, 11} and 11 in drawn   # 全池样本可达
    # 池空 → None(调用方回退 EARLY_WIN_DELTA)
    assert sim_pool.live_delta_for('reward', 4, random.Random(0),
                                 pool_map={'reward': {1: {}}}) is None
    assert sim_pool.live_delta_for(
        'supply', 4, random.Random(0), pool_map={}) is None


def test_fallback_pool_reward_delta_is_constant() -> None:
    """fallback 空池:reward/supply 回退 EARLY_WIN_DELTA(两态语义)。"""
    r = cw_sim.simulate_p1(0, pool='fallback')
    rd = [d for _, nt, d, _ in r.hp_events if nt in ('reward', 'supply')]
    assert rd and set(rd) == {tables.EARLY_WIN_DELTA}


def test_snapshot_reward_pool_matches_corpus_truth() -> None:
    """提交快照对拍(regen-robust):reward 池入位、n≥30、
    均值≈语料真值(带形式——ADR-0292 规格原文即「≈」,经检查项
    ±1hp 漂移带+伪影哨兵带断言;池每次局终自动再生,锁瞬时均值
    等值=池耦合 change-detector,再生即红)。supply 无真值锚
    (ADR-0345):合法样本(如 Δ=0)不辖,只锁伪影哨兵带。"""
    pm, _, _ = sim_pool.resolve_pool('snapshot')
    rep = check_reward_delta_pool_bucket_lock(sim_pool.plane_view(pm))
    assert rep['violations'] == 0, rep
    assert rep['reward']['n'] >= 30
    assert abs(rep['reward']['mean'] - REWARD_POOL_TRUTH_MEAN) <= 1.0


def test_reward_lock_catches_drift_and_artifact() -> None:
    """检查项变异:均值漂移 / 跨 run 伪影形态(负值、大正值)必报。
    (ADR-0362:检查项消费 plane=1 视图口径,合成池直接给扁平桶——
    检查代码本身零改动,与 plane_view 输出同形。)"""
    drift = {'reward': {6: [2] * 30 + [9] * 10}}   # 均值 3.75 > 带
    rep = check_reward_delta_pool_bucket_lock(drift)
    assert rep['violations'] >= 1 and any('漂移' in i for i in rep['issues'])
    artifact = {'reward': {6: [2] * 30 + [41, -2]}}   # 批㉗ F4 形态
    rep2 = check_reward_delta_pool_bucket_lock(artifact)
    assert rep2['violations'] >= 1 \
        and any('伪影' in i for i in rep2['issues'])
    starved = {'reward': {6: [2] * 8}}   # n<30:分布证据不足
    rep3 = check_reward_delta_pool_bucket_lock(starved)
    assert rep3['violations'] >= 1
    # 空池(fallback)不辖(同 battle 锁空池语义)
    assert check_reward_delta_pool_bucket_lock({})['violations'] == 0
    # supply(ADR-0345):无真值锚——合法小样本(Δ=0,语料实测
    # 形态)不辖;跨 run 大跳变伪影仍必报(检测价值不降)
    supply_legit = {'supply': {9: [0]}}   # 语料首现真实样本形态
    assert check_reward_delta_pool_bucket_lock(supply_legit)['violations'] == 0
    supply_artifact = {'supply': {9: [0] * 3 + [41]}}   # 批㉗ F4 量级
    rep4 = check_reward_delta_pool_bucket_lock(supply_artifact)
    assert rep4['violations'] >= 1 \
        and any('伪影' in i for i in rep4['issues'])


def test_pool_build_never_mixes_runs(tmp_path: Path) -> None:
    """跨 run 配对伪影防线:生成器/池构建按 run 分组——上一 run 末行
    hp 与下一 run 首个奖励行 hp 的差分(批㉗ F4 伪影源)不入池。"""
    d = tmp_path / 'replay'
    d.mkdir()
    (d / 'decisions.jsonl').write_text(
        json.dumps({'run_id': 'r1', 'plane': 1, 'round_num': 1,
                    'state': {'board': {'仙舟': 6}, 'deployed': []}},
                   ensure_ascii=False) + '\n'
        + json.dumps({'run_id': 'r2', 'plane': 1, 'round_num': 1,
                      'state': {'board': {'仙舟': 6}, 'deployed': []}},
                     ensure_ascii=False) + '\n'
        + json.dumps({'run_id': 'r2', 'plane': 1, 'round_num': 2,
                      'state': {'board': {'仙舟': 6}, 'deployed': []}},
                      ensure_ascii=False) + '\n',
        encoding='utf-8')
    # r1 末行 hp 30 → r2 首行(奖励)hp 71:全局相邻差分 = +41(伪影)
    (d / 'outcomes.jsonl').write_text(
        json.dumps({'run_id': 'r1', 'plane': 1, 'round_num': 1,
                    'node_type': '普通战斗', 'hp_after': 30},
                   ensure_ascii=False) + '\n'
        + json.dumps({'run_id': 'r2', 'plane': 1, 'round_num': 1,
                      'node_type': '奖励', 'hp_after': 71},
                     ensure_ascii=False) + '\n'
        + json.dumps({'run_id': 'r2', 'plane': 1, 'round_num': 2,
                      'node_type': '奖励', 'hp_after': 73},
                      ensure_ascii=False) + '\n',
        encoding='utf-8')
    pool, _ = sim_pool._pool_from_replay(d)
    # ADR-0362:差分归属后行位面——reward 行 plane=1,桶挂 plane=1 层
    assert pool.get('reward') == {1: {6: [2]}}   # 只有 r2 同 run 差分 +2
    assert 41 not in [x for v in pool['reward'][1].values() for x in v]


def test_sampler_v4_and_snapshot_selfconsistent() -> None:
    """采样器版本(ADR-0404 起 v10——boss 桶键 Σboard→净星深;
    v11=ADR-0407 encounter 桶键 depth→rung;v8/v9=ADR-0362
    plane 维键化,note 链与常量错位自 v10 对齐;本锁语义=版本入指纹
    +快照自洽)。"""
    assert sim_pool._SAMPLER_VERSION == 11
    m, fp, src = sim_pool.resolve_pool('snapshot')
    assert src == 'snapshot'
    from sr_od.application.currency_war.data import cw_delta_pool_data
    assert fp == cw_delta_pool_data.META['fingerprint']
    assert cw_delta_pool_data.META['sampler_version'] == 11
    # 池语义变更使指纹与旧版快照(…/fd48f135/bab146c6 系)可区分
    assert not fp.startswith(('d891233d', '066c4185', '886f8a39',
                              'fd48f135', 'bab146c6'))


def test_batch_report_embeds_reward_lock() -> None:
    """simulate_p1_batch 内嵌 reward 分布锁(fallback 空池不辖=0)。"""
    rep = runner.simulate_p1_batch(3, pool='fallback', ledger=False)
    cv = rep['checks_violations']
    assert 'reward_delta_pool_bucket_lock' in cv
    assert cv['reward_delta_pool_bucket_lock']['violations'] == 0




