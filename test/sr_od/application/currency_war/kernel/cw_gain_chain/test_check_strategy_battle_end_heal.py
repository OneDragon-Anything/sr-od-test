"""策略卡战斗结束回血检查腿测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_battle_end_heal)。

测试面依据 = 迭代设计 designs/T-325-xingji-heping-baoxian.md §4 锁 3
(REVIEW-T325 免裁 7/7;直构形态先例 = 同目录 test_check_strategy_boss_
end_heal.py 的容器直置):
- 纯函数锁:无卡 0 / 持卡 10 / 双卡(奋斗协议 boss_end_heal_hp 同持)
  两函数各 Σ 各自字段独立不相串 / 表外卡 miss-safe(get_strategy 归一
  通道 miss = None 零贡献不炸);
- 归一通道锁:本卡规范名无分隔符形变支(normalize_invest_name 形变族
  = bullet/全角冒号映射,本卡名不含),归一面 = get_strategy 入口
  直读 STRATEGY_ECONOMY 注册行同实例(单一源,零第二份登记);
- 节点类型门归调用方(kind ∈ COMBAT_NODE_TYPES 在 sim 结算腿),本函数
  对任意持卡局返回合量,sim 侧门锁 =
  sim/cw_sim_backend/test_strategy_battle_end_heal_sim_chain.py。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_battle_end_heal,
    check_strategy_boss_end_heal,
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

_CARD = '星际和平保险'
_BOSS_CARD = '奋斗协议'


def _gs(*cards: str) -> GameState:
    """直构 gs(持卡直置 = 持卡事实单一源;cards 空 = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if cards:
        gs.write_logic(gs.active_strategies, list(cards),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_no_card_returns_zero() -> None:
    """锁 3a:未持卡 → 0(零写零副作用)。"""
    gs = _gs()
    before = gs.write_seq
    assert check_strategy_battle_end_heal(gs) == 0, '未持卡应零'
    assert gs.write_seq == before, '纯读零写契约破坏'


def test_held_card_returns_ten() -> None:
    """锁 3b:持星际和平保险 → 10(注册行直读)。"""
    assert check_strategy_battle_end_heal(_gs(_CARD)) == 10, '持卡回血合量'


def test_dual_card_two_functions_independent() -> None:
    """锁 3c(双卡不相串):星际和平保险 + 奋斗协议同持 → 战斗结束腿
    恰 10(只 Σ battle_end_heal_hp)、首领战腿恰 50(只 Σ boss_end_heal_
    hp)——两检查函数独立不相串,族邻腿零交叉污染。"""
    gs = _gs(_CARD, _BOSS_CARD)
    assert check_strategy_battle_end_heal(gs) == 10, \
        '战斗结束腿不得混入首领战字段'
    assert check_strategy_boss_end_heal(gs) == 50, \
        '首领战腿不得混入战斗结束字段'


def test_out_of_registry_card_miss_safe() -> None:
    """锁 3d(归一通道 miss-safe):表外卡经 get_strategy 归一 miss =
    None 零贡献不炸(与持卡并存时持卡腿照常)。"""
    assert check_strategy_battle_end_heal(_gs('躺平')) == 0, '表外卡零贡献'
    assert check_strategy_battle_end_heal(_gs('躺平', _CARD)) == 10, \
        '表外卡不吞持卡腿'


def test_normalization_reads_registry_single_source() -> None:
    """锁 3e(归一单一源):检查函数所读 economy 对象 = STRATEGY_ECONOMY
    注册行同实例(get_strategy 归一入口直读注册表,零第二份登记)。"""
    strategy = get_strategy(_CARD)
    assert strategy is not None and strategy.economy \
        is STRATEGY_ECONOMY[_CARD], '归一通道应直读注册行单一源'
