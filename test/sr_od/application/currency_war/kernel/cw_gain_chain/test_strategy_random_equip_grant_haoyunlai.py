"""好运来(id 231601)即时效果条目随机简易装备发放锁(镜像 src = kernel/
cw_gain_effects.py 的泛化随机装备表 ``_STRATEGY_RANDOM_EQUIP_GRANTS``
'好运来' 行('简易', 2)+ 工厂 ``_make_random_equip_effect('简易', 2)``
经 ``PICK_INVEST_EFFECTS`` 生成式注册;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,新锁落新镜像,先例 = 同目录
test_strategy_random_equip_grant_qiang_zaishou_plus.py count=2 模式卡
枪在手+)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 4/锁 6:
- 锁 6 链发放真值:固定 rng 注入链发放(选卡落地拍:equips 恰 +2、
  两名各自 ∈ 简易池派生集且逐位 = 同种子重放采样值——重放形既锁 rng
  恰 2 抽又锁采样序,放回语义 = 两次独立掷可重复同件,禁断言互异;
  效果串恒 2 条 ``strategy_random_equip:<名>``)/equips 未观察拒落
  跳写形态(效果串恒 count 条);
- 锁 4 自我交互(同链锁承载):拿卡链落地 +2 简易**不被本卡转换**——
  掷得采样名 ∈ 简易池不入本卡进阶谓词(源类别互斥),照常入栏;同局
  持自由市场时的转换属其辖(bench 分支),跨卡语义归
  test_gain_equipment_conversion_equip_target.py 锁 5 双域对号。
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
_SIMPLE_SEED = 20261102

_CARD = '好运来'


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;镜像 test_gain_chain._make_gs
    的 bench/equips 两支,本卡即时效果条目只涉这两域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=c, star=s))
                 for c, s in bench]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _replay_two_picks() -> tuple[str, str]:
    """同种子对同池重放两抽(采样单一源 = roll_random_equip 禁第二采样
    表达式;返回 (第一抽, 第二抽),供链发放真值逐位对拍)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    rng = random.Random(_SIMPLE_SEED)
    return roll_random_equip(rng, '简易'), roll_random_equip(rng, '简易')


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


def test_instant_leg_chain_places_two_no_self_conversion(
        rows_sink: _RowSink) -> None:
    """链发放真值(设计 §4 锁 6,行身份锁 + 锁 4 自我交互):gain_invest_
    strategy 确定入口(rand=False)+ 固定 rng 注入 → equips 恰 +2、两名
    各自 ∈ 简易池派生集(禁手抄清单)且逐位 = 重放采样值(重放形锁 rng
    恰 2 抽 + 采样序;放回语义 = 两抽可重复同件,不断言互异)、效果串恰
    2 条 ``strategy_random_equip:<名>``、active_strategies 入表;掷得
    简易件不入本卡进阶谓词照常入栏(自我转换零,锁 4);正常路径零申报
    行。session=None 直构形态(只登记不写状态的实现分支被闸跳过,登记形态断言由键集闭集
    锁承载)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    pick1, pick2 = _replay_two_picks()
    pool = set(equips_by_category('简易'))
    assert pick1 in pool and pick2 in pool, '预验证:两名 ∈ 简易池'
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == [pick1, pick2], \
        'equips 恰 +2 且逐位 = 重放采样值(rng 恰 2 抽;简易不被本卡转换)'
    assert out.effects == (f'strategy_random_equip:{pick1}',
                           f'strategy_random_equip:{pick2}'), '效果串恰 2 条'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_instant_leg_equips_unobserved_skip_decoupled() -> None:
    """equips 未观察形态锁(设计 §4 锁 6 跳写支):拒落跳写(原语
    detail='equips_unobserved' 现役语义,零写零缺陷)、效果串恒 count 条
    ``strategy_random_equip:<名>(skipped)``(发放事实与落位成败解耦;
    解耦随 count=2 放大 = 两抽照常消费,串恒 2 条)。"""
    pick1, pick2 = _replay_two_picks()
    gs = _make_gs(bench=[])   # equips 不种 = 域未观察
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False,
                               sig=_LSIG, rng=random.Random(_SIMPLE_SEED))
    assert out.placed
    assert gs.equips.value is None, '未观察域零写'
    assert out.effects == (f'strategy_random_equip:{pick1}(skipped)',
                           f'strategy_random_equip:{pick2}(skipped)'), \
        '效果串恒 count 条(skipped 形态)'
