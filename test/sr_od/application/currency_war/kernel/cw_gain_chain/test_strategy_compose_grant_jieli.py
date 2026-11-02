"""借力打力(id 252601)char×char 双角色组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '借力打力' 行:
``_compose_grant_legs(_make_char_grant_effect('黑塔'),
_make_char_grant_effect('缇宝'))``;先例 = 同目录
test_strategy_compose_grant_shuangrenwu.py 双人舞双腿形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-274 对应稿
§4 锁面(REVIEW-T274 免裁 6/6;卡面官方原文:「敌方目标被消灭后，【借力球】
的伤害分摊比例永久提高0.15%。获得【黑塔】和【缇宝】。」——条件段借力球
参数敌方侧召唤物域游戏侧自算 bot 零建模;腿序 = 卡文语序,效果串 2 条):

- 组合行单一源:双腿组合行在册(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → 恰两角色入栏(黑塔/缇宝卡文序)、效果串恰 2 条
  char_grant、rng 零消费。
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

_CARD = '借力打力'
_SEED = 20261211


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


def test_jieli_compose_row_single_source() -> None:
    """组合行单一源:双腿组合行在册;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行在册'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_jieli_chain_places_two_chars() -> None:
    """行为链真值:确定入口 → 恰两角色入栏(卡文序)、效果串恰 2 条、
    rng 零消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'效果串恰 2 条: {effects}'
    assert effects == ('char_grant:黑塔(placed=True,merge=0)',
                       'char_grant:缇宝(placed=True,merge=0)'), \
        f'双腿步串卡文序: {effects}'
    names = [s.unit.char_id for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert names == ['黑塔', '缇宝'], f'恰两角色入栏(卡文序): {names}'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写一行'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
