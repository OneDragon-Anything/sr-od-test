"""量产型装甲祝福(id 230501)装备腿行为锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '量产型装甲祝福' 行:具名装备单腿
``_make_named_equip_grant_effect('量产型装甲', 1)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_shengming_zhufu_grants.py 生命之花祝福)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-235 对应稿
§4 锁 3(REVIEW-T235 免裁 7/7;卡面官方原文「获得1个【量产型装甲】」;
rand=False 策略卡侧具名腿通道归属;祝福面 = UNIT_BUFF 零响应登记):

- 行为链真值:确定入口 → equips 恰 +1 量产型装甲、步串
  ``named_equip_grant:量产型装甲(placed=True)``、零随机面。
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

_CARD = '量产型装甲祝福'
_SEED = 20261202


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


def test_liangchan_zhufu_chain_places_armor() -> None:
    """行为链真值(锁 3):on_strategy_gained 直构(rand=False)→ equips
    恰 +1 量产型装甲、步串逐件一条、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert effects == ('named_equip_grant:量产型装甲(placed=True)',), \
        f'单件步串: {effects}'
    assert gs.equips.value == ['量产型装甲'], f'equips 恰 +1: {gs.equips.value}'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '落位写 evidence'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
