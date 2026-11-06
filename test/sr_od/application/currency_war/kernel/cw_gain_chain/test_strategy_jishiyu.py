"""及时雨(id 300701)随机星档×装备授予组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '及时雨' 行:
``_compose_grant_legs(_make_random_star_char_effect(4, 2, count=3),
_make_named_equip_grant_effect('完美投影仪', 1))``;count=3 = 工厂 count
缺省参扩展首例多连发消费;先例 = 同目录 test_strategy_tianguang.py
天降救兵形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-300 对应稿
(REVIEW-T300 免裁 6/6;卡面官方原文:「获得3个随机2星4费角色和1个
【完美投影仪】，获得4次免费刷新。」——效果条目1 随机 2星4费×3 / 效果条目2 完美
投影仪装备入栏[完美投影仪 ∈ EQUIPMENTS 工具类,非占席道具,规模效应
装备授予先例同款] / 效果条目3 免费刷新在 ECONOMY burst 注册行零动作):

- 组合行单一源:两条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:恰三随机角色(2 星)入席+完美投影仪装备入栏、效果串
  恰 4 条(3 随机@2star+1 装备授予)、rng 恰消费。
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

_CARD = '及时雨'
_SEED = 20261216


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


def test_jishiyu_compose_row_single_source() -> None:
    """组合行单一源:两条效果条目组合行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_jishiyu_chain_places_three_chars_and_equip() -> None:
    """行为链真值:恰三随机角色(2 星)入席+完美投影仪装备入栏、效果串
    恰 4 条(3 随机@2star+1 装备授予)、rng 恰消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 4, f'效果串恰 4 条: {effects}'
    assert sum(1 for e in effects
               if e.startswith('strategy_gift_random:')) == 3, \
        f'三随机角色腿: {effects}'
    assert all(e.endswith('@2star') for e in effects[:3]), \
        f'2 星档: {effects}'
    assert '完美投影仪' in effects[3], f'装备授予腿: {effects}'
    units = [s.unit for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert len(units) == 3 and all(u.star == 2 for u in units), \
        f'恰三随机角色 2 星入席: {units}'
    assert '完美投影仪' in gs.equips.value, \
        f'装备入栏(完美投影仪 ∈ EQUIPMENTS 工具类,规模效应先例同款): ' \
        f'{gs.equips.value}'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() != rng_state0, '随机面(rng 恰消费)'
