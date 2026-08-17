"""cw_price_ledger(35 号影子价格总线)v0 测试:J1 注入恢复 + 环审计 + 形状合约。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_price_ledger import (  # noqa: E402
    AnchorState,
    anchor_states,
    arb_cycle_buy_sell,
    price_matrix,
    price_shape_contracts,
    shadow_price,
)


def _mock_value(t: int, gold: int, level: int, hp: int) -> float:
    """合成值函数:gold 对数递减 + hp 线性低血加权 + level 线性(健康形状)。"""
    import math
    return 10 * math.log1p(gold) + (0.2 if hp < 40 else 0.05) * hp + 3 * level


def _mock_bad_value(t: int, gold: int, level: int, hp: int) -> float:
    """病态值函数:gold 边际递增(违反递减形状)。"""
    return 0.002 * gold * gold + hp * 0.05 + 3 * level


def test_shadow_price_semantics() -> None:
    """差分语义:mock 对数效用 → gold 价为正且随金位递减。"""
    s_low = AnchorState(4, 10, 5, 50)
    s_hi = AnchorState(4, 60, 5, 50)
    p_low = shadow_price(s_low, 'gold', _mock_value)
    p_hi = shadow_price(s_hi, 'gold', _mock_value)
    assert p_low > 0 and p_hi > 0 and p_low > p_hi


def test_anchor_states_grid() -> None:
    """锚定集:代表网格覆盖 3 位面段 × 金/血/等级档。"""
    sts = anchor_states()
    assert len(sts) >= 27
    assert {a.t for a in sts} == {4, 13, 22}
    assert {a.hp for a in sts} >= {20, 50, 80}


def test_arb_cycle_buy_sell() -> None:
    """H2 环审计:机制精确价(1星全额退=无损循环 ok;注入 bug 价→arb 检出)。"""
    ok = arb_cycle_buy_sell(cost=2, star=1)
    assert ok['cycle_ratio'] == 1.0 and ok['verdict'] == 'ok'
    # 注入错价:卖回 > 买入(价值生成器)→ 检出
    bad = arb_cycle_buy_sell(cost=1, star=2, fee_tolerance=-4)   # refund=3-(-?) → 构造 >1+tol
    # 直接验证报警条件逻辑:refund 3 / cost 1 = 3.0 > tol → arb
    assert bad['verdict'] == 'arb'


def test_j1_shape_contracts_detect_violation() -> None:
    """J1 注入恢复:健康形状 pass;病态(gold 递增)→ gold 违约检出。"""
    sts = anchor_states()
    good = price_shape_contracts(price_matrix(sts, _mock_value))
    assert good['verdict'] == 'pass'
    bad = price_shape_contracts(price_matrix(sts, _mock_bad_value))
    assert bad['gold_monotone_violations'] > 0
    assert bad['verdict'] == 'fail'
