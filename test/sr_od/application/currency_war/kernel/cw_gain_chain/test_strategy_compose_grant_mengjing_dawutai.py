"""梦境大舞台(id 252301)单角色组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '梦境大舞台' 行:
``_compose_grant_legs(_make_char_grant_effect('花火'))``;单角色组合行,
按被测方法拆目录规范落位,先例 = 同目录
test_strategy_compose_grant_gangtie.py 钢铁美学单角色形)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 6
(卡面句③「获得【花火】」即时角色效果条目骑厂交付;句② 条件装备效果条目走
STRATEGY_BOND_TIER_GRANTS + 结算拍检查效果条目另表,两注册面分治——GRANTS
条目 equips_immediate 维持 (),条件发放禁误补即时字段):

- 组合行单一源:组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 恰一角色入栏(花火 1★)、效果串恰 1 条
  char_grant、equips 零写(本行只辖角色句)、rng 零消费;
- 词表隔离锁:'盛会之星星徽' ∉ BENCH_ITEM_NAMES(星徽系装备非占席,
  条件效果条目发放物不入占席道具词表)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_RANDOM_EQUIP_GRANTS,
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '梦境大舞台'
_SEED = 20261210


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


def test_mengjing_compose_row_single_source() -> None:
    """组合行单一源:单角色组合行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_mengjing_chain_places_huohi_only() -> None:
    """行为链真值:确定入口 → 恰一角色入栏(花火)、效果串恰 1 条
    char_grant、equips 零写(本行只辖句③角色句,条件装备效果条目不入效果
    体)、rng 零消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 1, f'效果串恰 1 条: {effects}'
    assert effects == ('char_grant:花火(placed=True,merge=0,uid=1)',), \
        f'一条效果条目步串: {effects}'
    names = [s.unit.char_id for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert names == ['花火'], f'恰一角色入栏: {names}'
    stars = [s.unit.star for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert stars == [1], f'1★ 先验家族口径: {stars}'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.equips.value == [], 'equips 应零写(装备效果条目另表)'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'


def test_badge_equip_not_bench_item() -> None:
    """词表隔离锁:'盛会之星星徽' ∉ BENCH_ITEM_NAMES(星徽系装备归
    equips 装备库存域;错入占席词表会让条件效果条目发放被误判占席道具)。"""
    assert '盛会之星星徽' not in BENCH_ITEM_NAMES, \
        '星徽发放物禁入占席道具词表'
