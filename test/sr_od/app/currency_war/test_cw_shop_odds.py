"""货币战争 D牌期望模型(cw_shop_odds)测试 —— 纯逻辑,不依赖游戏。

验证 V4.4 牌池概率模型(77124902/77074467):二项+超几何+状态转移算期望刷新次数。
无精确 ground truth(原文只给方法+参数),测**单调性 + 边界**(关系正确即可):
- p↑ → 期望↓;j(已有)↑ → 期望↓;c(牌池操纵)↑ → 期望↓。
- 边界:p≤0/j≥k → 0;7级3费找2星有限正数;3星>2星。
"""
from __future__ import annotations

import math

import pytest

from sr_od.application.currency_war.data.cw_shop_odds import (
    SHOP_SLOTS,
    expected_refreshes,
    expected_refreshes_for_card,
    refresh_prob,
)

# —— 边界 ——


def test_zero_p_returns_zero() -> None:
    """p≤0 → 0(该等级不出该费用,刷不到)。"""
    assert expected_refreshes(0.0, 13, 18, 0, 3, 0) == 0.0


def test_owned_meets_target_returns_zero() -> None:
    """j≥k → 0(已凑齐,无需再刷)。"""
    assert expected_refreshes(0.4, 13, 18, 0, 3, 3) == 0.0
    assert expected_refreshes(0.4, 13, 18, 0, 9, 10) == 0.0


# —— 单调性 ——


def test_higher_p_fewer_refreshes() -> None:
    """刷新概率越高,凑齐所需刷新次数越少。"""
    e_low = expected_refreshes(0.3, 13, 18, 0, 3, 0)
    e_mid = expected_refreshes(0.6, 13, 18, 0, 3, 0)
    e_high = expected_refreshes(1.0, 13, 18, 0, 3, 0)
    assert e_low > e_mid, "p=0.3 期望 > p=0.6"
    assert e_mid > e_high, "p=0.6 期望 > p=1.0"
    assert e_high > 0


def test_more_owned_fewer_refreshes() -> None:
    """手上已有越多目标牌,凑齐所需刷新越少(2星 k=3)。"""
    e0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e1 = expected_refreshes(0.4, 13, 18, 0, 3, 1)
    e2 = expected_refreshes(0.4, 13, 18, 0, 3, 2)
    assert e0 > e1, "j=0 期望 > j=1"
    assert e1 > e2, "j=1 期望 > j=2"


def test_pool_manipulation_reduces_refreshes() -> None:
    """买走同费非目标牌(c↑)→ 目标在剩余池里更密 → 期望刷新↓(牌池操纵有效)。"""
    e_c0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e_c10 = expected_refreshes(0.4, 13, 18, 10, 3, 0)
    e_c30 = expected_refreshes(0.4, 13, 18, 30, 3, 0)
    assert e_c0 > e_c10, "c=0 期望 > c=10"
    assert e_c10 > e_c30, "c↑ 期望继续↓"


# —— sanity ——


def test_v44_example_finite_positive() -> None:
    """V4.4 实测参数(77124902 例):7级(p=0.4)找2星3费(v=13,a=18),手上1张 → 有限正数。"""
    e = expected_refreshes(0.4, 13, 18, 0, 3, 1)
    assert e > 0
    assert not math.isinf(e), "期望应为有限值"


def test_three_star_needs_more_than_two_star() -> None:
    """3星(k=9)比 2星(k=3)需要更多刷新(凑齐更多张)。"""
    e_2star = expected_refreshes(0.4, 13, 18, 0, 3, 0)
    e_3star = expected_refreshes(0.4, 13, 18, 0, 9, 0)
    assert e_3star > e_2star, "3星(9张)期望 > 2星(3张)"


# —— 便捷查询 ——


def test_refresh_prob_lookup() -> None:
    """refresh_prob 查表:7级3费=0.4 实测点;无数据=0。"""
    assert refresh_prob(7, 3) == pytest.approx(0.4, abs=1e-2)
    assert refresh_prob(99, 3) == 0.0, "无该等级 → 0"


def test_expected_refreshes_for_card() -> None:
    """便捷查询:7级 D 3费到 2星 → 有限正;已有2张 → 更少。"""
    e = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=0)
    assert e > 0
    e_owned = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=2)
    assert e_owned < e, "已有2张 → 期望更少"


def test_shop_slots_is_5() -> None:
    """每次刷新 5 格(机制常量)。"""
    assert SHOP_SLOTS == 5
