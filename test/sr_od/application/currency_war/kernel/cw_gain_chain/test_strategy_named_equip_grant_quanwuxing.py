"""全武行(id 231001)具名装备一条效果条目直书登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '全武行' 行:
``_make_named_equip_grant_effect('武器大师', 1)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_named_equip_grant_wushang_tongguan.py 无伤通关)。

测试面依据 = 设计稿(原件已退役)T-242 对应稿
§4 锁 1 修正形(已退役评审稿 无需用户决定 6/6;卡面官方原文「获得1个【武器大师】」;
效果条目2「额外提供5%×3」= 零建模 + 判读申报制,装备携带形态族口径):

- 行为链真值:确定入口 → equips 恰 +1 武器大师、步串恰 1 条
  ``named_equip_grant:武器大师(placed=True)``、零随机面。
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

_CARD = '全武行'
_SEED = 20261204


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


def test_quanwuxing_chain_places_weapon_master() -> None:
    """行为链真值(锁 1):on_strategy_gained 直构(rand=False)→ equips
    恰 +1 武器大师、步串恰 1 条、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 1, f'效果串恰 1 条: {effects}'
    assert effects == ('named_equip_grant:武器大师(placed=True)',), \
        f'单件步串: {effects}'
    assert gs.equips.value == ['武器大师'], f'equips 恰 +1: {gs.equips.value}'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
