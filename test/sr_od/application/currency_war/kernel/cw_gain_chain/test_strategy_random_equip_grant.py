"""买彩票(id 110101)随机星徽发放锁(镜像 src = kernel/cw_gain_effects.py
的泛化随机装备表 ``_STRATEGY_RANDOM_EQUIP_GRANTS`` 星徽行 + 工厂
``_make_random_equip_effect('星徽', 1)`` 经 ``PICK_INVEST_EFFECTS`` 生成式
注册;按被测方法拆目录规范落位——test_gain_chain.py 超线冻结禁追加,新锁
落新镜像,先例 = 同目录既有镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-136-maicai-piao.md(定稿)§4 + REVIEW-T136 六裁决点默认案:
- 泛化表 (category, count) 星徽行登记(打捞人才库+ 简易行同表泛化形,
  迁移回归重立留 test_gain_chain.py 原区);池 = ``equips_by_category``
  注册表派生单源,'星徽' 类别池 import 期独立闸搭环境侧便车;
- 固定 rng 注入链发放真值(星徽行链锁)/equips 未观察拒落跳写形态/
  零后果前提锁;rand 语义锁(采样腿 write_logic_rand 通道、不触发失配网)
  由 test_gain_chain.test_random_equip_leg_rand_channel_subchain 辖
  (同一工厂路径的通道语义,类别实参不改变通道选择,不重复立锁);
- 键集闭集断言(+1 '买彩票')与采样纯函数锁(池派生/种子可复现)随
  泛化改形重立于 test_gain_chain.py 原区。
"""
from __future__ import annotations

import random

import pytest

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
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_STAR_SEED = 20261031


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


def test_star_equip_leg_chain_places_one(rows_sink: _RowSink) -> None:
    """链发放真值(设计 §4 锁 3):gain_invest_strategy 确定入口(rand=False)
    + 固定 rng 注入 → equips 恰 +1、名 ∈ 星徽池派生集且 = 采样值(禁手抄
    清单)、效果串恰 1 条 ``strategy_random_equip:<名>``(装备无星级,串不
    带 @ 后缀)、active_strategies 入表;正常路径零申报行。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    pick = roll_random_equip(random.Random(_STAR_SEED), '星徽')
    assert pick in equips_by_category('星徽'), '预验证:采样名 ∈ 星徽池'
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '买彩票', rand=False, sig=_LSIG,
                               rng=random.Random(_STAR_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['买彩票'], '注册入表'
    assert gs.equips.value == [pick], 'equips 恰 +1 且名 = 采样值'
    assert out.effects == (f'strategy_random_equip:{pick}',), '效果串恰 1 条'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_star_equip_leg_equips_unobserved_skip_decoupled() -> None:
    """equips 未观察形态锁(设计 §4 锁 4):拒落跳写(原语
    detail='equips_unobserved' 现役语义,零写零缺陷)、效果串恒登记
    ``strategy_random_equip:<名>(skipped)``(发放事实与落位成败解耦,
    非静默丢失;骇客 mod_sampled 两形态同构)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    pick = roll_random_equip(random.Random(_STAR_SEED), '星徽')
    gs = _make_gs(bench=[])   # equips 不种 = 域未观察
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '买彩票', rand=False, sig=_LSIG,
                               rng=random.Random(_STAR_SEED))
    assert out.placed
    assert gs.equips.value is None, '未观察域零写'
    assert out.effects == (f'strategy_random_equip:{pick}(skipped)',), \
        '效果串恒登记(skipped 形态)'


def test_star_equip_leg_zero_consequence(rows_sink: _RowSink) -> None:
    """零后果锁(设计 §4 锁 6):链执行后装备获得后果链零动作(无后果追加入席)
    ——前提依赖 = 星徽池 ∩ EQUIP_ACQUIRE_CONSEQUENCES = ∅(若未来后果表
    收星徽件,本锁前提失效须随批改,勿盲改断言)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        EQUIP_ACQUIRE_CONSEQUENCES,
    )
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    # 前提守卫:破前提时 on_equipment_gained 回调会沿后果链追加入席,
    # 「效果串恒 1 条 + bench 零变」失效——守卫先红,提示语义变化。
    assert set(equips_by_category('星徽')) & \
        set(EQUIP_ACQUIRE_CONSEQUENCES) == set(), \
        '星徽池 ∩ 后果表须为空(零后果前提)'
    pick = roll_random_equip(random.Random(_STAR_SEED), '星徽')
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '买彩票', rand=False, sig=_LSIG,
                               rng=random.Random(_STAR_SEED))
    assert out.effects == (f'strategy_random_equip:{pick}',), \
        '效果串恰 1 条(无后果追加串)'
    assert bench_units_of(gs) == [], '装备获得后果链零入席'
    assert rows_sink.kinds() == [], '正常路径零申报行'
