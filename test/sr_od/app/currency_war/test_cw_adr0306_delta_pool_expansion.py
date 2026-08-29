"""ADR-0306(Δ池扩容批)锁 + ADR-0308(W31 节点胜率阶梯)迁移后状态。

裁决要点(ADR-0306 仍有效的部分):
- 胜判定唯一权威口径 = killed(结算屏 extras);Δ(相邻轮 hp 差分)
  是派生量。生成器口径下 killed 已知行异号实证 0/61;
- 各桶 n≥10 或 META bucket_poverty 显式披露贫困。

ADR-0308(W37)迁移:boss 回退胜率的 rung 外推机制(boss_win_p /
BOSS_WIN_P_* / _BOSS_WIN_P_EXTRAPOLATED 缓存)整体废弃,胜负面单一
取值口 = ``node_win_p``(W31 实测节点×轮次阶梯,n=192)。
"""

from sr_od.application.currency_war.sim import cw_sim
from sr_od.application.currency_war.data import cw_delta_pool_data
from sr_od.application.currency_war.data.cw_battle_tables import (
    NODE_WIN_P_BY_TYPE as tables_NODE_WIN_P_BY_TYPE,
    NODE_WIN_P_LADDER as tables_NODE_WIN_P_LADDER,
)
from sr_od.application.currency_war.kernel import cw_battle_calib as calib
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_delta_pool_bucket_coverage,
)


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


def test_snapshot_meta_corpus_accounting_and_poverty() -> None:
    """META 带语料行数账(增量盘点基准)+ 桶贫困显式披露。"""
    src_rows = cw_delta_pool_data.META.get('source_rows')
    assert isinstance(src_rows, dict)
    assert src_rows.get('outcomes.jsonl', 0) > 0
    assert src_rows.get('decisions.jsonl', 0) > 0
    poverty = cw_delta_pool_data.META.get('bucket_poverty')
    assert isinstance(poverty, list) and poverty
    # rung≥3 缺桶必须披露(语料不足如实报)
    assert 'battle:桶3(缺)' in poverty
    assert 'battle:桶4(缺)' in poverty


def test_boss_win_p_machinery_removed() -> None:
    """ADR-0308:rung 外推机制整体废弃——残留 = 死码回潮信号。"""
    for gone in ('boss_win_p', 'BOSS_WIN_P_BY_ENGINES',
                 'BOSS_WIN_P_EXTRAPOLATED_MIN_RUNG', 'BOSS_WIN_P_FALLBACK',
                 '_BOSS_WIN_P_EXTRAPOLATED'):
        assert gone not in cw_sim.__dict__, \
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
    pool_map, _, _ = cw_sim.resolve_pool('snapshot')
    rep = check_delta_pool_bucket_coverage(
        cw_sim.plane_view(pool_map), meta=cw_delta_pool_data.META)
    assert rep['violations'] == 0


def test_batch_report_embeds_coverage_check() -> None:
    """simulate_p1_batch 内嵌 delta_pool_bucket_coverage(ADR-0306 件5)。"""
    rep = cw_sim.simulate_p1_batch(3, pool='fallback', ledger=False,
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
