"""空仓(id 202401)即时腿随机简易装备发放锁(镜像 src = kernel/
cw_gain_effects.py 的泛化随机装备表 ``_STRATEGY_RANDOM_EQUIP_GRANTS``
'空仓' 行('简易', 1)+ 工厂 ``_make_random_equip_effect('简易', 1)``
经 ``PICK_INVEST_EFFECTS`` 生成式注册;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_random_equip_grant_qiang_zaishou.py 枪在手)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-189-kongcang.md(定稿)§4 锁 1(骑 T-136 锁形,行身份锁):
- 固定 rng 注入链发放真值(选卡落地拍:equips 恰 +1、名 ∈ 简易池派生集
  且 = 采样值、效果串恰 1 条 ``strategy_random_equip:<名>``——锁成员
  关系不锁池计数)/equips 未观察拒落跳写形态;
- 同卡条件腿(「进入新节点时…获得2经验值」)不入本表——触发时点非选卡
  拍,归 cw_investments.STRATEGY_EMPTY_EQUIP_XP_GRANTS + sim 节点窗腿
  (登记面锁 = kernel/cw_investments/test_strategy_empty_equip_xp_grants.py,
  谓词面锁 = 同目录 test_check_strategy_empty_equip_xp.py,sim 世界锁 =
  sim/cw_sim_backend/test_strategy_empty_equip_xp_sim_chain.py,两条效果条目分域);
- rand 语义锁(采样腿 write_logic_rand 通道、不触发失配网)由
  test_gain_chain.test_random_equip_leg_rand_channel_subchain 辖——
  同一工厂路径的通道语义,本行与该锁同为 '简易' 类别实参,类别实参不
  改变通道选择,不重复立锁(枪在手先例同判)。
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
    consume_defect_sink,
    set_defect_sink,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_SIMPLE_SEED = 20261103


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像 test_gain_chain._make_gs
    的 bench/equips 两支,本卡即时腿只涉这两域)。"""
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


def test_instant_leg_chain_places_one(rows_sink: _RowSink) -> None:
    """链发放真值(设计 §4 锁 1,行身份锁):gain_invest_strategy 确定入口
    (rand=False)+ 固定 rng 注入 → equips 恰 +1、名 ∈ 简易池派生集且 =
    采样值(禁手抄清单)、效果串恰 1 条 ``strategy_random_equip:<名>``
    (装备无星级,串不带 @ 后缀)、active_strategies 入表;正常路径零
    申报行。session=None 直构形态(只登记不写状态的实现分支被闸跳过,登记形态断言由键集
    闭集锁承载)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    pick = roll_random_equip(random.Random(_SIMPLE_SEED), '简易')
    assert pick in equips_by_category('简易'), '预验证:采样名 ∈ 简易池'
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '空仓', rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.active_strategies.value == ['空仓'], '注册入表'
    assert gs.equips.value == [pick], 'equips 恰 +1 且名 = 采样值'
    assert out.effects == (f'strategy_random_equip:{pick}',), '效果串恰 1 条'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_instant_leg_equips_unobserved_skip_decoupled() -> None:
    """equips 未观察形态锁(设计 §4 锁 1 跳写支):拒落跳写(原语
    detail='equips_unobserved' 现役语义,零写零缺陷)、效果串恒登记
    ``strategy_random_equip:<名>(skipped)``(发放事实与落位成败解耦,
    非静默丢失;骇客 mod_sampled 两形态同构)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    pick = roll_random_equip(random.Random(_SIMPLE_SEED), '简易')
    gs = _make_gs(bench=[])   # equips 不种 = 域未观察
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, '空仓', rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.equips.value is None, '未观察域零写'
    assert out.effects == (f'strategy_random_equip:{pick}(skipped)',), \
        '效果串恒登记(skipped 形态)'
