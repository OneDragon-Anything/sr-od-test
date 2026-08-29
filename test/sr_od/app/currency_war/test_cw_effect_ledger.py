"""cw_effect_ledger(53 号既持效果台账)v0 测试:三算例涌现方向(53 号 §2.2)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_effect_ledger import (  # noqa: E402
    AggregateEffect,
    build_env_ledger,
    build_ledger,
    interest_with,
    level_cost_with,
    node_income_with,
)


def test_case_spy_xp_discount() -> None:
    """算例 1 商业间谍(单击 4→3):升级成本全线 −25%。"""
    led = build_ledger([AggregateEffect('商业间谍', 'xp_click_delta', -1.0)])
    assert level_cost_with(30, led) == 90.0        # 30 击 × 3
    assert level_cost_with(30, build_ledger([])) == 120.0   # 基线 4


def test_case_longtermism_timing() -> None:
    """算例 2 长期主义:日程时点价值——gold 43 时下节点 +7 跨 50 息档(摊平分给不出)。"""
    led = build_ledger([AggregateEffect('长期主义', 'next_nodes', 7.0, remaining_nodes=3)])
    # gold 43 + 节点收入(5+7)= 55 ≥ 50 → 跨息档;无日程时 43+5=48 < 50 不跨
    assert node_income_with(0, 5.0, 0.0, led) == 12.0
    assert 43 + node_income_with(0, 5.0, 0.0, led) >= 50
    assert 43 + node_income_with(0, 5.0, 0.0, build_ledger([])) < 50
    # 日程只在余期内
    assert led.calendar_at(5) == 0.0


def test_case_buyout_cap_zero() -> None:
    """算例 3 买断制(cap 0):interest 恒 0 → 攒金无意义(现状活矛盾:为不付息的钱守 50)。"""
    led = build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)])
    assert interest_with(80, led) == 0
    assert interest_with(80, build_ledger([])) == 5   # 基线息
    # 息上调
    led10 = build_ledger([AggregateEffect('利息上调', 'interest_cap', 10.0)])
    assert interest_with(120, led10) == 10


def test_win_reward_multiplier() -> None:
    """伟大征服 ×3:连胜金乘子进收入(现状 DP 照 ×1 算)。"""
    led = build_ledger([AggregateEffect('伟大征服', 'win_mult', 3.0)])
    assert node_income_with(0, 5.0, 2.0, led) == 5.0 + 6.0   # streak 2×3
    assert node_income_with(0, 5.0, 2.0, build_ledger([])) == 7.0


def test_boss_node_calendar() -> None:
    """特战资金 boss+7:boss 位日程(粗锚 8/17/26)。"""
    led = build_ledger([AggregateEffect('特战资金', 'boss_node', 7.0)])
    assert led.calendar_at(8) == 7.0 and led.calendar_at(0) == 0.0


def test_ledger_buysell_wiring_semantics_retained() -> None:
    """批 3 DP 退役后的台账语义残留锁:台账构建/效果解析通道保留
    (消费面=cw_economy 经济效果;原 DP 值函数注入断言随 cw_horizon
    退役删除——锁面重推出处=BLUEPRINT §3 DP 处置,git prior art)。"""
    from sr_od.application.currency_war.cw_effect_ledger import (
        build_ledger,
        effects_from_strategies,
    )
    led = build_ledger(effects_from_strategies(['买断制']))
    assert led.mutations.interest_cap == 0   # 买断制:息帽 0(台账仍承载经济效果)

def test_v1_overlay_routes() -> None:
    """v1 全量扫描补的路由:采购专员 surprise_every / 淘金客 xp_per_refresh /
    买断制 xp_per_node / 免费午餐 burst。"""
    led = build_ledger([
        AggregateEffect('采购专员·彩', 'surprise_every', 5),
        AggregateEffect('淘金客', 'xp_per_refresh', 2.0),
        AggregateEffect('买断制', 'xp_per_node', 4.0),
        AggregateEffect('免费午餐', 'free_refresh_burst', 11),
    ])
    m = led.mutations
    assert m.refresh_surprise_every == 5
    assert m.xp_per_refresh == 2.0
    assert m.xp_per_node == 4.0
    assert m.free_refresh_burst == 11


def test_env_ledger_plane_start_gold() -> None:
    """环境侧扩展(ADR-0144 缺口首补):增发货币 → 位面首节点日程;
    长线利好 → 刷新价突变(30 刷后 1 金,与 38 号跨线投资联动)。"""
    led = build_env_ledger(['增发货币', '长线利好'])
    assert led.calendar_at(0) == 6.0       # P1 首节点
    assert led.mutations.refresh_discount_at == 30
    assert led.mutations.refresh_price_after == 1
    # 未覆盖环境 = 空台账 = 现状行为
    empty = build_env_ledger(['火药味'])
    assert empty.calendar == {} and empty.mutations.refresh_discount_at == 0
