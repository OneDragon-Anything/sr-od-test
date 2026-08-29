# -*- coding: utf-8 -*-
"""批㉟ 检查项锁:A/B 方向性叙述的窗口口径守卫
(``check_ab_verdict_claim``)。

双向锁:green 路径(够 n 且超底的方向叙述、非方向叙述)通过;
变异杀(去 n 门/去噪声带门必红,防安慰剂)。来源实证见
``sim_压测_批㉟``:0302-0304 收官「三窗领先」产生于 n=30 窗,
n=100 复验符号翻转。
"""
import math

import pytest

from sr_od.application.currency_war.sim.cw_sim_checks import (
    AB_VERDICT_MIN_N,
    check_ab_verdict_claim,
)


def _floor(sd: float, n: int) -> float:
    return 1.96 * sd / math.sqrt(n)


def test_green_directional_above_floor_passes():
    """n≥门槛且 |diff| 超 95% 底:方向叙述合法(0 违规)。"""
    sd, n = 20.0, 100
    diff = _floor(sd, n) + 2.0
    out = check_ab_verdict_claim(diff, sd, n, 'leads')
    assert out['violations'] == 0
    assert out['directional'] is True


def test_nondirectional_claim_never_flagged():
    """平局/噪声/披露级叙述不辖(任何 n)。"""
    assert check_ab_verdict_claim(-3.0, 14.0, 30, 'noise')['violations'] == 0
    assert check_ab_verdict_claim(0.0, 0.0, 10, 'tie')['violations'] == 0


def test_campaign_case_n30_lead_is_violation():
    """批㉟ 实证形态:n=30 窗、|gap|=3、sd≈14(底≈5.0)→ 双违规。"""
    out = check_ab_verdict_claim(-3.0, 14.0, 30, '领先')
    assert out['violations'] >= 1
    assert any('below_min_n' in r for r in out['reasons'])
    assert any('noise_band' in r for r in out['reasons'])


def test_n100_within_noise_band_is_violation():
    """n=100 但差值在噪声带内:方向叙述仍违规(批㉟ anchor +1.87
    vs SE≈2.8 形态)。"""
    sd, n = 28.0, 100
    diff = 1.87
    assert diff < _floor(sd, n)
    out = check_ab_verdict_claim(diff, sd, n, 'behind')
    assert out['violations'] == 1
    assert 'noise_band' in out['reasons'][0]


def test_mutation_remove_n_gate_kills():
    """变异杀①:去 n 门(把门槛当 0)→ campaign case 漏报。"""
    out = check_ab_verdict_claim(-3.0, 14.0, 30, '领先')
    # 用被检函数自身口径模拟「无 n 门」:仅噪声带门时应只报 1 条;
    # 完整函数必须报 ≥2(含 below_min_n)——若实现丢了 n 门,
    # 下面的断言失败(变异被杀)。
    assert len(out['reasons']) >= 2


def test_mutation_remove_band_gate_kills():
    """变异杀②:去噪声带门 → n=100 带内形态漏报。"""
    out = check_ab_verdict_claim(1.87, 28.0, 100, 'behind')
    assert out['violations'] >= 1, '噪声带门失效会漏报带内方向叙述'


def test_min_n_constant_is_100():
    """门槛常量钉死(变更须过 ADR,防静默放宽)。"""
    assert AB_VERDICT_MIN_N == 100


if __name__ == '__main__':
    pytest.main([__file__, '-q'])
