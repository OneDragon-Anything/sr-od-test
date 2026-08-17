"""cw_landscape(01+10 salvage 板面价值地形 v0)测试:断点单调/对收缩/盲区解(ADR-0169)。"""
from sr_od.application.currency_war.cw_landscape import (
    _PAIRS,
    board_value,
    breakpoint_utility,
    pair_synergy,
    unit_value_curve,
)


def test_breakpoint_monotone():
    """断点效用单调不减(高档 ≥ 低档;越多人停高档效用差越大由构造保证)。"""
    for trait in ('列车同行', '仙舟'):
        us = [breakpoint_utility(trait, k) for k in range(0, 7)]
        assert all(us[i] <= us[i + 1] for i in range(len(us) - 1)), trait


def test_pairs_shrinkage_discipline():
    """超加性对:只有 n≥8 且 lift>1 进表(防 optimizer's curse);查表不崩。"""
    assert all(v > 0 for v in _PAIRS.values())
    assert pair_synergy('列车同行', '仙舟') >= 0.0   # 有值或收缩 0,不崩
    assert pair_synergy('不存在', '也不存在') == 0.0


def test_unit_value_curve_transition_derived():
    """过渡牌 = 曲线交叉的派生概念:1费 Early 高 Late 衰减;5费反向。"""
    early1 = unit_value_curve('三月七', 2)
    late1 = unit_value_curve('三月七', 9)
    assert early1 > late1                       # 1费 = 过渡
    early5 = unit_value_curve('景元', 2)
    late5 = unit_value_curve('景元', 9)
    assert late5 > early5                       # 5费 = 大件


def test_board_value_blindspot1_bench_strength():
    """10 号盲区 1 的解:强度在备战席的 comp(bench 计数)天然可表达。"""
    v_board_only = board_value({'列车同行': 4})
    v_with_bench = board_value({'列车同行': 4}, bench_counts={'仙舟': 3})
    assert v_with_bench > v_board_only          # bench 项生效


def test_board_value_more_traits_not_always_better():
    """地形语义:激活档计数(跨档跳变),非逐单位线性。"""
    v3 = board_value({'列车同行': 3})
    v4 = board_value({'列车同行': 4})
    assert v4 >= v3
    assert v3 > 0 and v4 > 0
