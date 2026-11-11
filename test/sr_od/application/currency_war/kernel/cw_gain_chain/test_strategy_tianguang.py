"""天降救兵(id 300501)随机星档×箱条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '天降救兵' 行:
``_compose_grant_legs(_make_random_star_char_effect(1, 3),
_make_box_grant_effect('简易武装箱'))``;roll star 参扩展首例消费;
按被测方法拆目录规范落位,先例 = 同目录
test_strategy_compose_grant_gangtie.py 钢铁美学形)。

测试面依据 = 原稿锁面
§4 锁面(原稿评审锁 无需用户决定 7/7;卡面官方原文:「获得一个随机3星1费角色，
获得1个【简易武装箱」。」——效果条目1 随机星档角色(双档卡面明写)/效果条目2 箱条目):

- 组合行单一源:两条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 恰一随机角色(3 星)入席+恰一箱入栏、效果串
  恰 2 条(strategy_gift_random@3star+box_grant)、rng 恰消费 1 次。
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

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '天降救兵'
_SEED = 20261215


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


def test_tianguang_compose_row_single_source() -> None:
    """组合行单一源:两条效果条目组合行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_tianguang_chain_places_random_char_and_box() -> None:
    """行为链真值:确定入口 → 恰一随机角色(3 星)入席+恰一箱入栏、
    效果串恰 2 条、rng 恰消费 1 次。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'效果串恰 2 条: {effects}'
    assert effects[0].startswith('strategy_gift_random:') \
        and effects[0].endswith('@3star'), f'随机 3 星角色效果条目: {effects}'
    assert effects[1].startswith('box_grant:简易武装箱'), \
        f'箱条目: {effects}'
    units = [s.unit for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert len(units) == 1 and units[0].star == 3, \
        f'恰一随机角色 3 星入席: {units}'
    box_slots = [sl for sl in gs.bench.value.slots
                 if sl.kind != 'unit' and sl.kind != 'empty'
                 and getattr(sl, 'item', None) == '简易武装箱']
    assert len(box_slots) == 1, f'箱占席道具槽恰一: {gs.bench.value}'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() != rng_state0, '随机面(rng 恰消费)'
