"""燃起来了(id 252801)含三条效果条目的卡零改动现值回归锁(镜像 src = kernel/
cw_investments.py 与绑定/估值面;按被测方法拆目录规范落位 mandate_v1/
镜像,同构对表基准 = test_strategy_yueguang_zero_modeling.py
月光宝盒七锁)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-276 对应稿
§4 七锁(REVIEW-T276 免裁 3/3;卡面官方原文:「【燃血角斗场】以80%上限
开始战斗，且保留的充能提高20%。获得【万敌】和【千冶·刃】。」——腿 A/B
实机(live)和模拟器(sim)两边盲零建模零登记;效果条目 C 授予/绑定/估值三面已登记零动作):

- 锁 1 授予形状:STRATEGY_GRANTS 条目逐字段(卡文语序/advisor False/
  零装备面);
- 锁 2 估值传导:gift_hit_tier = core,分数断言只引常量名;
- 锁 3 绑定面:显式绑定二元组对拍(阵营×角色,scope 只申报不锁死);
- 锁 4 规范名幂等;
- 锁 5 零建模现值回归:on_strategy_gained 返回空效果串 ∧ 世界容器零写
  (现值锁非终态锁,交付家族批落码组合行时随批修订翻转,设计稿 §4 已
  内嵌修订义务);
- 锁 6 反扫闭集:候选扫描在册 + 注册表在册双断言;
- 锁 7 经济面零条目:三表零命中(零建模申报的回归面,家族收口批落
  组合行时 PICK 部分随批翻转)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import gift_hit_tier
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _STRATEGY_BINDINGS_EXPLICIT,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
    _scan_strategy_grant_candidates,
    normalize_invest_name,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    GIFT_TIER_SCORE,
    grant_gift_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '燃起来了'


def test_ranqilai_grant_shape() -> None:
    """锁 1(授予形状):条目逐字段(卡文语序/advisor False/零装备面)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('万敌', '千冶·刃'), '卡文语序'
    assert grant.advisor is False, 'advisor False'
    assert grant.equips_immediate == (), '零装备面'


def test_ranqilai_gift_value_tier() -> None:
    """锁 2(估值传导):core 档,分数断言只引常量名(禁字面死值)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert gift_hit_tier(grant) == 'core', 'core 档'
    assert grant_gift_value(grant, frozenset()) == GIFT_TIER_SCORE['core'], \
        '分数 = 常量'


def test_ranqilai_binding_pair() -> None:
    """锁 3(绑定面):显式绑定二元组对拍(scope 只申报不锁死)。"""
    assert _CARD in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定在册'
    factions, chars = _STRATEGY_BINDINGS_EXPLICIT[_CARD]
    assert factions == frozenset({'燃血'}), '阵营侧'
    assert chars == frozenset({'万敌', '千冶·刃'}), '角色侧'


def test_ranqilai_name_normalize() -> None:
    """锁 4(规范名):normalize 幂等。"""
    assert normalize_invest_name(_CARD) == _CARD, '幂等'


def test_ranqilai_zero_modeling_on_gain() -> None:
    """锁 5(零建模现值回归):on_strategy_gained 返回空效果串且世界零写
    (现值锁非终态锁,交付家族批落码组合行时随批修订翻转)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=None)
    assert effects == (), f'零建模空效果串: {effects}'
    assert gs.write_seq == seq_before, '世界容器零写'


def test_ranqilai_scan_closed_set() -> None:
    """锁 6(反扫闭集):候选扫描在册 + 注册表在册双断言。"""
    assert _CARD in _scan_strategy_grant_candidates(), '候选扫描在册'
    assert _CARD in STRATEGY_GRANTS, '注册表在册'


def test_ranqilai_zero_modeling_registries() -> None:
    """锁 7(经济面零条目):三表零命中(零建模申报的回归面)。"""
    assert _CARD not in STRATEGY_ECONOMY, 'ECONOMY 零命中'
    assert _CARD not in STRATEGY_EFFECTS, 'EFFECTS 零命中'
    assert _CARD not in PICK_INVEST_EFFECTS, 'PICK 零命中'
