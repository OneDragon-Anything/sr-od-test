"""test_cw_delta_pool 主题锁(结构合并批,机械拼接;2026-09-09 二轮手术)。

成员(原文件 docstring 语义索引):
- b37_delta_pool_audit: test_cw_b37_delta_pool_audit.py
- adr0306_delta_pool_expansion: test_cw_adr0306_delta_pool_expansion.py
- battle_rung_delta_pool: test_cw_battle_rung_delta_pool.py
- delta_pool_snapshot: test_cw_delta_pool_snapshot.py
- adr0407_encounter_rung_pool: test_cw_adr0407_encounter_rung_pool.py
- w109_pool_pipeline: test_cw_w109_pool_pipeline.py
- pool_data_defense: 池再生数据防线(2026-09-08 事故批新增段,原并入未登记,本轮补录)
- adr0582_synthetic_supply_pairing_filter: 合成行/conf 门配对过滤(同上,补录)
- r409_delta_pool_starvation_guard: test_cw_r409_delta_pool_starvation_guard.py(2026-09-03 瘦身批并入)
- r411_pool_no_cost_truncation: test_cw_r411_pool_no_cost_truncation.py(2026-09-03 瘦身批并入;n4/n5 手抄常数改注册表现算,2000 次抽样按纪律 12 降到 500)

2026-09-09 二轮手术(判据 = sr-od-test/README.md 测试纪律 + 战役工作稿
METHODOLOGY;删除/合并明细 = .debug/temp/cw_test_slim_audit/reports/_cluster_R2A.md):
- 来源前缀别名(_<tag>_原名)统一为单一绑定并归顶——消除「同测混用两别名」
  隐患(机械拼接疤痕清单:METHODOLOGY §4.14);
- 子集/重复测试删除(采样器版本锁/快照指纹双锁/batch 指纹/battle_rung META 表)、
  同形测试并参化、三次 batch 嵌入检查并一次、三处结算接线源码锁并一。
"""
from __future__ import annotations

import inspect
import json
import random
from pathlib import Path

import pytest

from sr_od.application.currency_war.data import cw_delta_pool_data
from sr_od.application.currency_war.data.cw_battle_tables import (
    BUCKET_MIN_N,
    NODE_WIN_P_BY_TYPE,
    NODE_WIN_P_LADDER,
)
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_battle_calib as calib
from sr_od.application.currency_war.sim import (
    cw_delta_pool_gen,
    engine_p1,
    ledger_hooks,
    runner,
)
from sr_od.application.currency_war.sim import pool as sim_pool
from sr_od.application.currency_war.sim.checks.calib import check_ab_verdict_claim
from sr_od.application.currency_war.sim.checks.corpus import (
    check_boss_rung_corpus_sample_gate,
    check_delta_pool_poverty_selfconsistency,
    check_paired_prefork_wave_identity,
)
from sr_od.application.currency_war.sim.checks.ledger import (
    check_sim_pool_no_cost_truncation,
)
from sr_od.application.currency_war.sim.checks.pool import (
    BATTLE_RUNG_TRUTH,
    check_ab_depth_boundary_confound,
    check_battle_rung_pool_bucket_lock,
    check_delta_pool_bucket_coverage,
    check_delta_pool_bucket_min_n,
    check_depth_cliff_monotonicity,
)
from sr_od.application.currency_war.sim.pool import _Pool

# ==================== b37_delta_pool_audit ====================

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
    pm, _, _ = sim_pool.resolve_pool('snapshot')
    out = check_delta_pool_poverty_selfconsistency(
        sim_pool.plane_view(pm), cw_delta_pool_data.META)
    assert out['violations'] == 0, f'{out}'
    assert out['disclosed_n'] == out['pool_poor_n']


def test_poverty_selfconsistency_synthetic_green() -> None:
    out = check_delta_pool_poverty_selfconsistency(
        _mini_pool(), _mini_meta())
    assert out['violations'] == 0, f'{out}'


def test_poverty_selfconsistency_skip_states() -> None:
    """两跳过态:无披露载体(meta=None)/空池(fallback)→ 0 违规不辖。"""
    out = check_delta_pool_poverty_selfconsistency(_mini_pool(), None)
    assert out['violations'] == 0
    assert '不辖' in out['note']
    assert check_delta_pool_poverty_selfconsistency(
        {}, _mini_meta())['violations'] == 0


def _drifted_meta() -> dict:
    return {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                               'battle:桶4(缺)',
                               'boss:桶9(n=9)]']}   # 全角括号


def _undisclosed_meta() -> dict:
    return {'bucket_poverty': ['battle:桶2(n=9)', 'battle:桶3(缺)',
                               'battle:桶4(缺)']}   # 删 boss 披露行


def _stale_meta() -> dict:
    meta = _mini_meta()
    meta['bucket_poverty'] = list(meta['bucket_poverty']) + [
        'battle:桶0(n=9)']   # 池中不贫困的桶出现在披露
    return meta


def _n_mismatch_pool() -> dict:
    pool = _mini_pool()
    pool['battle'][2] = [-7] * 8   # 池 n=8 而披露 n=9
    return pool


@pytest.mark.parametrize(
    'pool_map,meta,marker',
    [(_mini_pool(), _drifted_meta(), '不可解析'),
     (_mini_pool(), _undisclosed_meta(), '未披露'),
     (_mini_pool(), _stale_meta(), '过期'),
     (_n_mismatch_pool(), _mini_meta(), 'n 值')],
    ids=('format_drift', 'undisclosed', 'stale', 'n_mismatch'))
def test_poverty_selfconsistency_drift_flags(
        pool_map: dict, meta: dict, marker: str) -> None:
    """变异杀四态(批㊲ 攻击面,2026-09-09 并参化):
    ①格式漂移(全角括号/空格)→ 解析失败违规——旧 coverage 字符串
    精确匹配下这是静默失配;②池贫困未披露 → 违规;③过期披露
    (披露池中不贫困桶)→ 违规;④披露 n 值与池不符 → 违规。"""
    out = check_delta_pool_poverty_selfconsistency(pool_map, meta)
    assert out['violations'] >= 1, f'{out}'
    assert any(marker in v for v in out['detail'])


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
    # 未观测组合 → 类型边际(期望值从注册表现算,禁手抄锚值)
    assert calib.node_win_p('battle', 6) == NODE_WIN_P_BY_TYPE['battle']
    assert calib.node_win_p('encounter', 6) == NODE_WIN_P_BY_TYPE['encounter']
    assert calib.node_win_p('boss', 8) == NODE_WIN_P_BY_TYPE['boss']
    for nt in ('reward', 'supply'):
        for rn in (1, 2, 5, 8):
            assert calib.node_win_p(nt, rn) == 1.0
    assert calib.node_win_p('unknown_node', 5) == 0.0


def test_node_win_p_values_all_valid_probabilities() -> None:
    """阶梯全体值 ∈ [0,1](胜率语义自洽)。"""
    for (_nt, _rn), v in NODE_WIN_P_LADDER.items():
        assert 0.0 <= v <= 1.0, (_nt, _rn, v)
    for nt, v in NODE_WIN_P_BY_TYPE.items():
        assert 0.0 <= v <= 1.0, (nt, v)


def test_snapshot_meta_win_stats_fields() -> None:
    """META battle_rung 逐桶带双口径胜率统计(权威=killed)。

    (原 test_snapshot_meta_carries_battle_rung_table 的主桶键存在性
    断言已并本测——同文件同事实择一,2026-09-09。)"""
    table = cw_delta_pool_data.META.get('battle_rung')
    assert isinstance(table, dict) and table
    assert {'0', '1'} <= set(table)
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
        assert gone not in engine_p1.__dict__, \
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
    pool_map, _, _ = sim_pool.resolve_pool('snapshot')
    rep = check_delta_pool_bucket_coverage(
        sim_pool.plane_view(pool_map), meta=cw_delta_pool_data.META)
    assert rep['violations'] == 0


# (原 test_batch_report_embeds_coverage_check 已并入 r409 段
#  test_batch_report_embeds_pool_level_checks——同一 batch 运行的嵌入
#  检查面,2026-09-09 三测并一(纪律 11:同次运行内重复昂贵计算)。)


# (原 test_boss_settle_uses_win_p_single_source 已并入
#  test_settle_wiring_and_single_source——同事实「node_win_p 单一取值口」
#  在两测各断一次,2026-09-09 择一。)





# ==================== battle_rung_delta_pool ====================

def test_snapshot_pool_rung_domain_truth_and_domains() -> None:
    """提交快照 rung 域/真值锚/encounter 迁键/boss 域四面对拍。

    独立性声明:本测对快照**内联现判**,不经 check_battle_rung_pool_
    bucket_lock(检查器自身真值表 = test_check_battle_rung_pool_
    bucket_lock_unit;若此处换调检查器,检查器回归时两测同时失明)。
    2026-09-09 四测并一测,断言面逐条保留:

    - battle 桶键全落 rung 域(0-4),双主桶 n≥10(批⑬ F1);
    - 双主桶均值符合真值表(真值锚=v13/ADR-0582 过滤后语料重推:
      r0 -9.73/r1 -3.24;漂移 ≤3hp。旧锚 -11.5/-6.3 是含毒语料——
      合成行入配对——的产物,治理随批重推,非机械跟绿);
    - v11/ADR-0407:encounter 桶键已迁 rung 且主桶达标(批⑬ F1
      「暂 depth 分桶」边界声明已被扩容+键查证解禁取代);
    - boss 池域不缩(重生成不丢失既有极值样本 min≤-36;批⑬ F7
      原始读数 -42 是决策帧口径,outcomes 差分口径不可达)。
    (ADR-0362:各面消费 plane=1 视图;P2 桶另辖。)
    """
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
    battle = m['battle']
    assert battle, 'battle 池缺失'
    assert all(int(b) <= 4 for b in battle), \
        f'battle 桶键落 depth 域: {sorted(battle)}'
    assert len(battle.get(0, [])) >= 10 and len(battle.get(1, [])) >= 10
    for rg, truth in BATTLE_RUNG_TRUTH.items():
        v = battle[rg]
        mean = sum(v) / len(v)
        assert abs(mean - truth) <= 3.0, \
            f'battle rung{rg} 均值 {mean:+.1f} 距真值 {truth:+.1f} 漂移>3hp'
    enc = m.get('encounter') or {}
    assert enc, 'encounter 池缺失'
    assert not sorted(b for b in enc if int(b) >= 6), \
        f'encounter 桶键落 depth 域: {sorted(enc)}'
    assert len(enc.get(0, [])) >= 10, 'encounter rung0 主桶饥饿'
    assert len(enc.get(1, [])) >= 10, 'encounter rung1 主桶饥饿'
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
    # 均值漂移>3hp → 报(r0 真值 -9.73;旧值 -11.5 系含毒语料锚,给 -5)
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


def test_settle_wiring_and_single_source() -> None:
    """结算接线与单一取值口源码锁(三测并一,2026-09-09;原
    test_settle_wiring_battle_rung_single_source / _v11_settle_wiring_
    encounter_rung_source / _boss_settle_uses_win_p_single_source)。

    锁的是**接线存在性**(纪律 8 容忍档,失守形态:v11 前「池已
    rung 化、采样仍喂 depth」的键错位——调用串漂移即红):
    - simulate_p1 battle/encounter 两类节点经 _settle_rung 取样
      (rung 定义单一源 = _engines_count);
    - boss_settle_delta 掷胜走 node_win_p 单一取值口(ADR-0308 起
      回退层胜负面换 W31 阶梯),不散落内联阶梯表、不持 rung 键。
    """
    src = inspect.getsource(engine_p1.simulate_p1)
    assert '_settle_rung' in src
    assert "live_delta_for('battle', _settle_rung(st)" in src
    assert "live_delta_for('encounter', _settle_rung(st)" in src
    boss_src = inspect.getsource(calib.boss_settle_delta)
    assert 'node_win_p' in boss_src   # ADR-0308 胜负面单一取值口
    assert 'NODE_WIN_P_LADDER[' not in boss_src   # 不散落内联阶梯表
    assert '_engines_count' not in boss_src   # boss 侧不再 rung 键


def test_batch_report_embeds_pool_level_checks() -> None:
    """simulate_p1_batch 内嵌池级检查族(fallback 空池各检查不辖=0)。

    (2026-09-09 三测并一:coverage/battle_rung_lock/min_n+cliff 各自
    曾各跑一次 batch——checks 默认开启,一次运行可同验四键,纪律 11。)
    """
    rep = runner.simulate_p1_batch(3, pool='fallback', ledger=False,
                                   checks=True)
    cv = rep['checks_violations']
    assert 'delta_pool_bucket_coverage' in cv
    assert 'battle_rung_pool_bucket_lock' in cv
    assert 'delta_pool_bucket_min_n' in cv
    assert 'depth_cliff_monotonicity' in cv
    for key in ('delta_pool_bucket_coverage', 'battle_rung_pool_bucket_lock',
                'delta_pool_bucket_min_n', 'depth_cliff_monotonicity'):
        assert cv[key]['violations'] == 0, (key, cv[key])


# (原 test_snapshot_meta_carries_battle_rung_table 已并入
#  test_snapshot_meta_win_stats_fields——{'0','1'} 主桶键 + n/mean 字段面
#  同文件同事实,2026-09-09 择一保留全字段版。)






# ==================== delta_pool_snapshot ====================

def test_resolve_pool_snapshot_and_fallback() -> None:
    """snapshot 命中提交快照(归一 int 桶键);fallback 显式空池+打标。

    (原 test_snapshot_module_loads_and_fingerprint_selfconsistent 的
    「指纹重算 == META」与 unlabeled_dropped 披露键两面已并本测——
    resolve_pool('snapshot') 内部即做指纹失配校验,同事实双锁,
    2026-09-09 择一。)
    """
    m, fp, src = sim_pool.resolve_pool('snapshot')
    assert src == 'snapshot'
    assert fp == cw_delta_pool_data.META['fingerprint']
    # 可信标签口径:丢弃计数已披露(2026-08-22 retrofix 后死链
    # 历史标签置 None,不入池)
    assert 'unlabeled_dropped' in cw_delta_pool_data.META
    # 归一化后语义等价(int 桶键;json round-trip 的 str 键会让
    # live_delta_for 的 int 查询全 miss = 快照静默失效)
    # ADR-0362:位面层同样归一 int 键
    assert m == sim_pool._normalize_pool(cw_delta_pool_data.SNAPSHOT)
    assert all(isinstance(b, int)
               for planes in m.values() for b in planes)
    assert all(isinstance(b, int)
               for planes in m.values()
               for buckets in planes.values() for b in buckets)
    assert m.get('battle')

    m2, fp2, src2 = sim_pool.resolve_pool('fallback')
    assert src2 == 'fallback'
    assert m2 == {}
    assert fp2 == sim_pool.pool_fingerprint({})


def test_resolve_pool_auto_missing_raises_loudly(tmp_path: None | Path) -> None:
    """auto 缺源 raise(不静默回退空池)——blocker 修复的核心语义。"""
    with pytest.raises(sim_pool.DeltaPoolUnavailable):
        sim_pool.resolve_pool('auto', auto_dir=tmp_path / 'nonexistent')


def test_resolve_pool_path_json_snapshot(tmp_path: Path) -> None:
    """Path 模式:JSON 快照文件(生成器 --export-json 产物;
    ADR-0362 起形状 {节点:{位面:{桶:[Δ]}}})。"""
    p = tmp_path / 'snap.json'
    p.write_text(json.dumps(
        {'meta': {}, 'snapshot': {'battle': {1: {6: [-4]}}}},
        ensure_ascii=False), encoding='utf-8')
    m, fp, src = sim_pool.resolve_pool(p)
    assert src == f'path:{p.name}'
    assert m == {'battle': {1: {6: [-4]}}}
    assert fp == sim_pool.pool_fingerprint({'battle': {1: {6: [-4]}}})


def test_simulate_p1_records_pool_identity() -> None:
    """SimResult 带池指纹+来源(跨日基线对照须核指纹一致)。

    供给重校准起指纹含装备发放结构版本位(``+eqgN``)——发放结构是
    行为语义的一部分,新旧结构不可比,跨版本对照必须显式失败。
    """
    r = engine_p1.simulate_p1(42, pool='fallback')
    assert r.pool_source == 'fallback'
    assert r.pool_fingerprint == (
        sim_pool.pool_fingerprint({})
        + f'+eqg{engine_p1.EQUIP_GRANT_CALIB_VERSION}')
    r2 = engine_p1.simulate_p1(42, pool='snapshot')
    assert r2.pool_source == 'snapshot'
    assert r2.pool_fingerprint == (
        cw_delta_pool_data.META['fingerprint']
        + f'+eqg{engine_p1.EQUIP_GRANT_CALIB_VERSION}')


# (原 test_batch_report_carries_pool_fingerprint 已删(2026-09-09):
#  batch 报告指纹管线单路(runner.simulate_p1_batch 直取 results[0]),
#  batch 级指纹面由 test_cw_infra_locks.py::test_ci_smoke_snapshot_batch
#  以 snapshot 批承载,fallback 池身份面由本文件
#  test_simulate_p1_records_pool_identity 局级双源承载——组合即覆盖,
#  本测 10 局 batch 为纯重复运行成本。)


def test_snapshot_pool_is_live_in_sim() -> None:
    """金丝雀:快照池采样真实命中(防 str 桶键/归一化缺失类静默失效)。

    曾发:json round-trip 把桶键变 '9'(str),live_delta_for 用
    int 查询全 miss → snapshot 模式静默退旧模型而所有结构测试
    仍绿。本锁遍历快照桶,断言至少一次真实采样命中。
    """
    import random

    m, _, _ = sim_pool.resolve_pool('snapshot')
    hit = False
    # ADR-0362:桶在 plane=1 层下
    for node in ('battle', 'boss', 'encounter'):
        for bucket in (m.get(node, {}).get(1) or {}):
            v = sim_pool.live_delta_for(node, bucket, random.Random(1),
                                    pool_map=m)
            if v is not None:
                hit = True
                break
        if hit:
            break
    assert hit, '快照全桶采样 miss = 池静默失效(查 _normalize_pool)'


def test_generator_data_file_discipline() -> None:
    """生成器纪律:数据文件头部带勿手编标记 + 重生成命令。"""
    head = Path(cw_delta_pool_data.__file__).read_text(
        encoding='utf-8')[:600]
    assert '勿手编' in head
    assert 'gen_delta_pool_snapshot.py' in head





# ==================== adr0407_encounter_rung_pool ====================

def _p1_means() -> dict[int, float]:
    m, _, _ = sim_pool.resolve_pool('snapshot')
    m = sim_pool.plane_view(m)
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


# (原 test_v11_settle_wiring_encounter_rung_source 已并入
#  test_settle_wiring_and_single_source——encounter 调用串断言面在彼,
#  2026-09-09 三处接线锁并一。)




# ==================== w109_pool_pipeline ====================


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
        monkeypatch: pytest.MonkeyPatch) -> None:
    """局终钩子 best-effort:再生抛异常不外传(局终收尾不被打断)。"""
    def _boom(**kwargs):
        raise RuntimeError('sim_runs 回灌守卫误触发(构造)')

    monkeypatch.setattr(cw_delta_pool_gen, 'regenerate_snapshot', _boom)
    # 不抛即过(返回 None;warning 已由 log 记)
    assert ledger_hooks._regenerate_delta_pool_after_run() is None


# ==================== pool_data_defense(池数据防线)====================
# 生成器两道数据防线(2026-09-08 事故实证):①run 级隔离——前缀规则
# (fake_/sim_,类别级)+ 显式名单(个例级)统一判据,拦「进错目录的
# run」(假游戏局 fake_20260908 混进 live 生产流,目录守卫对 run 粒度
# 失明);②塌缩守卫——源行数账较现快照行数账 < 50% 拒绝再生覆写、
# 保留现快照(微型语料当日三次静默覆盖全量快照;对账正本 =
# ADR-0595 与编排者台账 T-126 note, 2026-09-08)。出处:生成器隔离机制块头与
# SNAPSHOT_COLLAPSE_MIN_RATIO 常量注(持久语义锚)。防线自检三态:
# 假语料源 → 拒绝;正常增量 → 放行;塌缩源 → 拒绝。
# fixture 全部 tmp_path 合成语料 + 写目标指 tmp(测试纪律 2/19:
# 零真实副作用、不碰生产快照)。


def _defense_delta_row(run_id: str, hp_from: float,
                       hp_to: float) -> tuple[dict, dict, dict]:
    """单差分 run 的最小行组:1 decisions 行 + 2 outcomes 行(奖励腿)。

    形态照搬本文件既有合成语料先例(test_regenerate_frozen_by_default:
    Σboard join 物料须覆盖配对后继键,否则 dep None 静默跳对——锁会
    假绿);各 run 的 hp 值错开,凭值即可证明「谁在池里、谁被隔离」。
    """
    dec = {'run_id': run_id, 'plane': 1, 'round_num': 2,
           'state': {'board': {'散': 4}, 'deployed': []}}
    out1 = {'run_id': run_id, 'plane': 1, 'round_num': 1,
            'node_type': '奖励', 'hp_after': hp_from,
            'hp_confidence': 1.0, 'board_before': {}}
    out2 = {'run_id': run_id, 'plane': 1, 'round_num': 2,
            'node_type': '奖励', 'hp_after': hp_to,
            'hp_confidence': 1.0, 'board_before': {'散': 1}}
    return dec, out1, out2


def _defense_write_corpus(src: Path,
                          row_groups: list[tuple[dict, dict, dict]]) -> None:
    """把行组落成 replay 目录(decisions/outcomes 各一份 jsonl,整写)。"""
    src.mkdir(parents=True, exist_ok=True)
    (src / 'decisions.jsonl').write_text(
        '\n'.join(json.dumps(d, ensure_ascii=False)
                  for d, _, _ in row_groups) + '\n', encoding='utf-8')
    (src / 'outcomes.jsonl').write_text(
        '\n'.join(json.dumps(o, ensure_ascii=False)
                  for _, o1, o2 in row_groups for o in (o1, o2)) + '\n',
        encoding='utf-8')


def test_quarantine_reason_single_source() -> None:
    """隔离判据单一源(防线①):前缀规则(类别级)与显式名单(个例级)
    都只经 _run_quarantine_reason 出;正常生产 run 与空值放行。

    事故局显式名单保留语义 = 机制化并入(2026-08-22 双进程写竞争
    两局行为不变:仍隔离),不是删名单。
    """
    q = cw_delta_pool_gen._run_quarantine_reason
    assert q('fake_20260908') is not None \
        and '假游戏' in (q('fake_20260908') or '')
    sim_id = 'sim_20260908_120001_n3_s0_aabbccdd_s7'
    assert q(sim_id) is not None and 'sim 批' in (q(sim_id) or '')
    assert q('run_20260822_185613') is not None   # 历史事故局并入机制
    assert q('run_20260822_191028') is not None
    assert q('run_20260907_214130') is None       # 正常生产 run 放行
    assert q(None) is None and q('') is None


def test_fake_and_sim_runs_isolated_from_snapshot(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """防线① 行为锁(混入形态):fake_/sim_ run 混在语料里时物理
    不入池,正常 run 照常入池,quarantined_hits 如实披露。

    若此锁红:隔离判据被绕开或收窄——假游戏/sim 批行会随下次再生
    流回提交快照(只「作废信任」不排池的旧病,QUARANTINED_RUNS
    机制注释所述)。禁为保绿收窄断言。
    """
    real_id = 'run_20260908_074522'
    groups = [
        _defense_delta_row('fake_20260908', 84, 47),   # 实证同款假游戏前缀
        _defense_delta_row(
            'sim_20260908_120001_n1_s0_aabbccdd_s1', 90, 37),
        _defense_delta_row(real_id, 100, 88),          # Δ=-12 唯一入池值
    ]
    src = tmp_path / 'replay'
    _defense_write_corpus(src, groups)
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    fp = cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    ns: dict = {}
    exec(target.read_text(encoding='utf-8'), ns)
    snap, meta = ns['SNAPSHOT'], ns['META']
    vals = [x for planes in snap.values() for bks in planes.values()
            for v in bks.values() for x in v]
    assert vals == [-12], vals          # -37/-53(假/sim 腿)不得出现
    assert set(meta['quarantined_hits']) == {
        'fake_20260908', 'sim_20260908_120001_n1_s0_aabbccdd_s1'}
    assert real_id in meta['runs'] and meta['fingerprint'] == fp


def test_fake_only_source_rejected_target_untouched(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """防线自检·拒绝态①:语料源只有 fake_ run → 隔离后无样本可配对,
    再生拒绝(池为空)且写目标零落盘——「拒绝」= 不产任何新快照,
    不是写了坏数据再报警。"""
    src = tmp_path / 'replay'
    _defense_write_corpus(
        src, [_defense_delta_row('fake_20260908', 84, 47)])
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    with pytest.raises(RuntimeError, match='池为空'):
        cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    assert not target.exists()


def test_normal_incremental_regeneration_passes(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """防线自检·放行态:正常 live 源增量(append-only,行数账只升)
    再生照常覆写——塌缩守卫只拦「缩」,不拦「长」。"""
    src = tmp_path / 'replay'
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    groups = [_defense_delta_row(f'run_20260908_{i:04d}', 100 - i, 88 - i)
              for i in range(4)]
    _defense_write_corpus(src, groups)
    cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    ns1: dict = {}
    exec(target.read_text(encoding='utf-8'), ns1)
    assert sum(ns1['META']['source_rows'].values()) == 12  # 4 run×(1+2)行
    groups += [_defense_delta_row(f'run_20260909_{i:04d}', 100 - i, 90 - i)
               for i in range(4)]
    _defense_write_corpus(src, groups)                     # 行数账翻倍
    fp2 = cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    ns2: dict = {}
    exec(target.read_text(encoding='utf-8'), ns2)
    assert sum(ns2['META']['source_rows'].values()) == 24
    assert ns2['META']['fingerprint'] == fp2


def test_collapsed_source_rejected_snapshot_preserved(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """防线自检·拒绝态②(塌缩守卫):源行数账 < 现快照行数账 × 50% →
    SourceCorpusCollapse,且「将被覆写的文件」字节原样保留——保留
    现快照是本防线的行为本体,不是副作用;异常文案自含两侧行数账
    (申报差异,局终钩子的 best-effort 警告即告警通道)。"""
    src = tmp_path / 'replay'
    target = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', target)
    groups = [_defense_delta_row(f'run_20260907_{i:04d}', 100 - i, 88 - i)
              for i in range(4)]
    _defense_write_corpus(src, groups)
    cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)  # 建基线
    before = target.read_text(encoding='utf-8')
    _defense_write_corpus(src, groups[:1])   # 塌缩:3/12 行 = 25% < 50%
    with pytest.raises(
            cw_delta_pool_gen.SourceCorpusCollapse, match='塌缩') as ei:
        cw_delta_pool_gen.regenerate_snapshot(src_dir=src, quiet=True)
    msg = str(ei.value)
    assert '保留现快照' in msg
    assert '12' in msg and '3' in msg       # 两侧行数账进文案(申报差异)
    assert target.read_text(encoding='utf-8') == before   # 零覆写


def test_collapse_baseline_reads_committed_head_not_disk(
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """塌缩守卫基线来源锁(2026-09-09 穿透定谳,ADR-0612):基线必须
    取 git HEAD 提交版,不是盘面文件——盘面被一次未提交的塌缩再生
    改写后,以盘面为基线的守卫对提交真值失明,微语料 vs 微语料永
    过闸,塌缩自我延续(2026-09-08 三次静默覆写后,286/48 微语料
    再生在守卫在场下持续放行,工作树伪影即实证)。

    构造(不依赖真实 git 态):盘面基线=已塌缩快照(行数账 6),
    HEAD 版=全量(行数账 24,经 _head_data_py_text 桩注入);微源
    6 行 ≥ 盘面基线×50%(旧实现放行=穿透)但 < HEAD 基线×50% →
    必须 SourceCorpusCollapse 且盘面字节原样保留。若此锁红:基线
    来源退回盘面 = 塌缩自我延续复发,禁为保绿收窄。
    """
    head_src = tmp_path / 'head_corpus'
    disk_src = tmp_path / 'disk_corpus'
    head_groups = [_defense_delta_row(f'run_20260901_{i:04d}', 100 - i, 88 - i)
                   for i in range(8)]          # 8 run × 3 行 = 24 行(全量)
    disk_groups = head_groups[:2]              # 2 run × 3 行 = 6 行(塌缩)
    _defense_write_corpus(head_src, head_groups)
    _defense_write_corpus(disk_src, disk_groups)
    head_file = tmp_path / 'head_version_data.py'
    disk_file = tmp_path / 'cw_delta_pool_data.py'
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', head_file)
    cw_delta_pool_gen.regenerate_snapshot(src_dir=head_src, quiet=True)
    head_text = head_file.read_text(encoding='utf-8')
    monkeypatch.setattr(cw_delta_pool_gen, 'DATA_PY', disk_file)
    cw_delta_pool_gen.regenerate_snapshot(src_dir=disk_src, quiet=True)
    disk_text = disk_file.read_text(encoding='utf-8')

    # 桩点 = 模块单函数(生产真实路径 = git show HEAD;仓外写目标
    # 自动走盘面兜底,既有 tmp 锁不受影响)。
    monkeypatch.setattr(cw_delta_pool_gen, '_head_data_py_text',
                        lambda _p: head_text)
    with pytest.raises(
            cw_delta_pool_gen.SourceCorpusCollapse, match='塌缩') as ei:
        cw_delta_pool_gen.regenerate_snapshot(src_dir=disk_src, quiet=True)
    msg = str(ei.value)
    assert '24' in msg and '6' in msg       # HEAD 基线 24 vs 微源 6 进文案
    assert disk_file.read_text(encoding='utf-8') == disk_text   # 盘面零覆写


def test_auto_pool_quarantine_same_judgment(tmp_path: Path) -> None:
    """auto 池同判据锁(ADR-0595 适用范围含 auto 池):_pool_from_replay
    消费同一 _run_quarantine_reason——fake_/sim_ run 不入缺省校准池,
    正常 run_ 照常入池(防过滤扩大化),quarantined_hits 同名披露。

    若此锁红:auto 池隔离被拆除——resolve_pool('auto') 是
    simulate_p1 的缺省池,假局行会持续被配对进缺省校准路径
    (ADR-0582 方案审阻断-1 同型反模式「默认路径继续吃毒」,
    ADR-0595 适用范围在案),禁为保绿拆除。"""
    real_id = 'run_20260908_074522'
    groups = [
        _defense_delta_row('fake_20260908', 84, 47),
        _defense_delta_row('sim_20260908_120001_n1_s0_aabbccdd_s1', 90, 37),
        _defense_delta_row(real_id, 100, 88),          # Δ=-12 唯一入池值
    ]
    d = tmp_path / 'replay'
    _defense_write_corpus(d, groups)
    pool, meta = sim_pool._pool_from_replay(d)
    vals = [x for planes in pool.values() for bks in planes.values()
            for v in bks.values() for x in v]
    assert vals == [-12], vals          # -37/-53(假/sim 腿)不得出现
    assert set(meta['quarantined_hits']) == {
        'fake_20260908', 'sim_20260908_120001_n1_s0_aabbccdd_s1'}
    assert real_id in meta['runs']


def test_auto_pool_normal_run_source_taken(tmp_path: Path) -> None:
    """auto 池放行锁:纯正常 run_ 源在 _pool_from_replay
    照常配对入池——隔离只辖 fake_/sim_ 前缀与显式名单,禁扩大化
    误伤生产局(run_ 前缀是生产局唯一历史形态,注册表核实)。"""
    groups = [_defense_delta_row('run_20260908_074522', 100, 88)]
    d = tmp_path / 'replay'
    _defense_write_corpus(d, groups)
    pool, meta = sim_pool._pool_from_replay(d)
    vals = [x for planes in pool.values() for bks in planes.values()
            for v in bks.values() for x in v]
    assert vals == [-12], vals
    assert meta['quarantined_hits'] == []


# ==================== r409_delta_pool_starvation_guard ====================
# (2026-09-03 瘦身批自 test_cw_r409_delta_pool_starvation_guard.py 原文并入;
# 2026-09-09 二轮:sim_pool/runner/random/检查器 import 已归顶统一绑定)

def test_guard_hungry_bucket_not_deterministic_cliff() -> None:
    """守卫触发:n<BUCKET_MIN_N 桶不裸采样——饥饿桶唯一样本不再恒定命中。

    本合成池形态:饥饿桶 n=1 与深邻桶 n=6 合并(共 7 样本),饥饿
    样本 -11 以 1/7 权重参与(合并非剔除);旧语义下饥饿桶采样
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
    """检查项 1:饥饿桶审计(批③ 形态:battle 桶6 n=1)。

    阈值单一源锁(原 test_sampler_version_bumped_and_snapshot_guarded
    的 BUCKET_MIN_N==5 断言并此,2026-09-09):n=5 不报/n=2 报钉住
    行为面,此处钉常数面——改桶宽阈值时两处同红,登记新阈值。
    """
    pool = {'battle': {6: [-11], 9: [-4] * 6},
            'encounter': {9: [-13, 2]}}
    rep = check_delta_pool_bucket_min_n(pool)
    assert rep['violations'] == 2
    assert 'battle:桶6(n=1)' in rep['buckets']
    assert 'encounter:桶9(n=2)' in rep['buckets']
    # 全健康池 / 空池(fallback)零违规
    assert check_delta_pool_bucket_min_n(
        {'battle': {6: [-1] * BUCKET_MIN_N}})['violations'] == 0
    assert check_delta_pool_bucket_min_n({})['violations'] == 0
    # 阈值常数面(单一源 = data/cw_battle_tables;期 0b 锁改判 N7)
    assert BUCKET_MIN_N == 5


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


# (原 test_batch_report_embeds_pool_checks 已并入
#  test_batch_report_embeds_pool_level_checks,2026-09-09 三测并一。)


# (原 test_sampler_version_bumped_and_snapshot_guarded 已删(2026-09-09,
#  跨文件子集):_SAMPLER_VERSION==11 / src=='snapshot' / fp==META 指纹
#  三面与 test_cw_reward_pool_sampling.py::
#  test_sampler_v4_and_snapshot_selfconsistent(超集:另钉 META sampler_
#  version + 旧指纹墓碑)同事实双锁,择一保留超集;其独有 BUCKET_MIN_N==5
#  面迁入 test_check_delta_pool_bucket_min_n。版本史语义见生产
#  sim/pool.py _SAMPLER_VERSION 常量注,无信息丢失。)


# ==================== r411_pool_no_cost_truncation ====================
# (2026-09-03 瘦身批自 test_cw_r411_pool_no_cost_truncation.py 并入;
# 两处按纪律修订:n4/n5 手抄常数 14/9 改注册表现算(纪律 9 推导锚定),
# 2000 次抽店按「断言成立的最小 n」降到 500(纪律 12;种子固定=确定性))

def test_pool_contains_cost_4_and_5() -> None:
    """全费入池:copies 含 4 费与 5 费角色(无 max_cost 过滤)。

    期望集合从注册表现算(原锁手抄「n4>=14/n5>=9」,注册表扩角色
    即静默过期):每个 4/5 费在册角色都必须在池,缺失点名单独报。
    """
    p = _Pool(random.Random(7))
    costs = {CHARACTERS[n].cost for n in p.copies}
    assert 4 in costs and 5 in costs
    for cost in (4, 5):
        expected = [n for n, c in CHARACTERS.items() if c.cost == cost]
        assert expected, f'注册表无 {cost} 费角色(锁口径失效,须重推)'
        missing = [n for n in expected if not p.copies.get(n)]
        assert not missing, f'{cost} 费角色未全入池(截断回归): {missing}'


@pytest.mark.parametrize('level,cost', [(5, 4), (9, 5)],
                         ids=('lv5_cost4', 'lv9_cost5'))
def test_high_cost_appears_in_shop(level: int, cost: int) -> None:
    """高档费用在可达等级的商店出现率 > 0(2026-09-09 两测并参化)。

    lv5 4 费 REFRESH_PROB .02(期望 ~50 命中/500 抽);lv9 5 费 .10
    (P1 可达等级)。红 = 池截断回归或概率未接。
    """
    p = _Pool(random.Random(11 if cost == 4 else 13))
    hits = sum(1 for _ in range(500) for c in p.draw_shop(level)
               if c.cost == cost)
    assert hits > 0, f'lv{level} 未见 {cost} 费(池截断或概率未接)'


def test_no_cost_truncation_check_two_state() -> None:
    """检查项两态(2026-09-09 两测并一):真池(全费)0 违规;
    截断池(去门变异,重建 max_cost=3)必报缺失费用 [4, 5]。"""
    p = _Pool(random.Random(1))
    assert check_sim_pool_no_cost_truncation(p.copies) == \
        {'violations': 0, 'missing_costs': []}
    truncated = {n: c for n, c in p.copies.items()
                 if CHARACTERS[n].cost <= 3}
    rep = check_sim_pool_no_cost_truncation(truncated)
    assert rep['violations'] == 2
    assert rep['missing_costs'] == [4, 5]


# ==================== adr0582_synthetic_supply_pairing_filter ====================
# Δ池生成器治理(ADR-0582):合成行(source='synthetic_supply',hp 为
# last_state 战前快照)与低可信行(hp_confidence<0.9)不作 hp 差分
# 端点——移行桥接重配对。锁形态依据方案审前置清单 4:fixture 注入
# 锁为主(镜像律是配对过程性质,池条目不含配对信息,快照层不可
# 检验;判例 = test_pool_build_never_mixes_runs)、快照级**缺席型**
# 断言为辅(禁快照值锁——池随局终自动再生,值锁=change-detector,
# ADR-0292 判例 test_cw_reward_pool_sampling.py 注)。


def _adr0582_replay(tmp_path: Path,
                    outcomes: list[dict]) -> Path:
    """最小 replay 目录:decisions 行按 outcomes 的 (run,plane,round)
    全集合生成(Σboard join 物料必须覆盖每个配对后继键,否则
    dep None 静默跳对——锁会假绿);outcomes 行原样落盘。"""
    d = tmp_path / 'replay'
    d.mkdir()
    keys = sorted({(o.get('run_id') or 'r1', o.get('plane') or 1,
                    o.get('round_num') or 0) for o in outcomes})
    dec = [json.dumps(
        {'run_id': run, 'plane': plane, 'round_num': rn,
         'state': {'board': {'散': 6}, 'deployed': []}},
        ensure_ascii=False) for run, plane, rn in keys]
    (d / 'decisions.jsonl').write_text(
        '\n'.join(dec) + '\n', encoding='utf-8')
    (d / 'outcomes.jsonl').write_text(
        '\n'.join(json.dumps(o, ensure_ascii=False)
                  for o in outcomes) + '\n', encoding='utf-8')
    return d


def test_pool_build_synthetic_row_never_endpoint(tmp_path: Path
                                                 ) -> None:
    """镜像律消失锁(毒形态 fixture,ADR-0582):合成行不入配对端点。

    形态 = g_20260907_025608 p1 实案(ADR-0577 §3.3 旁证):r4 战斗
    44 → 合成补给行 66(战前快照鬼值)→ r6 战斗 46。含毒口径产出
    幻影配对 +22(supply)并顶替真实 +2 为 −20(battle)——镜像律
    「supply 增益=上一轮战败取反」的直接来源;过滤后 supply 域无
    此对、battle 桥接恢复真实 +2。双消费面(快照生成器/auto 池)
    同断言——共享配对件的两侧接线都要在。
    """
    outcomes = [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1,
         'node_type': '普通战斗', 'hp_after': 44, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2,
         'node_type': '补给', 'hp_after': 66, 'hp_confidence': 0.0,
         'source': 'synthetic_supply', 'board_before': {}},
        {'run_id': 'r1', 'plane': 1, 'round_num': 3,
         'node_type': '普通战斗', 'hp_after': 46, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},
    ]
    d = _adr0582_replay(tmp_path, outcomes)
    pool_auto, meta_auto = sim_pool._pool_from_replay(d)
    pool_gen, meta_gen = cw_delta_pool_gen.build_pool(d, None)
    for p_map, m_map in ((pool_auto, meta_auto), (pool_gen, meta_gen)):
        # 合成行不入端点:supply 域整体缺席(+22 幻影不存在)
        assert 'supply' not in p_map, p_map.get('supply')
        # 桥接重配对:跨合成行的真实战斗差分 46−44=+2 恢复
        # (断链实现会丢真实对、留 −20 型错值——两形态都不在)
        assert p_map.get('battle') == {1: {0: [2]}}, p_map.get('battle')
        all_vals = [x for planes in p_map.values()
                    for bks in planes.values()
                    for v in bks.values() for x in v]
        assert -20 not in all_vals and 22 not in all_vals
        # 剔除计数如实披露(不静默)
        assert m_map['synthetic_supply_dropped'] == 1
        assert m_map['hp_conf_dropped'] == 0
    # auto/snapshot 指纹收敛判据(pool.py 无标签行案先例):同一语料
    # 两消费面必须同池——单侧过滤即破坏指纹相等性用途。
    assert pool_auto == pool_gen
    assert sim_pool.pool_fingerprint(pool_auto) \
        == sim_pool.pool_fingerprint(pool_gen)


def test_pool_build_conf_gate_drops_untrusted_with_bridge(
        tmp_path: Path) -> None:
    """conf 门剔除计数锁(ADR-0582):低可信行不作端点+移行桥接。

    两个真实毒形态一起钉:①非终局低可信行(语料实测 0 条,机制
    形态锁)——剔除后邻行桥接,真实量级 −13 不被伪值顶替;②终局
    loss_page hp=0 死亡腿(本语料 101 条,conf 门剔除主体)——
    hp=0 终局行保留至资格过滤(v12 hp0 瞬态只剔非终局),被 conf
    门剔出、不再产出任何配对(伪掉血对消失,也不会被节点兜底
    误标成假『补给』样本)。
    """
    outcomes = [
        # r1:84 →(低可信 50,conf 0.3,剔除+桥接)→ 71 = −13
        {'run_id': 'r1', 'plane': 1, 'round_num': 1,
         'node_type': '普通战斗', 'hp_after': 84, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2,
         'node_type': '遭遇', 'hp_after': 50, 'hp_confidence': 0.3,
         'board_before': {'散': 1}},
        {'run_id': 'r1', 'plane': 1, 'round_num': 3,
         'node_type': '普通战斗', 'hp_after': 71, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},
        # r2:100 →(终局 loss_page hp=0 conf 0.0,死亡腿,零配对)
        {'run_id': 'r2', 'plane': 1, 'round_num': 1,
         'node_type': '普通战斗', 'hp_after': 100, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},
        {'run_id': 'r2', 'plane': 1, 'round_num': 2,
         'node_type': '遭遇', 'hp_after': 0, 'hp_confidence': 0.0,
         'source': 'loss_page', 'board_before': {'散': 1}},
    ]
    d = _adr0582_replay(tmp_path, outcomes)
    pool, meta = sim_pool._pool_from_replay(d)
    # 桥接恢复真实差分;低可信中间行的『遭遇』标签不入桶
    assert pool.get('battle') == {1: {0: [-13]}}, pool.get('battle')
    assert 'encounter' not in pool
    all_vals = [x for planes in pool.values() for bks in planes.values()
                for v in bks.values() for x in v]
    assert 50 not in all_vals and 0 not in all_vals and -34 not in all_vals \
        and 21 not in all_vals and -100 not in all_vals
    # 经伪值中转的错差分(84→50=−34 / 50→71=+21 / 100→0=−100)都不在
    assert meta['hp_conf_dropped'] == 2   # 低可信中间行 + 终局死亡腿
    assert meta['synthetic_supply_dropped'] == 0
    assert meta['hp0_transient_dropped'] == 0   # 终局 hp0 不归 v12 瞬态


def test_pool_build_keeps_real_settlement_rows(tmp_path: Path
                                               ) -> None:
    """真实样本保留锁(ADR-0582 误杀防线):source 三形态(''/缺键/
    recovered,结算屏当时读取)全部照常入池——过滤只针对合成行族
    (telemetry.recorder 枚举精确匹配),禁「扩大化到非合成来源」。

    若此锁红:过滤谓词被改宽(如按 source 在场性误杀历史无键行
    239 条,或 recovered 残留结算屏行)——先重推 ADR-0582 谓词
    边界再动,禁机械跟绿。
    """
    outcomes = [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1,
         'node_type': '奖励', 'hp_after': 100, 'hp_confidence': 1.0,
         'source': '', 'board_before': {}},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2,
         'node_type': '普通战斗', 'hp_after': 90, 'hp_confidence': 1.0,
         'board_before': {'散': 1}},   # 无 source 键(历史行形态)
        {'run_id': 'r1', 'plane': 1, 'round_num': 3,
         'node_type': '遭遇', 'hp_after': 60, 'hp_confidence': 1.0,
         'source': 'recovered', 'board_before': {'散': 1}},
    ]
    d = _adr0582_replay(tmp_path, outcomes)
    pool, meta = sim_pool._pool_from_replay(d)
    assert pool.get('battle') == {1: {0: [-10]}}
    assert pool.get('encounter') == {1: {0: [-30]}}
    assert meta['synthetic_supply_dropped'] == 0
    assert meta['hp_conf_dropped'] == 0


def test_snapshot_supply_domain_free_of_large_artifacts() -> None:
    """快照级缺席断言(ADR-0582 唯一允许的快照层形态):supply 域
    不含 |Δ|>20 样本——合成行镜像律(+22/+47 型)与跨 run 大跳变
    一旦在再生后涌现即红。缺席型≠值锁:不断言 n/均值(池随实机
    局终自动再生,值锁=池耦合 change-detector,ADR-0292 判例)。
    """
    pm, _, _ = sim_pool.resolve_pool('snapshot')
    for plane in (1, 2):
        vals = [d for v in ((pm.get('supply') or {}).get(plane) or {}).values()
                for d in v]
        offenders = [d for d in vals if abs(d) > 20]
        assert not offenders, f'supply P{plane} 含 |Δ|>20 样本: {offenders}'
