"""cw_censoring(48 号删失感知层)v0 测试:stage 分解语义 + J0 偏差检出。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_censoring import (  # noqa: E402
    RunRecord,
    compare_vs_scalar,
    kaplan_meier_reach,
    outcomes_to_runs,
    stage_decompose,
)


def test_outcomes_to_runs_domain_guard() -> None:
    """值域守卫(M70 假 win 摄取口固化):plane=8/9 域外行不作 plane 证据;
    全域外的局剔除;域内行正常聚合。"""
    rows = [
        # 正常局:plane 1→2
        {'run_id': 'ok', 'plane': 1, 'hp_after': 50, 'comp_tag': '列车同行'},
        {'run_id': 'ok', 'plane': 2, 'hp_after': 0, 'comp_tag': '列车同行'},
        # M70 型污染局:全部行 plane=8(难度/等级泄漏)
        {'run_id': 'm70', 'plane': 8, 'hp_after': 0, 'comp_tag': 'X'},
        # 混合局:一条域外 + 一条域内
        {'run_id': 'mix', 'plane': 9, 'hp_after': 30, 'comp_tag': '万敌单C'},
        {'run_id': 'mix', 'plane': 2, 'hp_after': 10, 'comp_tag': '万敌单C'},
    ]
    recs = outcomes_to_runs(rows)
    ids = {r.run_id for r in recs}
    assert ids == {'ok', 'mix'}          # m70 全域外被剔除
    mix = next(r for r in recs if r.run_id == 'mix')
    assert mix.plane_reached == 2        # 域外 9 不计入
    ok = next(r for r in recs if r.run_id == 'ok')
    assert ok.plane_reached == 2 and not ok.survived


def _runs(spec: list[tuple[str, bool, int]]) -> list[RunRecord]:
    """(line, survived, plane_reached) → 记录列表。"""
    return [RunRecord(f'r{i}', ln, s, p) for i, (ln, s, p) in enumerate(spec)]


def test_stage_decompose_semantics() -> None:
    """P(win) = P(r2)×P(r3|r2)×P(win|r3) 乘积还原 scalar(分解自洽);零分母 None。"""
    spec = [('A', True, 3), ('A', False, 3), ('A', False, 2), ('A', False, 1), ('A', False, 1)]
    rep = stage_decompose(_runs(spec))
    d = rep['by_line']['A']
    assert d['n'] == 5
    assert d['p_reach_p2'] == 0.6 and d['p_reach_p3'] == 0.4
    assert d['p_reach_p3_given_p2'] == round(2 / 3, 4)
    assert d['p_win_given_p3'] == 0.5
    assert abs(d['scalar_vs_product']) < 1e-6   # 乘积 = 标量(分解自洽)
    # 零到达线:p(win|p3) = None(显式,非 0)
    rep2 = stage_decompose(_runs([('B', False, 1)] * 4))
    assert rep2['by_line']['B']['p_win_given_p3'] is None


def test_km_reach() -> None:
    """到达曲线:比例语义 + 空集防御。"""
    rs = _runs([('A', False, 2), ('A', True, 3), ('A', False, 1)])
    assert kaplan_meier_reach(rs, 2) == 2 / 3
    assert kaplan_meier_reach(rs, 3) == 1 / 3
    assert kaplan_meier_reach([], 2) == 0.0


def test_j0_finds_masked_late_potential() -> None:
    """J0 迹象一:scalar=0 但到达 p3 → 「后期潜力被掩埋」检出(maybe_pivot 量纲错实例)。"""
    spec = ([('A', False, 3)] * 3 + [('A', False, 1)] * 5)   # 到 p3 三次全输,5 次早死
    rep = compare_vs_scalar(_runs(spec))
    assert rep['j0_verdict'] != 'no_substantial_diff'
    f = [x for x in rep['findings'] if x['kind'] == 'late_potential_masked']
    assert f and f[0]['line'] == 'A'


def test_j0_quiet_when_consistent() -> None:
    """一致性语料(全通关/全早死无 p3)→ 无实质偏差(零误报)。"""
    spec = [('C', True, 3)] * 4 + [('D', False, 1)] * 4
    rep = compare_vs_scalar(_runs(spec))
    assert rep['findings'] == []


def test_j0_finds_survivor_inflation() -> None:
    """J0 迹象二:scalar>0 但 p(reach p2)<0.5 → 幸存者条件虚高检出。"""
    spec = ([('E', True, 3)] * 2 + [('E', False, 1)] * 6)   # 2/8 通关但早期到达仅 25%
    rep = compare_vs_scalar(_runs(spec))
    f = [x for x in rep['findings'] if x['kind'] == 'survivor_condition_inflated']
    assert f and f[0]['line'] == 'E'
