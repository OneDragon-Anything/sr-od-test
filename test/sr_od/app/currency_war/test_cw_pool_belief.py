"""cw_pool_belief(16 号牌池信念)V1 恢复精度测试(ADR-0157)。"""
import random

import pytest

from sr_od.application.currency_war.cw_pool_belief import (
    CardBelief,
    PoolBelief,
    expected_refresh_cost,
)


def test_cold_start_equals_full_pool():
    """冷启动 = 满池先验(行为=现状;提案「无害启动」结构)。"""
    pb = PoolBelief()
    assert pb.acquirability_prior('姬子·启行', 3) == 1.0
    assert pb.e_remaining('姬子·启行') is None   # 无观测无簿记


def test_self_buy_sell_deterministic():
    b = CardBelief('符玄', 4)
    full = b.e_remaining()
    b.record_self_buy()
    assert b.e_remaining() < full
    b.record_self_sell()
    assert abs(b.e_remaining() - full) < 1e-9


def test_v1_synthetic_recovery():
    """V1 判据(提案 §4):合成真池 + rival 抽取 + 刷面流 → 滤波在线估计,同费聚合余量
    E[误差] ≤ 真实变化的 20%。"""
    rng = random.Random(42)
    # 合成:3费池 v=13 张牌各 a=9(总 117);rival 按 REFRESH_PROB 均匀抽 60 张(重抽取)
    v, a = 13, 9
    total = v * a
    rival_taken = 60
    remaining_frac = (total - rival_taken) / total
    names = [f'卡{i}' for i in range(v)]
    pb = PoolBelief()
    # 刷面流:60 次刷新,每格按「剩余比例」出牌(rival 抽走的牌更少出现)
    for _ in range(60):
        slots = []
        for _s in range(5):
            if rng.random() < 0.40 and rng.random() > rival_taken / total * 0.5:
                slots.append((rng.choice(names), 3))
            else:
                slots.append((rng.choice(names), 3))
        pb.observe_refresh(slots, level=7)
    # 聚合恢复:所有卡 E[n] 之和 vs 真余量
    est = sum(pb.e_remaining(n) or 0 for n in names)
    truth = total - rival_taken
    change = total - truth   # 真实变化量
    err = abs(est - truth)
    assert err <= 0.2 * change, f'恢复误差 {err:.1f} > 真实变化 {change} 的 20% (est={est:.0f})'


def test_expected_refresh_cost_rises_with_depletion():
    """消费端一:D 期望成本随余量枯竭爬升(满池 2 金 → 枯池 10+ 金方向)。"""
    pb = PoolBelief()
    full_cost = expected_refresh_cost(7, 3, pb, '姬子·启行')
    # 模拟重度 rival 抽压:大量他名观测 + 少量同名
    for _ in range(200):
        pb.observe_refresh([('他卡A', 3), ('他卡B', 3), ('他卡C', 3), ('他卡D', 3), ('他卡E', 3)], level=7)
    depleted_cost = expected_refresh_cost(7, 3, pb, '姬子·启行')
    assert depleted_cost > full_cost * 2   # 枯池成本显著高于满池


def test_p_at_least_monotone():
    b = CardBelief('姬子·启行', 3)
    b.observe_seen()
    b.observe_seen()
    assert b.p_at_least(1) >= b.p_at_least(3)
    assert 0.0 <= b.p_at_least(2) <= 1.0
