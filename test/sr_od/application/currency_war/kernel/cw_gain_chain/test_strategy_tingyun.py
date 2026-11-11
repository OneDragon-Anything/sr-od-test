"""停云顾问(id 260501)具名装备授予单行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '停云顾问' 行:
``_make_named_equip_grant_effect('光能电池', 1)``;同形模板 = 加拉赫
顾问;按被测方法拆目录规范落位,先例 = 同目录 test_strategy_jialahe.py
加拉赫顾问形)。

测试面依据 = 设计稿(原件已退役)T-290 对应稿
§4 锁面(已退役评审稿 无需用户决定 5/5;卡面官方原文:「获得专家顾问【停云】，
并使其在本局游戏中加入商店。获得【光能电池】和4金币。」——顾问效果条目/金币效果条目
已登记零动作,本卡唯一机制件 = 光能电池具名授予效果条目):

- 行单一源:具名授予行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 顾问解锁+光能电池入栏、效果串恰 2 条
  (advisor_unlock+named_equip_grant)、rng 零消费。
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
    ChannelSig,
    GameState,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '停云顾问'
_SEED = 20261214


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def test_tingyun_row_single_source() -> None:
    """行单一源:具名授予行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_tingyun_chain_places_battery() -> None:
    """行为链真值:确定入口 → 顾问解锁+光能电池入栏、效果串恰 2 条、
    rng 零消费。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'顾问卡全链效果串(解锁+授予): {effects}'
    assert effects == ('advisor_unlock:停云顾问:停云',
                       'named_equip_grant:光能电池(placed=True)'), \
        f'全链步串: {effects}'
    assert '光能电池' in gs.equips.value, '装备入栏'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
