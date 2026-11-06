"""策略卡首领战结束回血检查腿测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_boss_end_heal)。

测试面依据 = 迭代设计 designs/T-313-fendou-xieyi.md §4 锁 2(REVIEW
-T313 无需用户决定 6/6;直构形态先例 = 同目录 test_check_strategy_boss_battle_
grants.py 的状态容器直置):
- 纯函数锁:无卡 0 / 持卡 50 / 多卡累加(持无回血腿的他卡不合量误加)
  / 表外卡 miss-safe(get_strategy 归一通道 miss = None 零贡献不炸);
- 归一通道锁:本卡规范名无分隔符形变支,归一面 = get_strategy 入口
  (active_strategies 存量 OCR 原始名经 normalize_invest_name 归一,
  blood_xp_mode 同法)——锁 economy 对象与 STRATEGY_ECONOMY 注册行同
  实例(直读单一源,零第二份登记);
- 节点类型门归调用方(kind == 'boss' 在 sim 结算腿),本函数对任意
  持卡局返回合量,sim 侧门锁 = sim/cw_sim_backend/
  test_strategy_boss_end_heal_sim_chain.py。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '奋斗协议'


def _gs(*cards: str) -> GameState:
    """直构 gs(持卡直置 = 持卡事实单一源;cards 空 = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if cards:
        gs.write_logic(gs.active_strategies, list(cards),
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def test_no_card_returns_zero() -> None:
    """锁 2a:未持卡 → 0(零写零副作用)。"""
    gs = _gs()
    before = gs.write_seq
    assert check_strategy_boss_end_heal(gs) == 0, '未持卡应零'
    assert gs.write_seq == before, '纯读零写契约破坏'


def test_held_card_returns_fifty() -> None:
    """锁 2b:持奋斗协议 → 50(注册行直读)。"""
    assert check_strategy_boss_end_heal(_gs(_CARD)) == 50, '持卡回血合量'


def test_multi_card_sum_only_heal_members() -> None:
    """锁 2c(多卡累加):奋斗协议 + 成本控制(无回血腿成员)→ 仍 50
    ——逐持卡 Σ boss_end_heal_hp,无腿成员零贡献不误加。"""
    assert check_strategy_boss_end_heal(_gs(_CARD, '成本控制')) == 50, \
        '无腿他卡不得误入合量'


def test_out_of_registry_card_miss_safe() -> None:
    """锁 2d(归一通道 miss-safe):表外卡经 get_strategy 归一 miss =
    None 零贡献不炸(与持卡并存时持卡腿照常)。"""
    assert check_strategy_boss_end_heal(_gs('躺平')) == 0, '表外卡零贡献'
    assert check_strategy_boss_end_heal(_gs('躺平', _CARD)) == 50, \
        '表外卡不吞持卡腿'


def test_normalization_reads_registry_single_source() -> None:
    """锁 2e(归一单一源):检查函数所读 economy 对象 = STRATEGY_ECONOMY
    注册行同实例(get_strategy 归一入口直读注册表,零第二份登记)。"""
    strategy = get_strategy(_CARD)
    assert strategy is not None and strategy.economy \
        is STRATEGY_ECONOMY[_CARD], '归一通道应直读注册行单一源'
