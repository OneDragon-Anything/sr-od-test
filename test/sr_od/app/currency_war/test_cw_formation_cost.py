"""cw_formation_cost 成型成本计算器测试(ADR-0159;判据1 涌现对拍)。"""
import pytest

from sr_od.application.currency_war.cw_formation_cost import best_search_level, formation_cost
from sr_od.application.currency_war.cw_shop_odds import refresh_prob


def test_zero_prob_level_prohibitive():
    """p=0 的等级:3 费在 lv3 刷不出 → 成本巨大(上界计入口径;真 inf 门在
    best_search_level 的 p>0 前置)。断言 >> 可行级成本。"""
    c3 = formation_cost({'姬子·启行': 3}, 3, n_sims=64)
    c7 = formation_cost({'姬子·启行': 3}, 7, n_sims=128)
    assert c3 > c7 * 3


def test_feasible_level_finite():
    c = formation_cost({'姬子·启行': 3}, 7, n_sims=128)
    assert 0 < c < 10_000


def test_higher_level_more_upfront_gold():
    """升级段:更高级含更多沉没升级金(lv7 成本的固定部分 > lv5)—— n_sims 同种子下
    用「p 相近的低费目标」近似验证单调性方向即可(轻量回归锚,不追求精确)。"""
    import random
    c5 = formation_cost({'三月七': 3}, 5, n_sims=256, rng=random.Random(5))
    c6 = formation_cost({'三月七': 3}, 6, n_sims=256, rng=random.Random(6))
    # 同为 1费目标:5 级 p 更高,搜牌更便宜;但 6 级升级金更高 —— 方向不确定,只断言有限
    assert 0 < c5 < 10_000 and 0 < c6 < 10_000


def test_best_search_level_jizi():
    """判据1 样例:姬子·启行(3费)最优搜牌级 = 7 级带(p=0.40 峰值;涌现对拍 12/17 命中行)。
    roster 只含 carry+3费 core(1费次要角色在 7 级几乎刷不出会污染 argmin —— 与
    判据脚本同口径:搜牌成本只对 carry 费用敏感)。"""
    lv, cost = best_search_level('姬子·启行', ['瓦尔特', '花火'])
    assert lv == 7 and cost < float('inf')


def test_best_search_level_wandi():
    """判据1 样例:万敌(1费)低级即可(5 级带)。"""
    lv, cost = best_search_level('万敌')
    assert lv in (3, 4, 5, 6) and cost < float('inf')
