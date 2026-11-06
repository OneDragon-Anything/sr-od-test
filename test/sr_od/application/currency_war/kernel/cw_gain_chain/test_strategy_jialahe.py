"""加拉赫顾问(id 260301)具名装备授予单行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '加拉赫顾问' 行:
``_make_named_equip_grant_effect('生命之花', 1)``;同物同形先例 = 无伤
通关(:1198);按被测方法拆目录规范落位,先例 = 同目录
test_strategy_compose_grant_gangtie.py 钢铁美学形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-288 对应稿
§4 锁面(REVIEW-T288 无需用户决定 7/7;卡面官方原文:「获得专家顾问【加拉赫】，
并使其在本局游戏中加入商店。获得【生命之花】和4金币。」——顾问腿/金腿
已登记零动作,本卡唯一机制件 = 生命之花具名授予腿):

- 组合行单一源:具名授予行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 恰一装备入栏(生命之花)、顾问解锁+生命之花入栏、效果串恰 2 条
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

_CARD = '加拉赫顾问'
_SEED = 20261213


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def test_jialahe_row_single_source() -> None:
    """行单一源:具名授予行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_jialahe_chain_places_flower() -> None:
    """行为链真值:确定入口 → 恰一装备入栏(生命之花)、效果串恰 1 条、
    rng 零消费。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'顾问卡全链效果串(解锁+授予): {effects}'
    assert effects == ('advisor_unlock:加拉赫顾问:加拉赫',
                       'named_equip_grant:生命之花(placed=True)'), \
        f'全链步串: {effects}'
    assert '生命之花' in gs.equips.value, '装备入栏'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
