"""幸运星祝福(id 230101)装备效果条目行为锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '幸运星祝福' 行:具名装备一条效果条目
``_make_named_equip_grant_effect('幸运星', 1)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,直接模板 =
test_strategy_named_equip_grant_wushang_tongguan.py 无伤通关)。

测试面依据 = 原稿锁面
§4 锁 3(原稿评审锁 无需用户决定 7/7;卡面官方原文「获得1个【幸运星】」;rand=False
策略卡侧具名效果条目通道归属;祝福面 = UNIT_BUFF 零响应登记,不在行为链):

- 行为链真值:确定入口 → equips 恰 +1 幸运星、步串
  ``named_equip_grant:幸运星(placed=True)``、落位写 evidence
  ``pick_invest_named_equip#equip``、零随机面。
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

_CARD = '幸运星祝福'
_SEED = 20261128


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


def test_xingyun_zhufu_chain_places_lucky_star() -> None:
    """行为链真值(锁 3):on_strategy_gained 直构(rand=False)→ equips
    恰 +1 幸运星、步串逐件一条、落位写 evidence、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert effects == ('named_equip_grant:幸运星(placed=True)',), \
        f'单件步串: {effects}'
    assert gs.equips.value == ['幸运星'], f'equips 恰 +1: {gs.equips.value}'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '落位写 evidence(效果体 evidence + #equip 后缀)'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
