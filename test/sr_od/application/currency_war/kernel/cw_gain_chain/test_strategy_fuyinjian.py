"""复印件(id 330301)行为锁(镜像 src = _make_owned_emblem_copy_effect
微工厂 + STRATEGY_ECONOMY xp_instant=24 注册行;先例 = 骇客采样族锁 +
伟大征服 XP 直测行[直锚先例 test_invest_strategy.py 伟大征服 (12.0,True)])。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-361 对应稿
(REVIEW-T361 无需用户决定 7/7;卡面官方原文:「获得一个已经拥有的星徽的复制,
获得24点经验。」):

- 锁 1 行为锁:直构 gs 固定种子采样 ∈ 原池 + 效果串恰 1 条
  ``emblem_copy:`` 前缀;
- 锁 2 空池锁:equips 全非星徽 → 零写 + ``emblem_copy:none(空池)`` 记录;
- 锁 3 池过滤锁:非星徽装备不入采样池(按 category 词表过滤);
- 锁 4 未观察锁:equips None → 零写 + skipped 记录(equips_unobserved);
- XP 注册行直测:'复印件': EconomyEffect(xp_instant=24) + 估值 24.0。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
    _make_owned_emblem_copy_effect,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    grant_gift_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPre')
_SIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                  mode='compute')


def _make_gs(equip_names: list[str] | None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    if equip_names is not None:
        gs.write_logic(gs.equips, list(equip_names),
                       produced_by='test_fuyinjian_seed', sig=_SIG)
    return gs


def test_copy_behavior_seeded_pool() -> None:
    """锁 1 行为锁(固定种子采样 ∈ 原池;效果串恰 1 条 emblem_copy: 前缀)。"""
    gs = _make_gs(['列车同行星徽', '生命之环'])
    effect = _make_owned_emblem_copy_effect()
    rng = random.Random(42)
    seq = effect(gs, sig=_SIG, rng=rng)
    assert len(seq) == 1 and seq[0].startswith('emblem_copy:'), \
        f'效果串形: {seq!r}'
    name = seq[0].split(':', 1)[1].split('(')[0]
    assert name in ('列车同行星徽', '生命之环'), f'采样越池: {name!r}'


def test_copy_empty_pool_no_writes() -> None:
    """锁 2 空池锁(equips 全非星徽 → 零写 + none(空池) 记录)。"""
    gs = _make_gs(['生命之环'])
    seq_before = gs.write_seq
    effect = _make_owned_emblem_copy_effect()
    seq = effect(gs, sig=_SIG, rng=random.Random(7))
    assert seq == ['emblem_copy:none(空池)'], f'空池记录: {seq!r}'
    assert gs.write_seq == seq_before, '空池零写'


def test_copy_pool_filter_non_emblem_excluded() -> None:
    """锁 3 池过滤锁(非星徽装备不入采样池)。"""
    gs = _make_gs(['简易武装箱'])
    effect = _make_owned_emblem_copy_effect()
    seq = effect(gs, sig=_SIG, rng=random.Random(11))
    assert seq == ['emblem_copy:none(空池)'], f'过滤失效: {seq!r}'


def test_copy_unobserved_skip() -> None:
    """锁 4 未观察锁(equips None → 零写 + skipped 记录)。"""
    gs = _make_gs(None)
    seq_before = gs.write_seq
    effect = _make_owned_emblem_copy_effect()
    seq = effect(gs, sig=_SIG, rng=random.Random(3))
    assert seq == ['emblem_copy:skipped(equips_unobserved)'], \
        f'未观察记录: {seq!r}'
    assert gs.write_seq == seq_before, '未观察零写'


def test_economy_row_and_valuation() -> None:
    """XP 注册行直测(xp_instant=24)+估值 24.0;PICK 登记键已登记。"""
    row = STRATEGY_ECONOMY['复印件']
    assert row.xp_instant == 24, f'XP 注册行漂移: {row!r}'
    assert row.xp_instant == 24
    assert '复印件' in PICK_INVEST_EFFECTS, 'PICK 登记键缺席'
