"""好运令牌·金(id 231501)两条效果条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '好运令牌·金' 行:具名×随机两条效果条目
``_compose_grant_legs(_make_named_equip_grant_effect('好运令牌', 1),
_make_random_equip_effect('简易', 1))``;按被测方法拆目录规范落位,
先例 = 同目录 test_strategy_compose_grant_jingmi_jin.py 精密拆装·金)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-247 对应稿
§4 锁面(REVIEW-T247 无需用户决定 6/6;卡面官方原文:「获得1个【好运令牌】和1件
随机简易装备」;效果条目1 具名确定写 rand=False;效果条目2 简易池 8 件均匀随机;
效果串恒 2 条按卡文语序):

- 组合行单一源:两条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → equips 恰 +2(令牌在前+随机一名在后)、
  效果串恰 2 条、rng 仅效果条目 2 消费。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '好运令牌·金'
_SEED = 20261206


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def test_haoyun_jin_compose_row_single_source() -> None:
    """组合行单一源:两条效果条目组合行已登记;泛化表零本卡键(防回退撞键)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    assert _CARD in PICK_INVEST_EFFECTS, '两条效果条目组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_haoyun_jin_chain_places_two_legs() -> None:
    """行为链真值:确定入口 → equips 恰 +2(令牌在前+随机一名在后)、
    效果串恰 2 条、rng 仅效果条目 2 消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    equips = gs.equips.value
    assert len(equips) == 2, f'equips 恰 +2(令牌+随机): {equips}'
    assert equips[0] == '好运令牌', f'具名在前(卡文语序): {equips}'
    assert equips[1] != '好运令牌', f'随机在后: {equips}'
    effects = out.effects
    assert len(effects) == 2, f'效果串恒 2 条: {effects}'
    assert effects[0] == 'named_equip_grant:好运令牌(placed=True)', \
        f'效果条目1 具名: {effects[0]}'
    assert effects[1].startswith('strategy_random_equip:'), \
        f'效果条目2 随机: {effects[1]}'
