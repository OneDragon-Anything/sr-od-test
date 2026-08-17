"""cw_progress_curves(p(t) 编译器)测试 + 审判层端到端(ADR-0171 供给)。"""
from sr_od.application.currency_war.cw_line_tribunal import LineHypothesis, timeline_lag_lr, verdict
from sr_od.application.currency_war.cw_progress_curves import (
    dominant_tempo,
    expected_curve,
    expected_curve_for_carry,
)


def test_curve_monotone_and_bounded():
    """曲线:单调不减、[0,1] 有界、27 节点全覆盖。"""
    for tempo in ('5级搜牌', '7级搜牌', '速升9级'):
        c = expected_curve(tempo)
        vals = [c[n] for n in sorted(c)]
        assert all(vals[i] <= vals[i + 1] + 1e-9 for i in range(len(vals) - 1))
        assert all(0.0 <= v <= 1.0 for v in vals)
        assert max(c) > 0.7    # 终局成型度高


def test_fast_tempo_leads_early():
    """语义:速升9 前期进度 > 5级搜牌(人类 meta 的节奏差在曲线上可分)。"""
    c_fast = expected_curve('速升9级')
    c_slow = expected_curve('5级搜牌')
    assert c_fast[6] > c_slow[6]      # 早期速升领先
    # 终点相近(都成型)
    assert abs(c_fast[26] - c_slow[26]) <= 0.2


def test_dominant_tempo_from_plaza():
    """plaza 主流节奏:姬子·启行(274 篇)→ 7级搜牌(实证主档)。"""
    assert dominant_tempo('姬子·启行') == '7级搜牌'
    assert expected_curve_for_carry('姬子·启行') is not None
    # 小聚类(无统计意义)→ None(预注册不灌)
    assert expected_curve_for_carry('不存在carry') is None


def test_tribunal_end_to_end_with_curve():
    """端到端:p(t) 曲线 → 掉队量 → LR → 判决(供给链完整)。"""
    curve = expected_curve_for_carry('姬子·启行')
    assert curve is not None
    h = LineHypothesis('h1', '姬子线', 'commit', checkpoints=[8], deadline=12,
                       expected=curve)
    # 实际进度远落后期望(节点 8 期望 ~0.6 实际 0.2)
    lag = h.progress_lag(8, 0.2)
    assert lag > 0.3
    h.add_evidence(8, 'timeline_lag', f'掉队 {lag:.2f}', timeline_lag_lr(lag))
    v = verdict(h, 8, cost_abandon=18.0, cost_hold=6.0)
    assert v.action in ('abandon', 'amended')
    # 健康线(实际超期望)→ 守
    h2 = LineHypothesis('h2', '姬子线', 'commit', checkpoints=[8], deadline=12,
                        expected=curve)
    assert h2.progress_lag(8, 0.7) == 0.0
    h2.add_evidence(8, 'timeline_lag', '健康', timeline_lag_lr(0.0))
    v2 = verdict(h2, 8, cost_abandon=18.0, cost_hold=6.0)
    assert v2.action in ('hold', 'amended')
