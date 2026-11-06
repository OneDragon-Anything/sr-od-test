"""月光宝盒(id 252501)含三条效果条目的卡零改动现值回归锁(镜像 src = kernel/
cw_investments.py 与绑定/估值面;按被测方法拆目录规范落位 mandate_v1/
镜像,先例 = 同目录既有登记锁族)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-273 对应稿
§4 七锁(REVIEW-T273 无需用户决定 4/4;卡面官方原文:「完美通关时，夜之半神获得
的【月光精华】提高100%，领取夜之半神奖励时，也会获得一名夜之半神角色，
【月色】层数越高，越可能领取到高费角色。获得【赛飞儿】和【万敌】。」
——腿 A/B 型③零建模;腿 C 授予/绑定/估值三面已登记零动作):

- 锁 1 授予形状:STRATEGY_GRANTS 条目逐字段(卡文语序/advisor False/
  零装备面);
- 锁 2 估值传导:gift_hit_tier = core,分数断言只引常量名;
- 锁 3 绑定面:显式绑定二元组对拍(阵营×角色,scope 只申报不锁死);
- 锁 4 规范名幂等;
- 锁 5 零建模现值回归:on_strategy_gained 返回空效果串(现值锁非终态
  锁,交付家族批写进代码时随批修订退役);
- 锁 6 反扫闭集:候选扫描已登记;
- 锁 7 经济面零条目:三表零命中(零建模申报的回归面)。
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

_CARD = '月光宝盒'


def test_yueguang_grant_shape() -> None:
    """锁 1(授予形状):条目逐字段(卡文语序/advisor False/零装备面)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('赛飞儿', '万敌'), '卡文语序'
    assert grant.advisor is False, 'advisor False'
    assert grant.equips_immediate == (), '零装备面'


def test_yueguang_gift_value_tier() -> None:
    """锁 2(估值传导):core 档,分数断言只引常量名(禁字面死值)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert gift_hit_tier(grant) == 'core', 'core 档'
    assert grant_gift_value(grant, frozenset()) == GIFT_TIER_SCORE['core'], \
        '分数 = 常量'


def test_yueguang_binding_pair() -> None:
    """锁 3(绑定面):显式绑定二元组对拍(scope 只申报不锁死)。"""
    assert _CARD in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定已登记'
    factions, chars = _STRATEGY_BINDINGS_EXPLICIT[_CARD]
    assert factions == frozenset({'夜之半神'}), '阵营侧'
    assert chars == frozenset({'赛飞儿', '万敌'}), '角色侧'


def test_yueguang_name_normalize() -> None:
    """锁 4(规范名):normalize 幂等。"""
    assert normalize_invest_name(_CARD) == _CARD, '幂等'


def test_yueguang_zero_modeling_on_gain() -> None:
    """锁 5(零建模现值回归):on_strategy_gained 返回空效果串且世界零写
    (现值锁非终态锁,交付家族批写进代码时随批修订退役)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG,
                                 rng=None)
    assert effects == (), f'零建模空效果串: {effects}'
    assert gs.write_seq == seq_before, '世界容器零写'


def test_yueguang_scan_closed_set() -> None:
    """锁 6(反扫闭集):候选扫描已登记 + 注册表已登记双断言。"""
    assert _CARD in _scan_strategy_grant_candidates(), '候选扫描已登记'
    assert _CARD in STRATEGY_GRANTS, '注册表已登记'


def test_yueguang_zero_modeling_registries() -> None:
    """锁 7(经济面零条目):三表零命中(零建模申报的回归面)。"""
    assert _CARD not in STRATEGY_ECONOMY, 'ECONOMY 零命中'
    assert _CARD not in STRATEGY_EFFECTS, 'EFFECTS 零命中'
    assert _CARD not in PICK_INVEST_EFFECTS, 'PICK 零命中'
