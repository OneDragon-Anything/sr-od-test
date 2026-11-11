"""量子力学(id 252901)单角色组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '量子力学' 行:
``_compose_grant_legs(_make_char_grant_effect('希儿'))``;希儿同物组合行
第三例[钢铁美学/量子同频星徽后],先例 = 同目录
test_strategy_compose_grant_gangtie.py 钢铁美学一条效果条目形)。

测试面依据 = 设计稿(原件已退役)T-277 对应稿
§4 锁面(已退役评审稿 无需用户决定 7/7;卡面官方原文:「【量子同频】角色累计星数达
3/6/9时，额外获得1/2/3层【同频】。获得【希儿】。」——条件段【量子同频
星数档位】游戏侧自算 bot 零建模;效果串 1 条):

- 组合行单一源:单角色组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 恰一角色入栏(希儿)、效果串恰 1 条 char_grant、
  rng 零消费。
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

_CARD = '量子力学'
_SEED = 20261212


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


def test_liangzi_compose_row_single_source() -> None:
    """组合行单一源:单角色组合行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_liangzi_chain_places_one_char() -> None:
    """行为链真值:确定入口 → 恰一角色入栏(希儿)、效果串恰 1 条、
    rng 零消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 1, f'效果串恰 1 条: {effects}'
    assert effects == ('char_grant:希儿(placed=True,merge=0,uid=1)',), \
        f'一条效果条目步串: {effects}'
    names = [s.unit.char_id for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert names == ['希儿'], f'恰一角色入栏: {names}'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
