"""欢愉星徽(id 203701)装备×角色两条效果条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '欢愉星徽' 行:双具名交叉组合
``_compose_grant_legs(_make_named_equip_grant_effect('欢愉星徽', 1),
_make_char_grant_effect('绯英'))``;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_wuqiang_grants.py 五百强)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-204 对应稿
§4(REVIEW-T204 免裁 10/10;卡面官方原文:「获得1个【欢愉星徽】，和1个
【绯英】。」;反转①徽腿 rand=False〔策略卡侧具名效果条目通道归属,fields.md
§3.2.15 族级分野注记〕;反转②组合登记行准展开卡形态):

- 登记单一源:两条效果条目组合行(欢愉星徽×1 先/绯英后,依卡文语序);泛化
  随机表零条目(双具名非随机族);
- 行为链真值(锁 2):确定入口 → equips 恰 +1 星徽、bench 恰 +1 绯英、
  效果串两条(named_equip_grant:/char_grant: 前缀分域)、零随机面。
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

_CARD = '欢愉星徽'
_SEED = 20261106


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


def test_huanyu_registry_row_single_source() -> None:
    """登记单一源:组合行在册(装备×角色两条效果条目);泛化随机表零条目;
    id 对拍 plaza:203701。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
    )
    assert _CARD in PICK_INVEST_EFFECTS, '组合行在册'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, '双具名非随机族'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:203701', \
        '注册行 id 对拍'


def test_huanyu_chain_places_equip_and_char() -> None:
    """行为链真值(锁 2):确定入口 → equips 恰 +1 星徽、bench 恰 +1
    绯英、效果串两条前缀分域、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == ['欢愉星徽'], f'equips 恰 +1: {gs.equips.value}'
    bench_units = [s.unit.char_id for s in gs.bench.value.slots
                   if s.kind == 'unit' and s.unit is not None]
    assert bench_units == ['绯英'], f'bench 恰 +1 绯英: {bench_units}'
    assert len(out.effects) == 2, f'效果串两条: {out.effects}'
    assert any(e.startswith('named_equip_grant:') for e in out.effects), \
        f'装备腿前缀: {out.effects}'
    assert any(e.startswith('char_grant:') for e in out.effects), \
        f'角色腿前缀: {out.effects}'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
