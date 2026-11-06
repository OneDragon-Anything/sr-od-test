"""五百强(id 203001)双具名组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '五百强' 行:双具名组合
``_compose_grant_legs(_make_named_equip_grant_effect('折叠小刀', 1),
_make_named_equip_grant_effect('和平手枪', 1))``;按被测方法拆目录
规范落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 =
同目录 test_strategy_random_equip_grant_kongcang.py 空仓)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-196 对应稿
§4(REVIEW-T196 无需用户决定 7/7;卡面官方原文:「首次有我方队员在战斗中达到500
前台或后台强度时，获得30金币。立即获得【折叠小刀】、【和平手枪】。」):

- 登记单一源:双具名组合行(折叠小刀×1 先/和平手枪×1 后,依卡文语序;
  条件金腿零建模归属型③不发放,不入泛化随机表);
- 行为链真值(锁 2):gain_invest_strategy 确定入口 → equips 恰两件按
  卡文语序、效果串两条具名族形态;零随机面(具名腿无采样,rng 不消费)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
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

_CARD = '五百强'
_SEED = 20261104


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


def test_wuqiang_registry_row_single_source() -> None:
    """登记单一源:组合行已登记(双具名);泛化随机表零条目(非随机族);
    id 对拍 plaza:203001。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        _STRATEGY_RANDOM_EQUIP_GRANTS,
        PICK_INVEST_EFFECTS,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
    )
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, '双具名非随机族'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:203001', \
        '注册行 id 对拍'


def test_wuqiang_chain_places_two_named_in_order() -> None:
    """行为链真值(锁 2):确定入口 → equips 恰两件按卡文语序(折叠小刀
    先/和平手枪后)、效果串两条具名族形态、零随机面。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == ['折叠小刀', '和平手枪'], \
        f'两件具名按卡文语序: {gs.equips.value}'
    assert len(out.effects) == 2, f'效果串两条: {out.effects}'
    assert all('named' in e or 'equip' in e for e in out.effects), \
        f'具名族形态: {out.effects}'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
