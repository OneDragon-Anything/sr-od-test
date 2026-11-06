"""广聚天下英才(id 203601)全员发放锁(镜像 src = kernel/
cw_gain_effects.py PICK_INVEST_EFFECTS '广聚天下英才' 行:全员同费档
效果体工厂 ``_make_all_cost_chars_effect(2)``;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_random_equip_grant_kongcang.py 空仓)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-203 对应稿
§4(REVIEW-T203 免裁 8/8;卡面官方原文:「获得所有2费角色各一个。」):

- 行为链真值:确定入口 → equips/席按池逐名入席、效果串恒 Σ池数条
  (发放事实与落位成败解耦)、零随机面(rng 不消费);
- 披露键三键在册(池含专家/星级先验 1/溢出截断)。
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

_CARD = '广聚天下英才'
_SEED = 20261105


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


def test_all_chars_pool_keys_registered() -> None:
    """披露键三键在册(池含专家/星级先验/溢出截断;家族形 = 全元组精确
    比对,随批扩员同形)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_ALL_CHARS_ASSUMPTION_KEYS,
    )
    assert STRATEGY_ALL_CHARS_ASSUMPTION_KEYS == (
        'strategy_all_chars_pool_includes_expert',
        'strategy_all_chars_star_prior_1',
        'strategy_all_chars_overflow_truncation',
    ), '披露键三键漂移'


def test_all_chars_chain_places_pool_and_zero_rng() -> None:
    """行为链真值:确定入口 → 全池逐名入席(bench 写)、效果串恒 Σ池数
    条、零随机面(rng 不消费);session=None 直构形态(只登记不写状态的实现分支被闸跳过,
    登记形态断言由键集闭集锁承载)。"""
    from sr_od.application.currency_war.data.cw_chars import chars_by_cost
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    pool = [ch.name for ch in chars_by_cost(2)]
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    bench_units = [s.unit.char_id for s in gs.bench.value.slots
                   if s.kind == 'unit' and s.unit is not None]
    assert bench_units == pool[:9], \
        f'入席 = 池前 9 名(席容量截断沿链现役,溢出零写): {bench_units}'
    assert len(pool) == 15, f'前置:2 费池 15 名(含专家): {len(pool)}'
    assert len(out.effects) == len(pool), \
        f'效果串恒 Σ池数条: {len(out.effects)} vs {len(pool)}'
    assert all(e.startswith('all_cost_chars:') for e in out.effects), \
        f'效果串前缀: {out.effects[:3]}'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
    assert _CARD in PICK_INVEST_EFFECTS, '注册行在册(效果体引用存活)'
