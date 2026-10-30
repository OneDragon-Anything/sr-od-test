"""武装支援(id 102501)组合双腿锁(镜像 src = kernel/cw_gain_effects.py 的
组合子 ``_compose_grant_legs`` + ``PICK_INVEST_EFFECTS`` 组合登记行;按被测
方法拆目录规范落位——test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,
先例 = 同目录既有镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-116-wuzhuang-zhiyuan.md(定稿)§4 锁 1 + REVIEW-T116 六裁决点默认案:
- 组合登记 = ``PICK_INVEST_EFFECTS['武装支援'] = _compose_grant_legs(
  _make_random_equip_effect(1), _make_reinforcement_effect(((3, 2),)))``
  (腿序 = 卡文语序装备腿先/角色腿后;腿参数登记行单次出现,单一源);
- 固定 rng 注入链发放真值:rng 消费序 3 抽 = 第 1 抽装备
  (``roll_random_simple_equip``)+ 第 2/3 抽角色
  (``roll_reinforcement_names`` 3 费池放回)——腿序改排即采样名漂移,
  被顺序断言捕获;效果串恰 3 条且顺序固定;
- 前提守卫:「效果串恒 3 条」前提 = 简易池 ∩ ``EQUIP_ACQUIRE_CONSEQUENCES``
  = ∅(设计 §1.2d/§4 锁 1 前提注记)——装备注册表扩员(新简易件带获得
  后果)时守卫先红,提示语义变化,勿盲改主锁断言数。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _RANDOM_SIMPLE_EQUIP_POOL,
    roll_random_simple_equip,
    roll_reinforcement_names,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    RandomCharSpec,
    random_char_pool,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 固定种子(角色 2 抽互异形态预验证值,失配 = 换种子)。
_COMPOSE_SEED = 20261031


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像 test_gain_chain._make_gs
    的 bench/equips 两支,本卡只涉这两域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像 test_gain_chain 同名 fixture,装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


def test_wuzhuang_zhiyuan_compose_legs_chain_in_order(
        rows_sink: _RowSink) -> None:
    """组合腿锁(设计 §4 锁 1):gain_invest_strategy 确定入口(rand=False)
    + 固定 rng 注入 → equips 恰 +1(名 ∈ 简易池派生集,禁手抄清单)、
    bench 恰 +2(名 ∈ 3 费载体派生集、均 1★;批内 2 只 < 3 零级联,
    级联仅与存量同名交互)、效果串恰 3 条且顺序 = [strategy_random_equip:
    <装备名>, strategy_gift_random:<角色名>@1star, strategy_gift_random:
    <角色名>@1star](顺序锁 = 多腿编排与 rng 消费序,本卡新增机制面);
    正常路径零申报行。"""
    # 预采样(独立 rng 实例按消费序 3 抽):与实际注入的 rng 同种子同序,
    # 腿序改排 = 采样名互换,顺序断言必红(改序 = 掷序漂移)。
    rng = random.Random(_COMPOSE_SEED)
    equip_pick = roll_random_simple_equip(rng)
    char_picks = roll_reinforcement_names(rng, 3, 2)
    # 前提守卫(设计 §4 锁 1 前提注记):破前提时装备获得后果链追加串,
    # 「效果串恒 3 条」失效——守卫先红,勿盲改断言数。
    assert set(_RANDOM_SIMPLE_EQUIP_POOL) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '简易池 ∩ 后果表须为空(效果串恒 3 条前提)'
    assert len(set(char_picks)) == 2, '预验证:本种子 2 抽互异(失配 = 换种子)'
    assert set(char_picks) <= set(random_char_pool(
        RandomCharSpec(cost=3, star=1))), '预验证:角色采样 ⊆ 3 费载体派生池'
    assert equip_pick in _RANDOM_SIMPLE_EQUIP_POOL, '预验证:装备采样 ∈ 简易池'

    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '武装支援', rand=False, sig=_LSIG,
                               rng=random.Random(_COMPOSE_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['武装支援'], '注册入表'
    assert gs.equips.value == [equip_pick], 'equips 恰 +1 且名 = 第 1 抽装备'
    units = sorted((u.char_id, u.star) for u in bench_units_of(gs))
    assert units == sorted((n, 1) for n in char_picks), 'bench 恰 +2 全 1★'
    assert out.effects == (
        f'strategy_random_equip:{equip_pick}',
        f'strategy_gift_random:{char_picks[0]}@1star',
        f'strategy_gift_random:{char_picks[1]}@1star',
    ), '效果串恰 3 条且顺序 = 卡文语序(装备腿先/角色腿后)'
    assert rows_sink.kinds() == [], '正常路径零申报行'
