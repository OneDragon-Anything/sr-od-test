"""ADR-0306(Δ池扩容批)锁:胜判定权威口径 + rung≥3 胜率外推 +
桶覆盖披露检查(delta_pool_bucket_coverage)+ 快照 META 扩展字段。

裁决要点(详 ADR-0306):
- 胜判定唯一权威口径 = killed(结算屏 extras);Δ(相邻轮 hp 差分)
  是派生量。生成器口径下 killed 已知行异号实证 0/61——0305 的
  「3/9 异号」系 tier×core 与 rung 两种分桶错位对照的伪影;
- rung≥3 无桶(语料不足,如实披露)→ boss 胜分支降级路径的胜率
  由拍脑袋 0.25 改为「rung2 桶实测」外推(快照 META 单一源);
- 各桶 n≥10 或 META bucket_poverty 显式披露贫困。
"""

import pytest

from sr_od.application.currency_war import cw_delta_pool_data, cw_sim
from sr_od.application.currency_war.cw_sim_checks import (
    check_delta_pool_bucket_coverage,
)


def _clear_extrap_cache() -> None:
    cw_sim.__dict__.pop('_BOSS_WIN_P_EXTRAPOLATED', None)


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


def test_boss_win_p_rung3_extrapolated_from_rung2() -> None:
    """rung≥3 胜率 = rung2 桶实测(快照 META win_killed)外推;
    rung0/1/2 仍用批③ H3 实测矩阵。"""
    _clear_extrap_cache()
    expect = cw_delta_pool_data.META['battle_rung']['2']['win_killed']
    assert expect is not None
    assert cw_sim.boss_win_p(3) == pytest.approx(expect)
    assert cw_sim.boss_win_p(4) == pytest.approx(expect)
    assert cw_sim.boss_win_p(99) == pytest.approx(expect)
    assert cw_sim.boss_win_p(0) == 0.0
    assert cw_sim.boss_win_p(1) == 0.0
    assert cw_sim.boss_win_p(2) == cw_sim.BOSS_WIN_P_BY_ENGINES[2]


def test_boss_win_p_fallback_without_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    """快照 META 缺 rung2 实测时退 BOSS_WIN_P_FALLBACK(不静默归零)。"""
    _clear_extrap_cache()
    meta_no_rung2 = {
        k: v for k, v in cw_delta_pool_data.META.items()
        if k != 'battle_rung'}
    monkeypatch.setattr(cw_delta_pool_data, 'META', meta_no_rung2)
    try:
        assert cw_sim.boss_win_p(3) == cw_sim.BOSS_WIN_P_FALLBACK
    finally:
        _clear_extrap_cache()


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
    """提交快照:贫困披露与池内容自洽(0 未披露)。"""
    pool_map, _, _ = cw_sim.resolve_pool('snapshot')
    rep = check_delta_pool_bucket_coverage(
        pool_map, meta=cw_delta_pool_data.META)
    assert rep['violations'] == 0


def test_batch_report_embeds_coverage_check() -> None:
    """simulate_p1_batch 内嵌 delta_pool_bucket_coverage(ADR-0306 件5)。"""
    rep = cw_sim.simulate_p1_batch(3, pool='fallback', ledger=False,
                                   checks=True)
    cv = rep['checks_violations']
    assert 'delta_pool_bucket_coverage' in cv
    assert cv['delta_pool_bucket_coverage']['violations'] == 0


def test_boss_settle_uses_win_p_single_source() -> None:
    """boss_settle_delta 掷胜走 boss_win_p 单一取值口(不散落内联表)。"""
    import inspect
    src = inspect.getsource(cw_sim.boss_settle_delta)
    assert 'boss_win_p' in src
    assert 'BOSS_WIN_P_BY_ENGINES[' not in src
