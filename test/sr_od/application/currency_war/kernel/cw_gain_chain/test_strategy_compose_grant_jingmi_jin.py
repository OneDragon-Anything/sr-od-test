"""精密拆装·金(id 231401)三条效果条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '精密拆装·金' 行:三条效果条目组合
``_compose_grant_legs(_make_named_equip_grant_effect('精密拆装扳手', 1),
_make_named_equip_grant_effect('冶金炉', 1),
_make_random_equip_effect('简易', 2))``;按被测方法拆目录规范落位,
先例 = 同目录 test_strategy_compose_grant_huishou.py 回收计划两条效果条目)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-246 对应稿
§4 锁面(REVIEW-T246 免裁 8/8;卡面官方原文:「获得1个【精密拆装扳手】，
1个【冶金炉】和2个随机简易武装」;效果条目1/效果条目2 具名确定写 rand=False;效果条目3
随机简易×2 放回抽 T-167 判例恰 2 次掷,效果串恒 4 条按卡文语序):

- 组合行单一源:三条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → equips 恰 +3(扳手/炉确定写在前、随机两名在后)、
  效果串恰 4 条(2 具名+2 随机)、rng 仅效果条目 3 消费。
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

_CARD = '精密拆装·金'
_SEED = 20261205


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


def test_jingmi_jin_compose_row_single_source() -> None:
    """组合行单一源:三条效果条目组合行已登记;泛化表零本卡键(防回退撞键)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    assert _CARD in PICK_INVEST_EFFECTS, '三条效果条目组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_jingmi_jin_chain_places_three_legs() -> None:
    """行为链真值:确定入口 → equips 恰 +3(扳手/炉在前+随机两名在后)、
    效果串恰 4 条(2 具名+2 随机)、rng 仅效果条目 3 消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    equips = gs.equips.value
    assert len(equips) == 4, f'equips 恰 +4(1 扳手+1 炉+2 随机): {equips}'
    assert equips[0] == '精密拆装扳手' and equips[1] == '冶金炉', \
        f'具名两件在前(卡文语序): {equips}'
    assert equips[2] not in ('精密拆装扳手', '冶金炉') and \
        equips[3] not in ('精密拆装扳手', '冶金炉'), \
        f'随机两名在后: {equips}'
    effects = out.effects
    assert len(effects) == 4, f'效果串恒 4 条: {effects}'
    assert effects[0] == 'named_equip_grant:精密拆装扳手(placed=True)', \
        f'效果条目1 具名: {effects[0]}'
    assert effects[1] == 'named_equip_grant:冶金炉(placed=True)', \
        f'效果条目2 具名: {effects[1]}'
    assert all(effects[i].startswith('strategy_random_equip:')
               for i in (2, 3)), f'效果条目3 随机两条: {effects[2:]}'
