"""策略卡选卡已损血衍生金检查腿测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_hp_loss_gold)。

测试面依据 = 迭代设计 designs/T-325-xingji-heping-baoxian.md §4 锁 2
(REVIEW-T325 无需用户决定 7/7;直构形态先例 = 同目录 test_check_strategy_boss_
end_heal.py 的容器直置):
- 纯函数锁:无卡 0 / 持卡 = max(0, opening−hp) / hp 未观察(None)→ 0
  (禁造假基座) / hp 已超开局血量(回血后)clamp 0 / 负基线入参
  ValueError;
- 归一通道锁:get_strategy 入口直读 STRATEGY_ECONOMY 注册行同实例
  (归一单一源,零第二份登记);
- 时点门归调用方(选卡落地拍在 sim 腿),sim 侧门锁 =
  sim/cw_sim_backend/test_strategy_hp_loss_gold_pick.py。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_hp_loss_gold,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    get_strategy,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='TestSigWriter')

_CARD = '星际和平保险'


def _gs(*cards: str) -> GameState:
    """直构 gs(持卡直置 = 持卡事实单一源;cards 空 = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if cards:
        gs.write_logic(gs.active_strategies, list(cards),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_no_card_returns_zero() -> None:
    """锁 2a:未持卡 → 0(零写零副作用,已损血再多也不发)。"""
    gs = _gs()
    before = gs.write_seq
    assert check_strategy_hp_loss_gold(gs, opening_hp=82) == 0, '未持卡应零'
    assert gs.write_seq == before, '纯读零写契约破坏'


def test_held_card_gold_equals_hp_lost() -> None:
    """锁 2b:持卡 → 已损血全额(opening−hp,clamp ≥0 由口径内置)。"""
    gs = _gs(_CARD)
    gs.observe(gs.hp, 57, sig=_SIG_OBS)   # 开局 82 → 直构损血至 57,已损 25
    assert check_strategy_hp_loss_gold(gs, opening_hp=82) == 25, \
        '衍生金 = 已损血全额'


def test_hp_unobserved_returns_zero() -> None:
    """锁 2c:hp 从未观察(None)→ 0,禁造假基座(apply_hp_outcome 未
    观察零写同款防御)。"""
    assert check_strategy_hp_loss_gold(_gs(_CARD), opening_hp=82) == 0, \
        'hp 未观察应零不猜'


def test_healed_above_opening_clamps_zero() -> None:
    """锁 2d:hp 高于开局血量(回血腿后合法形态)→ clamp 0,负差不出金。"""
    gs = _gs(_CARD)
    gs.observe(gs.hp, 95, sig=_SIG_OBS)
    assert check_strategy_hp_loss_gold(gs, opening_hp=82) == 0, \
        '回血越开局应 clamp 零'


def test_negative_opening_hp_raises() -> None:
    """锁 2e:负基线入参 ValueError(调用方传参错误响亮暴露,开局真值
    恒非负)。"""
    with pytest.raises(ValueError):
        check_strategy_hp_loss_gold(_gs(_CARD), opening_hp=-1)


def test_normalization_reads_registry_single_source() -> None:
    """锁 2f(归一单一源):检查函数所读 economy 对象 = STRATEGY_ECONOMY
    注册行同实例(get_strategy 归一入口直读注册表,零第二份登记)。"""
    strategy = get_strategy(_CARD)
    assert strategy is not None and strategy.economy \
        is STRATEGY_ECONOMY[_CARD], '归一通道应直读注册行单一源'
