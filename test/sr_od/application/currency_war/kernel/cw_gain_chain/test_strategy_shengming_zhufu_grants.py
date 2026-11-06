"""生命之花祝福(id 230401)装备腿行为锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '生命之花祝福' 行:具名装备一条效果条目
``_make_named_equip_grant_effect('生命之花', 1)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_heping_zhufu_grants.py 和平手枪祝福)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-234 对应稿
§4 锁 3(REVIEW-T234 免裁 7/7;卡面官方原文「获得1个【生命之花】」;
rand=False 策略卡侧具名效果条目通道归属;祝福面 = UNIT_BUFF 零响应登记):

- 行为链真值:确定入口 → equips 恰 +1 生命之花、步串
  ``named_equip_grant:生命之花(placed=True)``、零随机面。
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

_CARD = '生命之花祝福'
_SEED = 20261201


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


def test_shengming_zhufu_chain_places_flower() -> None:
    """行为链真值(锁 3):on_strategy_gained 直构(rand=False)→ equips
    恰 +1 生命之花、步串逐件一条、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert effects == ('named_equip_grant:生命之花(placed=True)',), \
        f'单件步串: {effects}'
    assert gs.equips.value == ['生命之花'], f'equips 恰 +1: {gs.equips.value}'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '落位写 evidence'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
