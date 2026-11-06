"""命运圣杯星徽(id 211401)装备×角色两条效果条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '命运圣杯星徽' 行:双具名交叉组合
``_compose_grant_legs(_make_named_equip_grant_effect('命运圣杯星徽', 1),
_make_char_grant_effect('远坂凛'))``;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_yezhi_grants.py 夜之半神星徽)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-219 对应稿
§4(REVIEW-T219 无需用户决定 6/6;卡面官方原文双具名直读;效果条目1 rand=False 策略
卡侧具名效果条目通道归属;效果条目2 远坂凛 1★ 先验家族口径,双套 need_star=1 旁证):

- 登记单一源:组合行已登记;泛化随机表零条目;
- 行为链真值:确定入口 → equips 恰 +1 徽、bench 恰 +1 远坂凛、
  效果串两条前缀分域、零随机面。
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

_CARD = '命运圣杯星徽'
_SEED = 20261116


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


def test_mingyun_registry_row_single_source() -> None:
    """登记单一源:组合行已登记;泛化随机表零条目;id 对拍 plaza:211401。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
    )
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, '双具名非随机族'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:211401', \
        '注册行 id 对拍'


def test_mingyun_chain_places_equip_and_char() -> None:
    """行为链真值:确定入口 → equips 恰 +1 徽、bench 恰 +1 远坂凛、
    效果串两条前缀分域、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == ['命运圣杯星徽'], f'equips 恰 +1: {gs.equips.value}'
    bench_units = [s.unit.char_id for s in gs.bench.value.slots
                   if s.kind == 'unit' and s.unit is not None]
    assert bench_units == ['远坂凛'], f'bench 恰 +1: {bench_units}'
    assert len(out.effects) == 2, f'效果串两条: {out.effects}'
    assert any(e.startswith('named_equip_grant:') for e in out.effects), \
        f'装备效果条目前缀: {out.effects}'
    assert any(e.startswith('char_grant:') for e in out.effects), \
        f'角色效果条目前缀: {out.effects}'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
