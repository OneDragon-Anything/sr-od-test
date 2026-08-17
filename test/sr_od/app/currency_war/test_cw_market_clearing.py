"""cw_market_clearing(43 号清算所)v0 测试:J0 零漂移 + 收敛 + J3 韧性注入 + 套利预算。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_market_clearing import (  # noqa: E402
    arbitrage_budget,
    clear,
)


class _SimpleTrader:
    """线性需求交易者:目标持有量 target,净需求 = target − price/scale(价高少要)。"""

    def __init__(self, name: str, target: float, scale: float = 1.0):
        self.name = name
        self.target = target
        self.scale = scale

    def net_demand(self, prices: dict[str, float]) -> dict[str, float]:
        # 双资源:gold 卖方(负需求换 gold 价)/卡买方
        return {'card': self.target - prices.get('card', 1.0) / self.scale}


def test_j0_zero_drift_when_no_traders_budget0() -> None:
    """J0 降级锚:max_iter=0(预算 0)→ π = π₀ 原值(精确现状级联,零漂移)。"""
    r = clear([_SimpleTrader('a', 2.0)], {'card': 1.0}, max_iter=0)
    assert r.prices == {'card': 1.0}
    assert not r.converged


def test_clearing_converges_to_equilibrium() -> None:
    """收敛:买方需求 3−p、卖方供给 p−1(报净需求 1−p,负号=向市场供)→ z_total=4−2p,
    均衡 p=2。"""
    class Buyer(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 3.0 - prices.get('card', 1.0)}       # 需求

    class Seller(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 1.0 - prices.get('card', 1.0)}       # 供给(负净需求)

    r = clear([Buyer('buyer', 0), Seller('seller', 0)], {'card': 1.0}, max_iter=60)
    assert r.converged, f"未收敛: {r.prices}"
    assert abs(r.prices['card'] - 2.0) < 0.1   # 均衡:z_total=0 → p=2


def test_j3_resilience_bad_initial_price() -> None:
    """J3 韧性注入:π₀ 故意错(偏离真均衡 3×,模拟 DP 常数错)→ 清算把价拉回均衡带
    (交易者否决坏价 = 权威自一致性而非自 DP)。"""
    class Buyer(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 3.0 - prices.get('card', 1.0)}

    class Seller(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 1.0 - prices.get('card', 1.0)}

    r_bad = clear([Buyer('b', 0), Seller('s', 0)], {'card': 6.0}, max_iter=80)
    assert r_bad.converged
    assert abs(r_bad.prices['card'] - 2.0) < 0.15, f"坏 π₀ 未被纠正: {r_bad.prices}"


def test_arbitrage_budget_semantics() -> None:
    """套利预算:均衡价下全资源 |z| 小(带内=市场无必要);偏离价下大(存在性依据)。"""
    class Buyer(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 3.0 - prices.get('card', 1.0)}

    class Seller(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': 1.0 - prices.get('card', 1.0)}

    eq = arbitrage_budget([Buyer('b', 0), Seller('s', 0)], {'card': 2.0})
    off = arbitrage_budget([Buyer('b', 0), Seller('s', 0)], {'card': 0.5})
    assert eq['card'] < 0.5 < off['card']


def test_price_floor_projection() -> None:
    """价格投影:下界 floor(资源价不为负)。"""
    class HeavySeller(_SimpleTrader):
        def net_demand(self, prices):
            return {'card': -5.0}

    r = clear([HeavySeller('hs', 0)], {'card': 1.0}, max_iter=10, floor=0.05)
    assert r.prices['card'] >= 0.05
