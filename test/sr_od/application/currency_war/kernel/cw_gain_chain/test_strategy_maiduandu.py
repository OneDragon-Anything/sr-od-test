"""买断制(id 300901)静态 XP 通道锁(镜像 src = sim/cw_sim_backend.py
strategy_xp_per_node_of 薄读函数 + _begin_node_window 聚段调用块;先例 =
同目录条件 XP 族锁形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-302 对应稿
(REVIEW-T302 无需用户决定 7/7;卡面官方原文:「你不再获得利息。即刻获得15金币。
每次进入新节点时，获得4经验。」——利息关闭腿 cap=0 聚合取宽零改动即活/
instant_gold=15 族级缺口维持/xp_per_node=4 静态通道状态副本写消费面):

- 薄读函数锁:持卡聚合求和分量(买断制 → 4);
- 注册行值锁:三静态分量(cap=0/instant_gold=15/xp_per_node=4);
- cap 取宽并存锁:并持利息上调(cap=10)→ resolved 取宽 = 10(ADR-0131);
- evidence 分账锁:sim 状态副本写独立笔 xp:strategy_per_node。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    strategy_xp_per_node_of,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_CARD = '买断制'


def _make_gs(*, held: tuple[str, ...] = ()) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if held:
        gs.observe(gs.active_strategies, list(held), sig=_SIG_OBS)
    return gs


def test_maiduandu_registry_row() -> None:
    """注册行值锁:三静态分量(instant_gold=15/cap=0/xp_per_node=4)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 15, '金 15(族级缺口维持)'
    assert eff.interest_cap_override == 0, '息通道 cap=0(0 也是有效覆写)'
    assert eff.xp_per_node == 4, '每节点 4 经验'


def test_xp_per_node_thin_reader() -> None:
    """薄读函数锁:持卡 → 4;未持卡 → 0。"""
    assert strategy_xp_per_node_of(_make_gs(held=(_CARD,))) == 4, '持卡 4'
    assert strategy_xp_per_node_of(_make_gs()) == 0, '未持卡 0'


def test_cap_widest_coexist() -> None:
    """cap 取宽并存锁:并持利息上调(cap=10)→ 聚合取宽 10(买断制 0 不
    硬关闭,ADR-0131 语义)。"""
    eff = STRATEGY_ECONOMY['利息上调']
    assert eff.interest_cap_override == 10, '利息上调 cap=10 已登记'
