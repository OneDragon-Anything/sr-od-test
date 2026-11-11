"""武装支援+(id 102502)三条效果条目分层组合锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS['武装支援+']`` 组合登记行;按被测方法拆目录规范
落位——test_gain_chain.py 超线冻结禁追加,新增测试落新镜像,先例 = 同目录
姊妹卡镜像文件 test_strategy_compose_grant.py)。

测试面依据 = 设计稿(原件已退役)
设计稿(原件已退役)§4 锁 1 + 已退役评审稿 六裁决点默认案:
- 组合登记 = ``PICK_INVEST_EFFECTS['武装支援+'] = _compose_grant_legs(
  _make_random_equip_effect('简易', 1), _make_reinforcement_effect(((4, 1),)))``
  (条目序 = 卡文语序装备效果条目先/角色效果条目后;效果条目参数登记行单次出现,单一源;
  金币效果条目不进效果体 = STRATEGY_ECONOMY 注册行 instant_gold=6 分层承载);
- 固定 rng 注入链发放真值:rng 消费序 2 抽 = 第 1 抽装备
  (``roll_random_equip`` 简易池)+ 第 2 抽角色(4 费池放回)——条目序改排
  即采样名漂移,被顺序断言捕获;效果串恰 2 条且顺序固定;
- 值域派生集:4 费采样池 = ``random_char_pool(RandomCharSpec(cost=4,
  star=1))``(chars_by_cost(4) 派生 14 名经双形态合并收尾——开拓者·记忆
  为键侧剔除条目,采样名走值侧形态;罗刹物理置于 5 费段区块,禁按段区块
  目测手抄清单);
- 前提守卫:「效果串恒 2 条」前提 = 简易池 ∩ ``EQUIP_ACQUIRE_CONSEQUENCES``
  = ∅(设计 §1.2d/§4 锁 1 前提注记)——装备注册表扩员(新简易件带获得
  后果)时守卫先红,提示语义变化,勿盲改主锁断言数;
- 禁断言面(设计 §2.3/§4):批内 1 只 < 3 零级联为平凡形态,不立级联
  形态断言(级联归一条效果条目 T-89 锁辖域);金币效果条目零新增锁、不立「sim 金不发放」
  行为锁(锁缺口 = 固化缺口为设计意图)。
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
    roll_random_equip,
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
    equips_by_category,
    random_char_pool,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 固定种子(单抽形态无互异约束,任意种子;失配 = 换种子)。
_COMPOSE_SEED = 20261101


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


def test_wuzhuang_zhiyuan_plus_compose_legs_chain_in_order(
        rows_sink: _RowSink) -> None:
    """组合效果条目锁(设计 §4 锁 1):gain_invest_strategy 确定入口(rand=False)
    + 固定 rng 注入 → equips 恰 +1(名 ∈ 简易池派生集,禁手抄清单)、
    bench 恰 +1(名 ∈ 4 费采样池派生集、1★;批内 1 只 < 3 零级联平凡
    形态)、效果串恰 2 条且顺序 = [strategy_random_equip:<装备名>,
    strategy_gift_random:<角色名>@1star](顺序锁 = 多条效果条目编排与 rng 消费
    序,本卡新增机制面);正常路径零申报行。"""
    # 预采样(独立 rng 实例按消费序 2 抽):与实际注入的 rng 同种子同序,
    # 条目序改排 = 采样名互换,顺序断言必红(改序 = 掷序漂移)。
    rng = random.Random(_COMPOSE_SEED)
    equip_pick = roll_random_equip(rng, '简易')
    char_pick = roll_reinforcement_names(rng, 4, 1)[0]
    # 前提守卫(设计 §4 锁 1 前提注记):破前提时装备获得后果链追加串,
    # 「效果串恒 2 条」失效——守卫先红,勿盲改断言数。
    assert set(equips_by_category('简易')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '简易池 ∩ 后果表须为空(效果串恒 2 条前提)'
    assert char_pick in random_char_pool(
        RandomCharSpec(cost=4, star=1)), '预验证:角色采样 ∈ 4 费采样池派生集'
    assert equip_pick in equips_by_category('简易'), '预验证:装备采样 ∈ 简易池'

    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '武装支援+', rand=False, sig=_LSIG,
                               rng=random.Random(_COMPOSE_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['武装支援+'], '注册入表'
    assert gs.equips.value == [equip_pick], 'equips 恰 +1 且名 = 第 1 抽装备'
    units = [(u.char_id, u.star) for u in bench_units_of(gs)]
    assert units == [(char_pick, 1)], 'bench 恰 +1 全 1★'
    assert out.effects == (
        f'strategy_random_equip:{equip_pick}',
        f'strategy_gift_random:{char_pick}@1star',
    ), '效果串恰 2 条且顺序 = 卡文语序(装备效果条目先/角色效果条目后)'
    assert rows_sink.kinds() == [], '正常路径零申报行'
