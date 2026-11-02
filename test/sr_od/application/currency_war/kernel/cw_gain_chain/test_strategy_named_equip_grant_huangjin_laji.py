"""黄金垃圾(id 231701)具名装备单腿直书登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '黄金垃圾' 行:
``_make_named_equip_grant_effect('金垃圾袋', 1)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_named_equip_grant_quanwuxing.py 全武行)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-249 对应稿
§4 锁面(REVIEW-T249 免裁 5/5;卡面官方原文:「获得一个【金垃圾袋】，它
提供大量属性和15金币。」——腿1 具名金垃圾袋确定发放;「大量属性和15金币」
= 装备携带形态战力面 + 金腿 STRATEGY_ECONOMY instant_gold=15 在册零改动):

- 行为链真值:确定入口 → equips 恰 +1 金垃圾袋、步串恰 1 条
  ``named_equip_grant:金垃圾袋(placed=True)``、零随机面。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
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

_CARD = '黄金垃圾'
_SEED = 20261207


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


def test_huangjin_laji_chain_places_bag() -> None:
    """行为链真值:on_strategy_gained 直构(rand=False)→ equips 恰 +1
    金垃圾袋、步串恰 1 条、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 1, f'效果串恰 1 条: {effects}'
    assert effects == ('named_equip_grant:金垃圾袋(placed=True)',), \
        f'单件步串: {effects}'
    assert gs.equips.value == ['金垃圾袋'], f'equips 恰 +1: {gs.equips.value}'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
