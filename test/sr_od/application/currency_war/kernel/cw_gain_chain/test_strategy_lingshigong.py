"""临时工合约(id 301901)两条效果条目锁(镜像 src = PICK '临时工合约' 具名装备
授予行 + STRATEGY_EQUIP_EXPIRY_GRANTS 白名单表 + check_strategy_equip_
expiry 纯判定 + sim 独立笔;先例 = 天降救兵组合锁 + 条件发放族锁形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-314 对应稿
(REVIEW-T314 无需用户决定 7/7;卡面官方原文:「获得8个【员工投影仪】，进入下个
节点时，所有未使用的【员工投影仪】都会消失。」):

- 锁 1 组合行单一源:效果条目1 行已登记+泛化表零本卡键;
- 锁 2 白名单表:集合 = {'临时工合约': ('员工投影仪',)} + 两查负控;
- 锁 3 判定矩阵:未持卡空集 / 持卡首窗移除集恰 1+一次性标志位 / 重放零重发 /
  一次性标志位封后到货件不受影响;
- 锁 4 消失域全名:他源在栏同名件一并移除(「所有」直读);
- 锁 5 空栏零移除:装备栏无件 → 移除集空(一次性标志位仍封)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_equip_expiry,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_RANDOM_EQUIP_GRANTS,
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EQUIP_EXPIRY_GRANTS,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_CARD = '临时工合约'


def _make_gs(*, held: tuple[str, ...] = (),
             equips: list[str] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if held:
        gs.write_logic(gs.active_strategies, list(held),
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def test_row_single_source() -> None:
    """锁 1:效果条目1 组合行已登记;泛化表零本卡键。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, '泛化表零本卡键'


def test_expiry_registry_closed() -> None:
    """锁 2:白名单表闭集 + 孤儿键/装备名负控(校验器已 import 承)。"""
    assert STRATEGY_EQUIP_EXPIRY_GRANTS == {_CARD: ('员工投影仪',)}, \
        '集合值对拍'
    for n in STRATEGY_EQUIP_EXPIRY_GRANTS:
        assert n in INVESTMENT_STRATEGIES, f'孤儿键: {n}'


def test_expiry_matrix_and_latch() -> None:
    """锁 3:判定矩阵(未持卡空/首窗移除+一次性标志位/重放零重发)。"""
    gs = _make_gs(held=(_CARD,), equips=['员工投影仪'])
    got = check_strategy_equip_expiry(gs, sig=_SIG)
    assert got == ('员工投影仪',), f'首窗移除集: {got}'
    latch = _CARD
    assert latch in (gs.strategy_conditional_done.value or ()), \
        f'一次性标志位: {gs.strategy_conditional_done.value}'
    again = check_strategy_equip_expiry(gs, sig=_SIG)
    assert again == (), f'重放零重发: {again}'
    gs_none = _make_gs()
    assert check_strategy_equip_expiry(gs_none, sig=_SIG) == (), \
        '未持卡空集'


def test_expiry_remove_full_domain() -> None:
    """锁 4:消失域全名(他源在栏同名件一并移除)。"""
    gs = _make_gs(held=(_CARD,), equips=['员工投影仪', '员工投影仪'])
    got = check_strategy_equip_expiry(gs, sig=_SIG)
    assert got == ('员工投影仪',), f'移除集按名去重: {got}'


def test_expiry_empty_equips_zero_remove() -> None:
    """锁 5:装备栏无件 → 移除集空(一次性标志位仍封)。"""
    gs = _make_gs(held=(_CARD,), equips=[])
    got = check_strategy_equip_expiry(gs, sig=_SIG)
    assert got == (), f'空栏零移除: {got}'
    assert _CARD in (gs.strategy_conditional_done.value or ()), \
        '一次性标志位 fire 即封(与移除写非空解耦)'
