# -*- coding: utf-8 -*-
"""test_cw_delta_pool 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- b37_delta_pool_audit: test_cw_b37_delta_pool_audit.py
- adr0306_delta_pool_expansion: test_cw_adr0306_delta_pool_expansion.py
- battle_rung_delta_pool: test_cw_battle_rung_delta_pool.py
- delta_pool_snapshot: test_cw_delta_pool_snapshot.py
- adr0407_encounter_rung_pool: test_cw_adr0407_encounter_rung_pool.py
- w109_pool_pipeline: test_cw_w109_pool_pipeline.py
- r409_delta_pool_starvation_guard: test_cw_r409_delta_pool_starvation_guard.py(2026-09-03 瘦身批并入)
- r411_pool_no_cost_truncation: test_cw_r411_pool_no_cost_truncation.py(2026-09-03 瘦身批并入;n4/n5 手抄常数改注册表现算,2000 次抽样按纪律 12 降到 500)
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== b37_delta_pool_audit ====================

import pytest

from sr_od.application.currency_war.sim import pool as cw_sim
from sr_od.application.currency_war.data.cw_delta_pool_data import  META as SNAP_META

from sr_od.application.currency_war.sim.checks.calib import check_ab_verdict_claim

from sr_od.application.currency_war.sim.checks.corpus import check_boss_rung_corpus_sample_gate, check_delta_pool_poverty_selfconsistency, check_paired_prefork_wave_identity

# --------------------------------------------------------------------
# check_delta_pool_poverty_selfconsistency
# --------------------------------------------------------------------

def _mini_pool() -> dict:
    """合成池:battle r0 富 / r2 薄 / r3 缺;boss 桶9 薄。"""
    return {
        'battle': {0: [-10] * 12, 2: [-7] * 9},
        'boss': {9: [-20] * 2},
    }


def _mini_meta() -> dict:
    return {'bucket_poverty': [
        'battle:桶1(缺)', 'battle:桶2(n=9)', 'battle:桶3(缺)',
        'battle:桶4(缺)', 'boss:桶9(n=2)',
    ]}


def test_poverty_selfconsistency_real_snapshot_green() -> None:
    """真实快照(resolve_pool 产物)↔ META 双向自洽 = 0 违规
    (锁生成器 _poverty_list 与池内容同源;重生成后仍须自洽;
    ADR-0362:检查项辖 plane=1 视图,与批内 pool-level 检查同口径)。"""
    pm, _, _ = cw_sim.resolve_pool('snapshot')
    out = check_delta_pool_poverty_selfconsistency(
        cw_sim.plane_view(pm), SNAP_META)
    assert out['violations'] == 0, f'{out}'
    assert out['disclosed_n'] == out['pool_poor_n']


def test_poverty_selfconsistency_synthetic_green() -> None:
    out = check_delta_pool_poverty_selfconsistency(
        _mini_pool(), _mini_meta())
    assert out['violations'] == 0, f'{out}'


def test_poverty_selfconsistency_meta_none_skips() -> None:
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), None)
    assert out['violations'] == 0
    assert '不辖' in out['note']


def test_poverty_selfconsistency_empty_pool_skips() -> None:
    out = check_delta_pool_poverty_selfconsistency({}, _mini_meta())
    assert out['violations'] == 0


def test_poverty_selfconsistency_format_drift_flags() -> None:
    """变异杀①:格式漂移(全角括号/空格)→ 解析失败违规
    (旧 coverage 的字符串精确匹配下这是静默失配,批㊲ 攻击面)。"""
    drifted = {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                                  'battle:桶4(缺)',
                                  'boss:桶9(n=9)]']}   # 全角括号
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), drifted)
    assert out['violations'] >= 1
    assert any('不可解析' in v for v in out['detail'])


def test_poverty_selfconsistency_undisclosed_flags() -> None:
    """变异杀②:池贫困未披露(删 boss 披露行)→ 违规。"""
    meta = {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                               'battle:桶4(缺)']}
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), meta)
    assert out['violations'] >= 1
    assert any('未披露' in v for v in out['detail'])


def test_poverty_selfconsistency_stale_flags() -> None:
    """变异杀③:过期披露(池中不贫困的桶出现在披露)→ 违规。"""
    meta = _mini_meta()
    meta['bucket_poverty'] = list(meta['bucket_poverty']) + [
        'battle:桶0(n=9)']
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), meta)
    assert out['violations'] >= 1
    assert any('过期' in v for v in out['detail'])


def test_poverty_selfconsistency_n_mismatch_flags() -> None:
    """变异杀④:披露 n 值与池不符(池 n=8 披露 n=9)→ 违规。"""
    pool = _mini_pool()
    pool['battle'][2] = [-7] * 8
    out = check_delta_pool_poverty_selfconsistency(pool, _mini_meta())
    assert out['violations'] >= 1
    assert any('n 值' in v for v in out['detail'])


# --------------------------------------------------------------------
# (check_boss_win_p_cache_freshness 六锁已随 ADR-0308 删除——被检
#  机制 boss_win_p/_BOSS_WIN_P_EXTRAPOLATED 缓存已废弃,锁死码无义)
# --------------------------------------------------------------------

# --------------------------------------------------------------------
# check_boss_rung_corpus_sample_gate
# --------------------------------------------------------------------

def _boss_rows_b37() -> list[dict]:
    """批㊲ 探针实证形态(2026-08-25 语料 17 行):r0 0/5、
    r1 0/9+1None、r2 1/2。"""
    return (
        [{'rung': 0, 'killed': False}] * 5
        + [{'rung': 1, 'killed': False}] * 9
        + [{'rung': 1, 'killed': None}]
        + [{'rung': 2, 'killed': True}, {'rung': 2, 'killed': False}])


def test_boss_gate_b37_shape_green() -> None:
    out = check_boss_rung_corpus_sample_gate(_boss_rows_b37())
    assert out['violations'] == 0
    assert out['buckets']['1']['win_killed'] == 0.0
    assert out['buckets']['1']['killed_known'] == 9
    assert out['buckets']['2']['win_killed'] == 0.5
    assert out['rung3plus_exists'] is False
    # 样本门逐桶属性(批㉗ F6 known≥3):rung1 known=9 已就绪、
    # rung2 known=2 未就绪;批㊲ 反证针对 rung≥3 直拟合(缺桶)
    assert out['buckets']['1']['direct_fit_ready'] is True
    assert out['buckets']['2']['direct_fit_ready'] is False


def test_boss_gate_all_unknown_flags() -> None:
    """变异杀:killed 全 None(采集断裂)→ 违规。"""
    out = check_boss_rung_corpus_sample_gate(
        [{'rung': 1, 'killed': None}] * 5)
    assert out['violations'] == 1
    assert '采集断裂' in out['detail'][0]


def test_boss_gate_empty_skips() -> None:
    out = check_boss_rung_corpus_sample_gate([])
    assert out['violations'] == 0
    assert '不辖' in out['note']


def test_boss_gate_direct_fit_ready_tracks() -> None:
    """样本门追踪:known≥3 的桶标 direct_fit_ready(直拟合就绪)。"""
    rows = [{'rung': 3, 'killed': True}] * 2 + \
           [{'rung': 3, 'killed': False}] + \
           [{'rung': 2, 'killed': True}] * 3
    out = check_boss_rung_corpus_sample_gate(rows)
    assert out['buckets']['3']['direct_fit_ready'] is True
    assert out['buckets']['2']['direct_fit_ready'] is True
    assert out['rung3plus_exists'] is True


# --------------------------------------------------------------------
# check_ab_verdict_claim 词表反转(批㊲ 加固)
# --------------------------------------------------------------------

@pytest.mark.parametrize('claim', ['首超', 'wins', '更高', 'better', ''])
def test_verdict_claim_unknown_wording_now_flagged(claim: str) -> None:
    """批㊲ 攻击面锁:换措辞旧版绕过(词表命中才辖)→ 新版默认辖。
    n=30 + 带内差 → 至少 1 违规。"""
    out = check_ab_verdict_claim(3.0, 14.0, 30, claim)
    assert out['directional'] is True
    assert out['violations'] >= 1, (
        f'claim={claim!r} 绕过判罚面 = 词表反转回归')


@pytest.mark.parametrize('claim', ['noise', 'noise_band', 'tie', '平局',
                                   '持平', '无差异', 'parity'])
def test_verdict_claim_nondirectional_whitelist_still_exempt(claim: str
                                                             ) -> None:
    out = check_ab_verdict_claim(-3.0, 14.0, 30, claim)
    assert out['directional'] is False
    assert out['violations'] == 0


@pytest.mark.parametrize('claim', ['leads', 'behind', '领先', '落后'])
def test_verdict_claim_legacy_directional_words_still_flagged(claim: str
                                                              ) -> None:
    """旧方向词在反转后仍辖(回归,不因词表反转漏放)。"""
    out = check_ab_verdict_claim(-3.0, 14.0, 30, claim)
    assert out['directional'] is True
    assert out['violations'] >= 1


# --------------------------------------------------------------------
# check_paired_prefork_wave_identity 扩全波(批㊲ 加固)
# --------------------------------------------------------------------

def _row(rn: int, waves: list[list[str]],
         actions: list[dict] | None = None) -> dict:
    return {
        'round_num': rn,
        'sim': {'shop_waves': [{'cards': [{'name': n} for n in w]}
                               for w in waves]},
        'actions': actions or [],
    }


def test_prefork_full_wave_synthetic_green() -> None:
    """合成 green:两臂全波一致(含同轮刷新波)+ 动作 sig 一致 → 0。"""
    a = [[_row(1, [['青雀', '姬子'], ['三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    b = [[_row(1, [['青雀', '姬子'], ['三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] == 0, f'{out}'


def test_prefork_second_wave_drift_now_flagged() -> None:
    """批㊲ 攻击面锁:同轮 wave0 一致、wave1(刷新波)不一致且动作
    sig 一致 → 旧版(只比首波)0 违规=漏检;新版必红。"""
    a = [[_row(1, [['青雀'], ['姬子', '三月七']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    b = [[_row(1, [['青雀'], ['希儿', '娜塔莎']],
               actions=[{'__type__': 'RefreshShop'}])],
         [_row(2, [['希儿']])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] >= 1, (
        '第二波(刷新波)不一致未被捕获 = 全波扩展回归(旧版漏检面)')


def test_prefork_first_wave_drift_still_flagged() -> None:
    """回归:首波不一致(批㊱ 原判据)仍必红。"""
    a = [[_row(1, [['青雀'], ['姬子']],
               actions=[{'__type__': 'RefreshShop'}])]]
    b = [[_row(1, [['三月七'], ['姬子']],
               actions=[{'__type__': 'RefreshShop'}])]]
    out = check_paired_prefork_wave_identity(a, b)
    assert out['violations'] >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-q'])



# ==================== adr0306_delta_pool_expansion ====================

from sr_od.application.currency_war.sim import engine_p1 as _adr0306_delta_pool_expansion_cw_sim
from sr_od.application.currency_war.sim import pool
from sr_od.application.currency_war.sim import runner
from sr_od.application.currency_war.data import cw_delta_pool_data
from sr_od.application.currency_war.data.cw_battle_tables import  NODE_WIN_P_BY_TYPE as tables_NODE_WIN_P_BY_TYPE, NODE_WIN_P_LADDER as tables_NODE_WIN_P_LADDER
from sr_od.application.currency_war.kernel import cw_battle_calib as calib

from sr_od.application.currency_war.sim.checks.pool import check_delta_pool_bucket_coverage


def test_node_win_p_ladder_w31_source_of_truth() -> None:
    """ADR-0308:回退层胜负面单一取值口 = W31 实测阶梯。

    - 逐轮实测组合优先:battle r3 0.30 / r4 0.29、encounter r7 0.04、
      boss r9 0.05(常量与 W31_报告 §2 数字一致);
    - 未观测组合退类型边际(battle 0.29 / encounter 0.04 / boss 0.05);
    - reward/supply 恒 1.0(零战力节点实测全胜);
    - 未知节点类型兜底 0.0(保守)。
    """
    assert calib.node_win_p('battle', 3) == 0.30
    assert calib.node_win_p('battle', 4) == 0.29
    assert calib.node_win_p('encounter', 7) == 0.04
    assert calib.node_win_p('boss', 9) == 0.05
    # 未观测组合 → 类型边际
    assert calib.node_win_p('battle', 6) == tables_NODE_WIN_P_BY_TYPE['battle']
    assert calib.node_win_p('encounter', 6) == 0.04
    assert calib.node_win_p('boss', 8) == 0.05
    for nt in ('reward', 'supply'):
        for rn in (1, 2, 5, 8):
            assert calib.node_win_p(nt, rn) == 1.0
    assert calib.node_win_p('unknown_node', 5) == 0.0


def test_node_win_p_values_all_valid_probabilities() -> None:
    """阶梯全体值 ∈ [0,1](胜率语义自洽)。"""
    for (_nt, _rn), v in tables_NODE_WIN_P_LADDER.items():
        assert 0.0 <= v <= 1.0, (_nt, _rn, v)
    for nt, v in tables_NODE_WIN_P_BY_TYPE.items():
        assert 0.0 <= v <= 1.0, (nt, v)


def test_snapshot_meta_win_stats_fields() -> None:
    """META battle_rung 逐桶带双口径胜率统计(权威=killed)。"""
    table = cw_delta_pool_data.META.get('battle_rung')
    assert isinstance(table, dict) and table
    for rg, row in table.items():
        assert {'n', 'mean', 'win_killed', 'win_delta', 'killed_known',
                'killed_unknown', 'sign_disagree'} <= set(row), rg
        # 分母披露自洽:killed 已知+未知 = 样本数
        assert row['killed_known'] + row['killed_unknown'] == row['n']
        if row['win_killed'] is not None:
            assert 0.0 <= row['win_killed'] <= 1.0
    # 语料真值锁(2026-08-25 语料,rung2 killed 已知 6 行 4 胜):
    # 重生成扩样后允许漂移,但权威口径统计必须仍在(动态读 META,
    # 只锁「rung≥2 存在 killed 口径值」的存在性)
    assert any((table[r] or {}).get('win_killed') is not None
               for r in table if int(r) >= 2)


def test_boss_win_p_machinery_removed() -> None:
    """ADR-0308:rung 外推机制整体废弃——残留 = 死码回潮信号。"""
    for gone in ('boss_win_p', 'BOSS_WIN_P_BY_ENGINES',
                 'BOSS_WIN_P_EXTRAPOLATED_MIN_RUNG', 'BOSS_WIN_P_FALLBACK',
                 '_BOSS_WIN_P_EXTRAPOLATED'):
        assert gone not in _adr0306_delta_pool_expansion_cw_sim.__dict__, \
            f'{gone} 已随 ADR-0308 废弃,不应残留(死码回潮)'


def test_check_delta_pool_bucket_coverage_unit() -> None:
    """贫困桶必须披露:未披露=违规;披露=0;缺桶同样辖。"""
    poor_pool = {'battle': {0: [-11] * 12, 1: [-6] * 9},
                 'encounter': {6: [-28]}}
    # 无 meta(披露载体缺失)→ 贫困桶全违规
    rep = check_delta_pool_bucket_coverage(poor_pool, meta=None)
    assert rep['violations'] >= 2
    assert any('battle:桶1' in p for p in rep['undisclosed'])
    # meta 披露齐 → 0 违规(battle 桶2/3/4 缺桶也须在披露里)
    meta = {'bucket_poverty': [
        'battle:桶1(n=9)', 'battle:桶2(缺)', 'battle:桶3(缺)',
        'battle:桶4(缺)', 'encounter:桶6(n=1)']}
    assert check_delta_pool_bucket_coverage(
        poor_pool, meta=meta)['violations'] == 0
    # 全桶充足且 battle rung0-4 齐 → 无贫困
    rich = {'battle': {r: [-5] * 10 for r in range(5)}}
    assert check_delta_pool_bucket_coverage(
        rich, meta={'bucket_poverty': []})['violations'] == 0


def test_snapshot_coverage_zero_undisclosed() -> None:
    """提交快照:贫困披露与池内容自洽(0 未披露;ADR-0362:辖
    plane=1 视图,与批内 pool-level 检查同口径)。"""
    pool_map, _, _ = pool.resolve_pool('snapshot')
    rep = check_delta_pool_bucket_coverage(
        pool.plane_view(pool_map), meta=cw_delta_pool_data.META)
    assert rep['violations'] == 0


def test_batch_report_embeds_coverage_check() -> None:
    """simulate_p1_batch 内嵌 delta_pool_bucket_coverage(ADR-0306 件5)。"""
    rep = runner.simulate_p1_batch(3, pool='fallback', ledger=False,
                                   checks=True)
    cv = rep['checks_violations']
    assert 'delta_pool_bucket_coverage' in cv
    assert cv['delta_pool_bucket_coverage']['violations'] == 0


def test_boss_settle_uses_win_p_single_source() -> None:
    """boss_settle_delta 掷胜走 node_win_p 单一取值口(不散落内联表)。"""
    import inspect
    src = inspect.getsource(calib.boss_settle_delta)
    assert 'node_win_p' in src
    assert 'NODE_WIN_P_LADDER[' not in src





# ==================== battle_rung_delta_pool ====================

import inspect
import json
import random
from pathlib import Path

from sr_od.application.currency_war.data import cw_delta_pool_data as _battle_rung_delta_pool_cw_delta_pool_data
from sr_od.application.currency_war.sim import engine_p1 as _sim
from sr_od.application.currency_war.sim import pool as sim_pool
from sr_od.application.currency_war.sim import runner as _battle_rung_delta_pool_runner
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib

from sr_od.application.currency_war.sim.checks.pool import BATTLE_RUNG_TRUTH, check_battle_rung_pool_bucket_lock


def test_snapshot_battle_buckets_are_rung_domain() -> None:
    """快照 battle 桶键全落 rung 域(0-4);depth 域键(≥6)= 未生效。
    (ADR-0362:消费 plane=1 视图;P2 桶另辖。)"""
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
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
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
    for rg, truth in BATTLE_RUNG_TRUTH.items():
        v = m['battle'][rg]
        mean = sum(v) / len(v)
        assert abs(mean - truth) <= 3.0, \
            f'battle rung{rg} 均值 {mean:+.1f} 距批⑬真值 {truth:+.1f} 漂移>3hp'


def test_snapshot_encounter_rung_keyed_v11() -> None:
    """v11(ADR-0407):encounter 桶键已迁 rung——桶键全落 0-4 域
    且主桶(rung0/rung1)达标(批⑬ F1 的「暂 depth 分桶」边界声明
    已被扩容+键查证解禁取代)。"""
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
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
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
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
    assert all(sim_pool.live_delta_for('battle', 0, rng, pool_map=pool) == -10
               for _ in range(10))
    assert all(sim_pool.live_delta_for('battle', 1, rng, pool_map=pool) == -5
               for _ in range(10))
    # rung2 桶缺 → 下探 rung1(信息最接近的可及桶)
    assert all(sim_pool.live_delta_for('battle', 2, rng, pool_map=pool) == -5
               for _ in range(10))
    # 超 rung 域键(如误传 depth)截幅入 0-4 后下探
    assert all(sim_pool.live_delta_for('battle', 9, rng, pool_map=pool) == -5
               for _ in range(10))
    # 池空 → None(调用方旧模型)
    assert sim_pool.live_delta_for('battle', 1, random.Random(1),
                               pool_map={}) is None


def test_live_delta_battle_guard_merges_adjacent_rungs() -> None:
    """battle 防饥饿守卫:薄 rung 桶与相邻 rung(±1)合并采样。"""
    pool = {'battle': {1: {1: [-3] * 6, 2: [-6]}}}   # rung2 n=1 饥饿
    rng = random.Random(0)
    drawn = [sim_pool.live_delta_for('battle', 2, rng, pool_map=pool)
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

    pool, meta = sim_pool._pool_from_replay(tmp_path)
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
    rep = _battle_rung_delta_pool_runner.simulate_p1_batch(3, pool='fallback', ledger=False)
    cv = rep['checks_violations']
    assert 'battle_rung_pool_bucket_lock' in cv
    assert cv['battle_rung_pool_bucket_lock']['violations'] == 0


def test_snapshot_meta_carries_battle_rung_table() -> None:
    """生成器把 battle rung 真值表锁进 META(批⑬检查项设计表原文)。"""
    table = _battle_rung_delta_pool_cw_delta_pool_data.META.get('battle_rung')
    assert isinstance(table, dict) and table
    assert {'0', '1'} <= set(table)
    for row in table.values():
        assert {'n', 'mean'} <= set(row)






# ==================== delta_pool_snapshot ====================

import json as _delta_pool_snapshot_json
from pathlib import Path as _delta_pool_snapshot_Path

import pytest as _delta_pool_snapshot_pytest

from sr_od.application.currency_war.data import cw_delta_pool_data as _delta_pool_snapshot_cw_delta_pool_data
from sr_od.application.currency_war.sim import engine_p1 as _delta_pool_snapshot_sim
from sr_od.application.currency_war.sim import pool as _delta_pool_snapshot_pool
from sr_od.application.currency_war.sim import runner as _delta_pool_snapshot_runner
def test_snapshot_module_loads_and_fingerprint_selfconsistent() -> None:
    """提交快照可加载;META 指纹与重算一致(手改会被发现)。"""
    fp = _delta_pool_snapshot_pool.pool_fingerprint(_delta_pool_snapshot_cw_delta_pool_data.SNAPSHOT)
    assert fp == _delta_pool_snapshot_cw_delta_pool_data.META['fingerprint']
    # 可信标签口径:丢弃计数已披露(2026-08-22 retrofix 后死链
    # 历史标签置 None,不入池)
    assert 'unlabeled_dropped' in _delta_pool_snapshot_cw_delta_pool_data.META


def test_resolve_pool_snapshot_and_fallback() -> None:
    """snapshot 命中提交快照(归一 int 桶键);fallback 显式空池+打标。"""
    m, fp, src = _delta_pool_snapshot_pool.resolve_pool('snapshot')
    assert src == 'snapshot'
    assert fp == _delta_pool_snapshot_cw_delta_pool_data.META['fingerprint']
    # 归一化后语义等价(int 桶键;_delta_pool_snapshot_json round-trip 的 str 键会让
    # live_delta_for 的 int 查询全 miss = 快照静默失效)
    # ADR-0362:位面层同样归一 int 键
    assert m == _delta_pool_snapshot_pool._normalize_pool(_delta_pool_snapshot_cw_delta_pool_data.SNAPSHOT)
    assert all(isinstance(b, int)
               for planes in m.values() for b in planes)
    assert all(isinstance(b, int)
               for planes in m.values()
               for buckets in planes.values() for b in buckets)
    assert m.get('battle')

    m2, fp2, src2 = _delta_pool_snapshot_pool.resolve_pool('fallback')
    assert src2 == 'fallback'
    assert m2 == {}
    assert fp2 == _delta_pool_snapshot_pool.pool_fingerprint({})


def test_resolve_pool_auto_missing_raises_loudly(tmp_path: None | _delta_pool_snapshot_Path) -> None:
    """auto 缺源 raise(不静默回退空池)——blocker 修复的核心语义。"""
    with _delta_pool_snapshot_pytest.raises(_delta_pool_snapshot_pool.DeltaPoolUnavailable):
        _delta_pool_snapshot_pool.resolve_pool('auto', auto_dir=tmp_path / 'nonexistent')


def test_resolve_pool_path_json_snapshot(tmp_path: _delta_pool_snapshot_Path) -> None:
    """Path 模式:JSON 快照文件(生成器 --export-json 产物;
    ADR-0362 起形状 {节点:{位面:{桶:[Δ]}}})。"""
    p = tmp_path / 'snap.json'
    p.write_text(_delta_pool_snapshot_json.dumps(
        {'meta': {}, 'snapshot': {'battle': {1: {6: [-4]}}}},
        ensure_ascii=False), encoding='utf-8')
    m, fp, src = _delta_pool_snapshot_pool.resolve_pool(p)
    assert src == f'path:{p.name}'
    assert m == {'battle': {1: {6: [-4]}}}
    assert fp == _delta_pool_snapshot_pool.pool_fingerprint({'battle': {1: {6: [-4]}}})


def test_simulate_p1_records_pool_identity() -> None:
    """SimResult 带池指纹+来源(跨日基线对照须核指纹一致)。

    供给重校准起指纹含装备发放结构版本位(``+eqgN``)——发放结构是
    行为语义的一部分,新旧结构不可比,跨版本对照必须显式失败。
    """
    r = _delta_pool_snapshot_sim.simulate_p1(42, pool='fallback')
    assert r.pool_source == 'fallback'
    assert r.pool_fingerprint == (
        _delta_pool_snapshot_pool.pool_fingerprint({})
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')
    r2 = _delta_pool_snapshot_sim.simulate_p1(42, pool='snapshot')
    assert r2.pool_source == 'snapshot'
    assert r2.pool_fingerprint == (
        _delta_pool_snapshot_cw_delta_pool_data.META['fingerprint']
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')


def test_batch_report_carries_pool_fingerprint() -> None:
    """批量结果携带池指纹(基线数字可追溯其校准地基)。"""
    s = _delta_pool_snapshot_runner.simulate_p1_batch(10, pool='fallback')
    assert s['pool_source'] == 'fallback'
    assert s['pool_fingerprint'] == (
        _delta_pool_snapshot_pool.pool_fingerprint({})
        + f'+eqg{_sim.EQUIP_GRANT_CALIB_VERSION}')


def test_snapshot_pool_is_live_in_sim() -> None:
    """金丝雀:快照池采样真实命中(防 str 桶键/归一化缺失类静默失效)。

    曾发:json round-trip 把桶键变 '9'(str),live_delta_for 用
    int 查询全 miss → snapshot 模式静默退旧模型而所有结构测试
    仍绿。本锁遍历快照桶,断言至少一次真实采样命中。
    """
    import random

    m, _, _ = _delta_pool_snapshot_pool.resolve_pool('snapshot')
    hit = False
    # ADR-0362:桶在 plane=1 层下
    for node in ('battle', 'boss', 'encounter'):
        for bucket in (m.get(node, {}).get(1) or {}):
            v = _delta_pool_snapshot_pool.live_delta_for(node, bucket, random.Random(1),
                                    pool_map=m)
            if v is not None:
                hit = True
                break
        if hit:
            break
    assert hit, '快照全桶采样 miss = 池静默失效(查 _normalize_pool)'


def test_generator_data_file_discipline() -> None:
    """生成器纪律:数据文件头部带勿手编标记 + 重生成命令。"""
    head = _delta_pool_snapshot_Path(_delta_pool_snapshot_cw_delta_pool_data.__file__).read_text(
        encoding='utf-8')[:600]
    assert '勿手编' in head
    assert 'gen_delta_pool_snapshot.py' in head





# ==================== adr0407_encounter_rung_pool ====================

from sr_od.application.currency_war.sim import engine_p1 as _adr0407_encounter_rung_pool_sim
from sr_od.application.currency_war.sim import pool as _adr0407_encounter_rung_pool_pool
def _p1_means() -> dict[int, float]:
    m, _, _ = _adr0407_encounter_rung_pool_pool.resolve_pool('snapshot')
    m = _adr0407_encounter_rung_pool_pool.plane_view(m)
    enc = m.get('encounter') or {}
    return {int(b): sum(v) / len(v)
            for b, v in enc.items() if len(v) >= 5}


def test_v11_pool_encounter_main_buckets_monotonic() -> None:
    """encounter 主桶均值随 rung 单调趋 0(梯度真实,非随机分箱)。"""
    means = _p1_means()
    assert {0, 1} <= set(means), f'encounter 双主桶缺失: {sorted(means)}'
    assert means[0] < means[1], \
        f'encounter rung 梯度不成立: r0={means[0]:.1f} >= r1={means[1]:.1f}'
    if 2 in means:
        assert means[1] < means[2], \
            f'encounter rung 梯度在 r2 反向: r1={means[1]:.1f} ' \
            f'>= r2={means[2]:.1f}'


def test_v11_settle_wiring_encounter_rung_source() -> None:
    """结算接线:simulate_p1 encounter 走 _settle_rung 单一源
    (与 battle 同式;防「池已 rung 化、采样仍喂 depth」错位)。"""
    import inspect
    src = inspect.getsource(_adr0407_encounter_rung_pool_sim.simulate_p1)
    assert "live_delta_for('encounter', _settle_rung(st)" in src




# ==================== w109_pool_pipeline ====================

import pytest as _w109_pool_pipeline_pytest

from sr_od.application.currency_war.sim import cw_delta_pool_gen
from sr_od.application.currency_war.sim import ledger_hooks


def test_regenerate_frozen_by_default(tmp_path, monkeypatch) -> None:
    """池再生入口可用性锁(F6 改锁,原「退役第一步冻结」语义反转)。

    原锁钉 DeltaPoolFrozen raise(快照停更);F6 语料治理批(编排者
    任务书)裁决撤销冻结——快照仍辖 reward/supply 池与 delta 对照臂,
    含 hp=0 伪影毒行的旧快照必须可再生治理。本锁改钉:再生入口
    正常工作且产物自洽(指纹回写产物 META)。

    密闭化(2026-09-03 测试瘦身批):原实现直读实机 replay 语料并
    回写生产数据文件——与实机局终自动再生管线(W109)构成多写者
    竞态,实机对局期间跑测试必假红(基线实证:收集期导入的 META
    指纹 vs 执行期语料指纹漂移),且违反「测试零真实副作用」纪律。
    改造:合成最小语料(3 行 jsonl,1 条 reward 差分)+ 写目标指
    tmp_path(文件名过 `*_data.py` 写目标白名单),断言只校验本次
    产物自身,不碰生产快照、不随实机语料漂移。
    """
    import json

    src = tmp_path / 'replay'
    src.mkdir()
    (src / 'decisions.jsonl').write_text(
        json.dumps({'run_id': 'r_test', 'plane': 1, 'round_num': 2,
                    'state': {'board': {'c1': 4}, 'deployed': []}},
                   ensure_ascii=False) + '\n', encoding='utf-8')
    (src / 'outcomes.jsonl').write_text(
        json.dumps({'run_id': 'r_test', 'plane': 1, 'round_num': 1,
                    'hp_after': 100}, ensure_ascii=False) + '\n'
        + json.dumps({'run_id': 'r_test', 'plane': 1, 'round_num': 2,
                      'hp_after': 88, 'node_type': '奖励'},
                     ensure_ascii=False) + '\n', encoding='utf-8')
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    fp = cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    assert isinstance(fp, str) and len(fp) == 16
    # 产物自洽:回读本次写出的产物,指纹=返回值,池含本次差分
    # (板深 4 → reward 桶 3;Δ = 88-100 = -12;json 键全字符串化)
    ns: dict = {}
    exec(target.read_text(encoding='utf-8'), ns)
    assert ns['META']['fingerprint'] == fp
    assert ns['META']['source_rows']['decisions.jsonl'] == 1
    assert ns['SNAPSHOT']['reward']['1']['3'] == [-12]


def test_hook_swallows_regeneration_failure(
        monkeypatch: _w109_pool_pipeline_pytest.MonkeyPatch) -> None:
    """局终钩子 best-effort:再生抛异常不外传(局终收尾不被打断)。"""
    def _boom(**kwargs):
        raise RuntimeError('sim_runs 回灌守卫误触发(构造)')

    monkeypatch.setattr(cw_delta_pool_gen, 'regenerate_snapshot', _boom)
    # 不抛即过(返回 None;warning 已由 log 记)
    assert ledger_hooks._regenerate_delta_pool_after_run() is None


# ==================== r409_delta_pool_starvation_guard ====================
# (2026-09-03 瘦身批自 test_cw_r409_delta_pool_starvation_guard.py 原文并入;
# 断言零改动;sim_pool/runner/random 复用前述成员既有绑定)

from sr_od.application.currency_war.sim.checks.pool import (
    check_ab_depth_boundary_confound,
    check_delta_pool_bucket_min_n,
    check_depth_cliff_monotonicity,
)


def test_guard_hungry_bucket_not_deterministic_cliff() -> None:
    """守卫触发:n<5 桶不裸采样——饥饿桶唯一样本不再恒定命中。

    合并候选 = 本桶∪深邻桶(20 样本),饥饿样本 -11 以 1/20
    权重参与(合并非剔除);旧语义下 depth∈[6,8] 的战斗轮
    **恒 -11**(确定性悬崖)是伪惩罚本体。
    (ADR-0279 起 battle 桶键=rung;v11/ADR-0407 起 encounter 同迁
    rung——守卫的 depth 路径锁改用 supply 承载,同一条守卫代码路径。)
    """
    # 桶6 n=1 恒 -11(批③ F1 原始形态);桶9 n=6 健康
    # (ADR-0362:合成池带 plane 层)
    pool = {'supply': {1: {6: [-11],
                           9: [-4, -5, -6, -7, -8, -9]}}}
    rng = random.Random(0)
    drawn = [sim_pool.live_delta_for('supply', 7, rng, pool_map=pool)
             for _ in range(200)]
    assert drawn.count(-11) <= 30   # ≈1/20 权重,远非常数(旧=200)
    assert -4 in drawn and -9 in drawn   # 邻桶样本可达(非恒悬崖)


def test_guard_picks_lower_variance_candidate() -> None:
    """降级选择:邻桶合并候选中取方差最小者(浅邻方差小 → 收敛浅邻)。"""
    pool = {'supply': {1: {
        3: [-3, -4, -5, -6, -7, -8],           # 浅邻:方差小
        6: [-11],                               # 饥饿桶
        9: [-30, -1, -30, -1, -30, -1],         # 深邻:方差大
    }}}
    rng = random.Random(1)
    for _ in range(200):
        v = sim_pool.live_delta_for('supply', 6, rng, pool_map=pool)
        assert v in (-3, -4, -5, -6, -7, -8, -11) or v == -11
        assert v != -30 and v != -1   # 深邻候选(方差大)不入选


def test_guard_tiny_pool_falls_back_to_bare_sample() -> None:
    """极端小池(无邻桶可合并):退回裸样本,语义不破(r340 兼容)。"""
    pool = {'battle': {1: {6: [-3, -5]}}}   # n=2,无邻桶,全池=本桶
    v = sim_pool.live_delta_for('battle', 7, random.Random(1),
                              pool_map=pool)
    assert v in (-3, -5)


def test_guard_preserves_missing_bucket_none() -> None:
    """守卫不改变缺桶两态语义(depth 路径):缺桶且无更浅桶 → None。

    ADR-0279:battle 桶键=rung,全 rung 桶不可达时走**全池兜底**
    (批⑬ F3「池均值兜底」形态,保经验分布方差)而非 None——
    battle 键 0 命中池内合并样本。
    """
    pool = {'battle': {1: {6: [-11], 9: [-4] * 6}}}
    assert sim_pool.live_delta_for('boss', 6, random.Random(1),
                                 pool_map=pool) is None
    assert sim_pool.live_delta_for('battle', 0, random.Random(1),
                                 pool_map=pool) in (-11, -4)


def test_guard_healthy_bucket_unchanged() -> None:
    """n≥5 健康桶照旧裸采样(守卫零影响面)。"""
    pool = {'battle': {1: {6: [-4, -5, -6, -7, -8]}}}
    rng = random.Random(2)
    for _ in range(50):
        v = sim_pool.live_delta_for('battle', 7, rng, pool_map=pool)
        assert v in (-4, -5, -6, -7, -8)


def test_check_delta_pool_bucket_min_n() -> None:
    """检查项 1:饥饿桶审计(批③ 形态:battle 桶6 n=1)。"""
    pool = {'battle': {6: [-11], 9: [-4] * 6},
            'encounter': {9: [-13, 2]}}
    rep = check_delta_pool_bucket_min_n(pool)
    assert rep['violations'] == 2
    assert 'battle:桶6(n=1)' in rep['buckets']
    assert 'encounter:桶9(n=2)' in rep['buckets']
    # 全健康池 / 空池(fallback)零违规
    assert check_delta_pool_bucket_min_n(
        {'battle': {6: [-1] * 5}})['violations'] == 0
    assert check_delta_pool_bucket_min_n({})['violations'] == 0


def test_check_depth_cliff_monotonicity() -> None:
    """检查项 2:可信桶均值随深度单调不减血。

    ADR-0279:battle 桶键=rung(深度单调语义不辖,检查内跳过);
    v11/ADR-0407 起 encounter 同为 rung 键同跳过——本锁用 reward
    承载 depth 路径。
    """
    # 违反:更深桶更痛(桶6 -5 → 桶9 -11)
    bad = {'reward': {6: [-5] * 6, 9: [-11] * 6}}
    rep = check_depth_cliff_monotonicity(bad)
    assert rep['violations'] == 1
    assert 'reward' in rep['pairs'][0]
    # 合规:更深不减血(趋 0 方向单调)
    good = {'reward': {6: [-11] * 6, 9: [-6] * 6, 12: [-2] * 6}}
    assert check_depth_cliff_monotonicity(good)['violations'] == 0
    # 饥饿桶(n<5)不参评——由检查项 1 辖
    skip = {'reward': {6: [-11], 9: [-5] * 6}}
    assert check_depth_cliff_monotonicity(skip)['violations'] == 0
    # battle/encounter(rung 键)不辖:非单调 rung 桶不报(方向锁归
    # battle_rung_pool_bucket_lock 真值表;encounter 为 v11 迁键面)
    rung_pool = {'battle': {0: [-11] * 6, 1: [-6] * 6, 2: [-11] * 6},
                 'encounter': {0: [-11] * 6, 1: [-20] * 6}}
    assert check_depth_cliff_monotonicity(rung_pool)['violations'] == 0


def _r409_battle_row(depth: int) -> dict:
    return {'plane': 1, 'round_num': 3,
            'sim': {'node': 'battle', 'depth': depth, 'delta': -5}}


def test_check_ab_depth_boundary_confound() -> None:
    """检查项 3:两臂深度桶占用不对称 → 池混杂标。"""
    a = [[_r409_battle_row(4), _r409_battle_row(7)]]     # A 跨桶 0/6
    b = [[_r409_battle_row(4), _r409_battle_row(4)]]     # B 只在桶 0
    hits = check_ab_depth_boundary_confound(a, b)
    assert len(hits) == 1
    assert '桶6' in hits[0] and 'A 臂' in hits[0]
    # 对称分布不报
    assert check_ab_depth_boundary_confound(
        [[_r409_battle_row(7)]], [[_r409_battle_row(8)]]) == []
    # 非战斗轮(reward)不入直方图
    reward_row = [{'plane': 1, 'round_num': 1,
                   'sim': {'node': 'reward', 'depth': 7, 'delta': 2}}]
    assert check_ab_depth_boundary_confound(
        [reward_row], []) == []


def test_batch_report_embeds_pool_checks() -> None:
    """simulate_p1_batch 内嵌池级检查(fallback 空池零违规)。"""
    rep = runner.simulate_p1_batch(3, pool='fallback', ledger=False)
    cv = rep['checks_violations']
    assert cv['delta_pool_bucket_min_n']['violations'] == 0
    assert cv['depth_cliff_monotonicity']['violations'] == 0


def test_sampler_version_bumped_and_snapshot_guarded() -> None:
    """采样器版本锁(历次语义: v3=ADR-0279 battle rung 分桶 /
    v4=ADR-0292 reward/supply 池采样 / v5=ADR-0306 胜率外推 /
    v6=ADR-0308 W31 节点×轮次胜率阶梯 / v7=ADR-0312 W50 采样键
    Σboard 全集口径 / v8(快照 note 链记 v9)=ADR-0362 Δ池
    plane 维键化 / v10=ADR-0404 boss 桶键 Σboard→净星深 /
    v11=ADR-0407 encounter 桶键 depth→rung)+ 提交快照自洽。"""
    assert sim_pool._SAMPLER_VERSION == 11
    from sr_od.application.currency_war.data.cw_battle_tables import BUCKET_MIN_N as _BUCKET_MIN_N  # 期 0b 锁改判(N7):单一源迁 data
    assert _BUCKET_MIN_N == 5
    m, fp, src = sim_pool.resolve_pool('snapshot')
    assert src == 'snapshot'
    from sr_od.application.currency_war.data import cw_delta_pool_data
    assert fp == cw_delta_pool_data.META['fingerprint']


# ==================== r411_pool_no_cost_truncation ====================
# (2026-09-03 瘦身批自 test_cw_r411_pool_no_cost_truncation.py 并入;
# 两处按纪律修订:n4/n5 手抄常数 14/9 改注册表现算(纪律 9 推导锚定),
# 2000 次抽店按「断言成立的最小 n」降到 500(纪律 12;种子固定=确定性))

from sr_od.application.currency_war.data.cw_chars import CHARACTERS as _r411_CHARACTERS
from sr_od.application.currency_war.sim.pool import _Pool as _r411_Pool
from sr_od.application.currency_war.sim.checks.ledger import check_sim_pool_no_cost_truncation


def test_pool_contains_cost_4_and_5() -> None:
    """全费入池:copies 含 4 费与 5 费角色(无 max_cost 过滤)。

    期望集合从注册表现算(原锁手抄「n4>=14/n5>=9」,注册表扩角色
    即静默过期):每个 4/5 费在册角色都必须在池,缺失点名单独报。
    """
    p = _r411_Pool(random.Random(7))
    costs = {_r411_CHARACTERS[n].cost for n in p.copies}
    assert 4 in costs and 5 in costs
    for cost in (4, 5):
        expected = [n for n, c in _r411_CHARACTERS.items() if c.cost == cost]
        assert expected, f'注册表无 {cost} 费角色(锁口径失效,须重推)'
        missing = [n for n in expected if not p.copies.get(n)]
        assert not missing, f'{cost} 费角色未全入池(截断回归): {missing}'


def test_four_cost_appears_at_lv5() -> None:
    """lv5 起商店 4 费出现率 > 0(REFRESH_PROB .02;期望 ~50 命中/500 抽)。"""
    p = _r411_Pool(random.Random(11))
    hits = sum(1 for _ in range(500) for c in p.draw_shop(5)
               if c.cost == 4)
    assert hits > 0, 'lv5 未见 4 费(池截断或概率未接)'


def test_five_cost_appears_at_lv9() -> None:
    """lv9 商店 5 费出现率 > 0(P1 可达等级;REFRESH_PROB .10)。"""
    p = _r411_Pool(random.Random(13))
    hits = sum(1 for _ in range(500) for c in p.draw_shop(9)
               if c.cost == 5)
    assert hits > 0, 'lv9 未见 5 费(池截断或概率未接)'


def test_check_passes_on_real_pool() -> None:
    """检查项:真池(全费)0 违规。"""
    p = _r411_Pool(random.Random(1))
    rep = check_sim_pool_no_cost_truncation(p.copies)
    assert rep == {'violations': 0, 'missing_costs': []}


def test_check_fires_on_truncated_pool() -> None:
    """检查项双向:截断池(去门变异)必报缺失费用。"""
    p = _r411_Pool(random.Random(1))
    truncated = {n: c for n, c in p.copies.items()
                 if _r411_CHARACTERS[n].cost <= 3}   # 变异:重建 max_cost=3
    rep = check_sim_pool_no_cost_truncation(truncated)
    assert rep['violations'] == 2
    assert rep['missing_costs'] == [4, 5]
