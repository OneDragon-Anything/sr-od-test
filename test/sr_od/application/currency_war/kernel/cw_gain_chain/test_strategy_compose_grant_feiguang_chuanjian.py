"""飞光·传剑(id 352702)双具名组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '飞光·传剑' 行:
``_compose_grant_legs(_make_char_grant_effect('彦卿'),
_make_char_grant_effect('景元'))``;char×char 组合行,按被测方法拆目录
规范落位,先例 = 同目录 test_strategy_compose_grant_yingyue.py 姊妹形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-411-feiguang-
chuanjian.md §4 锁 1/2/3(卡面官方原文:「获得【彦卿】和【景元】，他们获得
【师徒】羁绊。【彦卿】的【天河泻】获得强化，造成战斗中【仙舟】神君和
【景元】累计伤害值15%的伤害。两人同时在场上时，每进入一个新节点该值
提高4%。」——师徒羁绊非注册羁绊零建模;天河泻强化/共场叠层两条效果条目具名单位
战斗内技能数值面零建模;策略线分亲和面现役载体 = cw_invest_channels.
DEFINING_CARDS 定义卡点名登记,已由 test_cw_invest_channels.py 锁定,
本文件不重复):

- 登记面直测:GRANTS 条目 chars_immediate = 卡文语序 (彦卿, 景元) 且
  advisor=False(设计稿 §4 锁 1);绑定行 (仙舟域, {彦卿, 景元}) 用户
  确认语义冻结(§4 锁 2);组合行已登记,泛化表零本卡键(防回退撞键)。
- 行为链真值(§4 锁 3):确定入口 → 恰两角色入栏(彦卿/景元卡文序,
  1★ 先验家族口径)、效果串 2 条 char_grant、rng 零消费。
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
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BINDINGS,
    STRATEGY_GRANTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '飞光·传剑'
_SEED = 20261208


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


def test_feiguang_chuanjian_grant_and_binding_registry() -> None:
    """登记面直测:GRANTS 条目 chars_immediate = 卡文语序 (彦卿, 景元)
    且 advisor=False(非顾问分道);绑定行 (仙舟域, {彦卿, 景元})(用户
    确认语义冻结);组合行已登记,泛化表零本卡键(撞键形态禁回退)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('彦卿', '景元'), '卡文语序直读'
    assert grant.advisor is False, '非顾问分道'
    assert STRATEGY_BINDINGS[_CARD] == (
        frozenset({'仙舟'}), frozenset({'彦卿', '景元'})), \
        '绑定行(用户确认语义冻结)'
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_feiguang_chuanjian_chain_places_two_chars() -> None:
    """行为链真值:确定入口 → 恰两角色入栏(卡文序 彦卿→景元,1★ 先验)、
    效果串 2 条 char_grant、确定面写、rng 零消费(具名确定发放零采样面)。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert len(effects) == 2, f'效果串 2 条(两条效果条目): {effects}'
    assert effects == ('char_grant:彦卿(placed=True,merge=0,uid=1)',
                       'char_grant:景元(placed=True,merge=0,uid=2)'), \
        f'条目序 = 卡文语序彦卿→景元: {effects}'
    slots = [s for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert [s.unit.char_id for s in slots] == ['彦卿', '景元'], \
        f'恰两角色入栏(卡文序): {slots}'
    assert [s.unit.star for s in slots] == [1, 1], '1★ 先验家族口径'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
