"""飞光·映月(id 352701)拿卡拍三条效果条目组合登记行锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '飞光·映月' 行:
``_compose_grant_legs(_make_yingyue_tier_init_leg(),
_make_char_grant_effect('镜流'), _make_char_grant_effect('景元'))``;
tier 效果条目 + char×char 组合行,按被测方法拆目录规范落位,先例 = 同目录
test_strategy_compose_grant_shuangrenwu.py 双人舞形)。

测试面依据 = 原稿锁面 §4 锁 3(卡面官方原文:「获得【镜流】和特殊的1费【景元】，
他们获得【师徒】羁绊。【镜流】2星时，【景元】变为3费。【镜流】3星时，
【景元】变为你认识的5费【景元】。」——师徒羁绊非注册羁绊零建模;效果条目1
费用档初始写 1 = 特殊景元起始档,前置于发放类效果条目防发放级联覆盖,条目序理由
见 _make_yingyue_tier_init_leg docstring):

- 组合行单一源:三条效果条目组合行已登记(泛化表零本卡键负断言防回退撞键);
- 行为链真值:确定入口 → tier=1 先写(拿卡拍)、恰两角色入栏(镜流/
  景元卡文序)、效果串 3 条(tier 串 + 双 char_grant)、rng 零消费。
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

_CARD = '飞光·映月'
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


def test_yingyue_compose_row_single_source() -> None:
    """组合行单一源:三条效果条目组合行已登记;泛化表零本卡键(防回退撞键)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'


def test_yingyue_chain_writes_tier_and_places_two_chars() -> None:
    """行为链真值:确定入口 → tier=1 先写(拿卡拍,先于发放)、恰两角色
    入栏(卡文序 镜流→景元)、效果串 3 条、rng 零消费。"""
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    assert gs.yingyue_cost_tier.value is None, '前置:未拿卡 None'
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=rng0)
    assert gs.yingyue_cost_tier.value == 1, \
        '拿卡拍费用档初始写 1(特殊景元起始档)'
    assert len(effects) == 3, f'效果串 3 条(tier+两条效果条目): {effects}'
    assert effects == ('pick_invest_yingyue_tier',
                       'char_grant:镜流(placed=True,merge=0,uid=1)',
                       'char_grant:景元(placed=True,merge=0,uid=2)'), \
        f'条目序 = tier 先写 + 卡文语序: {effects}'
    names = [s.unit.char_id for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit]
    assert names == ['镜流', '景元'], f'恰两角色入栏(卡文序): {names}'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.write_seq > seq_before, '落位写'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'


def test_yingyue_grant_triggers_merge_star_tier_3() -> None:
    """发放触发合成级联(场上存量 2×镜流 + 发放镜流凑三 2★)→ 升星拍经
    合并升星入口写档 3:拿卡拍先落 1、升星拍随后单调推进(条目序防覆盖)。"""
    gs = _make_gs(bench=[('镜流', 1), ('镜流', 1)], equips=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=random.Random(_SEED))
    assert gs.yingyue_cost_tier.value == 3, \
        f'镜流 2★ 合成事件 → 档 3(拿卡拍 1 不覆盖升星拍): {effects}'
    stars = [s.unit.star for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit and s.unit.char_id == '镜流']
    assert 2 in stars, f'合成产物 2★ 镜流在席: {stars}'
