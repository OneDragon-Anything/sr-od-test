"""货币战争 D牌期望模型(cw_shop_odds)测试 —— 纯逻辑,不依赖游戏。

验证 V4.4 牌池概率模型(77124902/77074467):二项+超几何+状态转移算期望刷新次数。
无精确 ground truth(原文只给方法+参数),测**单调性 + 边界**(关系正确即可):
- p↑ → 期望↓;j(已有)↑ → 期望↓;c(牌池操纵)↑ → 期望↓。
- 边界:p≤0/j≥k → 0;7级3费找2星有限正数;3星>2星。
"""
from __future__ import annotations

import math

from sr_od.application.currency_war.cw_shop_odds import (
    SHOP_SLOTS,
    expected_refreshes,
    expected_refreshes_for_card,
    refresh_prob,
)
from test import SrTestBase


class TestCurrencyWarShopOdds(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    # —— 边界 ——

    def test_zero_p_returns_zero(self):
        """p≤0 → 0(该等级不出该费用,刷不到)。"""
        self.assertEqual(expected_refreshes(0.0, 13, 18, 0, 3, 0), 0.0)

    def test_owned_meets_target_returns_zero(self):
        """j≥k → 0(已凑齐,无需再刷)。"""
        self.assertEqual(expected_refreshes(0.4, 13, 18, 0, 3, 3), 0.0)
        self.assertEqual(expected_refreshes(0.4, 13, 18, 0, 9, 10), 0.0)

    # —— 单调性 ——

    def test_higher_p_fewer_refreshes(self):
        """刷新概率越高,凑齐所需刷新次数越少。"""
        e_low = expected_refreshes(0.3, 13, 18, 0, 3, 0)
        e_mid = expected_refreshes(0.6, 13, 18, 0, 3, 0)
        e_high = expected_refreshes(1.0, 13, 18, 0, 3, 0)
        self.assertGreater(e_low, e_mid, "p=0.3 期望 > p=0.6")
        self.assertGreater(e_mid, e_high, "p=0.6 期望 > p=1.0")
        self.assertGreater(e_high, 0)

    def test_more_owned_fewer_refreshes(self):
        """手上已有越多目标牌,凑齐所需刷新越少(2星 k=3)。"""
        e0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
        e1 = expected_refreshes(0.4, 13, 18, 0, 3, 1)
        e2 = expected_refreshes(0.4, 13, 18, 0, 3, 2)
        self.assertGreater(e0, e1, "j=0 期望 > j=1")
        self.assertGreater(e1, e2, "j=1 期望 > j=2")

    def test_pool_manipulation_reduces_refreshes(self):
        """买走同费非目标牌(c↑)→ 目标在剩余池里更密 → 期望刷新↓(牌池操纵有效)。"""
        e_c0 = expected_refreshes(0.4, 13, 18, 0, 3, 0)
        e_c10 = expected_refreshes(0.4, 13, 18, 10, 3, 0)
        e_c30 = expected_refreshes(0.4, 13, 18, 30, 3, 0)
        self.assertGreater(e_c0, e_c10, "c=0 期望 > c=10")
        self.assertGreater(e_c10, e_c30, "c↑ 期望继续↓")

    # —— sanity ——

    def test_v44_example_finite_positive(self):
        """V4.4 实测参数(77124902 例):7级(p=0.4)找2星3费(v=13,a=18),手上1张 → 有限正数。"""
        e = expected_refreshes(0.4, 13, 18, 0, 3, 1)
        self.assertGreater(e, 0)
        self.assertFalse(math.isinf(e), "期望应为有限值")

    def test_three_star_needs_more_than_two_star(self):
        """3星(k=9)比 2星(k=3)需要更多刷新(凑齐更多张)。"""
        e_2star = expected_refreshes(0.4, 13, 18, 0, 3, 0)
        e_3star = expected_refreshes(0.4, 13, 18, 0, 9, 0)
        self.assertGreater(e_3star, e_2star, "3星(9张)期望 > 2星(3张)")

    # —— 便捷查询 ——

    def test_refresh_prob_lookup(self):
        """refresh_prob 查表:7级3费=0.4 实测点;无数据=0。"""
        self.assertAlmostEqual(refresh_prob(7, 3), 0.4, places=2)
        self.assertEqual(refresh_prob(99, 3), 0.0, "无该等级 → 0")

    def test_expected_refreshes_for_card(self):
        """便捷查询:7级 D 3费到 2星 → 有限正;已有2张 → 更少。"""
        e = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=0)
        self.assertGreater(e, 0)
        e_owned = expected_refreshes_for_card(level=7, cost=3, target_star=2, owned=2)
        self.assertLess(e_owned, e, "已有2张 → 期望更少")

    def test_shop_slots_is_5(self):
        """每次刷新 5 格(机制常量)。"""
        self.assertEqual(SHOP_SLOTS, 5)
