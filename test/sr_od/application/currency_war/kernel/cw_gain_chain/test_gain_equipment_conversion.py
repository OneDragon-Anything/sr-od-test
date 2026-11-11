"""装备获得转换拦截锁(镜像 src = kernel/cw_gain_chain.py 的 gain_equipment
顶段守卫 + _equip_gain_conversion_hit 判定件;按被测方法拆目录规范落位
——test_gain_chain.py 已登记超限冻结禁追加,新锁落新镜像,先例 = 同目录
既有镜像文件)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 + 原稿评审锁
§4④:
- 锁 2 转换主锁:持卡 + gain_equipment(简易件, rand=False)→ equips 零
  增 + 备战席 +1 简易武装箱 + detail 含 converted;箱席满走溢出落位既有
  语义不另锁(落位矩阵回归 = test_gain_bench_item 三落位/test_gain_chain
  test_strategy_box_leg_bench_full_overflow_name 已登记);
- 锁 3 类别边界:进阶/工具/星徽/骇客改件(注册类别'特殊')获得不转换
  照常入栏(转换谓词按注册类别判);
- 锁 4 不持卡零转换(守卫零副作用);
- 锁 1+5 自我转换:选卡链落地 → 净得 1 箱(equips 零增 + bench +1;
  效果条目2 掷序消耗恰 1 抽,效果串恒登记采样名);
- 锁 6 掷序不变:同 seed 持/不持卡两局随机数消耗一致(转换零 rng 消费,
  状态副本差异仅在写入内容)。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_equipment,
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
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwGainChainTest')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '自由市场'

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_SEED = 20261031


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


def _hold_card(gs: GameState) -> None:
    """持卡直置(注册状态容器直写;选卡链正门路径 = 锁 5 走 gain_invest_strategy)。"""
    gs.write_logic(gs.active_strategies, [_CARD], produced_by='test-seed',
                   evidence='t:card', sig=_LSIG)


def _box_slots(gs: GameState) -> list:
    return [s for s in gs.bench.value.slots
            if s is not None and s.kind == 'supply_box']


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


def test_conversion_intercept_places_box_not_equip(rows_sink: _RowSink) -> None:
    """转换主锁(设计 §4 锁 2):持卡 + gain_equipment(简易件, rand=False)
    → 出参 placed=箱落位/detail 含 converted/landing='skipped'/effects 空;
    equips 零增(被转换件不入栏)+ 备战席 +1 简易武装箱(带名槽件);
    正常路径零申报行。rng 零消费(rand=False 原语本就无采样面,转换转发
    再加零——掷序锁由锁 6 两局对拍承载,不冗余双锁)。"""
    item = sorted(equips_by_category('简易'))[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs)
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed, '箱落位成功 = 转换 placed(占席道具落位结果映射)'
    assert out.detail == f'converted:{_CARD}', 'detail 含 converted 标记'
    assert out.landing == 'skipped' and out.merge_levels == 0 \
        and out.effects == (), '出参形状 = 合成 GainOutcome(装备原语语义档)'
    assert gs.equips.value == [], '被转换装备零入栏'
    boxes = _box_slots(gs)
    assert len(boxes) == 1 and boxes[0].item == '简易武装箱', \
        '备战席 +1 简易武装箱(带名槽件)'
    assert bench_units_of(gs) == [], '道具非角色,单位域不变'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_conversion_bench_unobserved_zero_write() -> None:
    """bench 未观察形态(锁 2 placed 语义半边):守卫在栏未观察早退之前,
    直构域持卡也转换——转发落位遇 bench 未观察拒落 → placed=False、
    equips 域零写(转换发生在入栏前,拒落不回滚改写为入栏),detail 仍
    带 converted 标记(拒绝因 = 落位域非转换面,标记留存证)。"""
    item = sorted(equips_by_category('简易'))[0]
    gs = _make_gs(equips=[])   # bench 不种 = 域未观察
    _hold_card(gs)
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed is False and out.detail == f'converted:{_CARD}'
    assert gs.equips.value == [], '未观察域零写(拒落不回滚入栏)'


@pytest.mark.parametrize('cat', ['进阶', '工具', '星徽', '特殊'])
def test_non_simple_categories_pass_through(cat: str,
                                            rows_sink: _RowSink) -> None:
    """类别边界(设计 §4 锁 3):非登记源类别获得不转换照常入栏(转换
    谓词按注册类别判;骇客改件效果条目注册类别 = '特殊' 不命中,设计 §1.3
    辨析回归)。取样排除后果表成员,隔离 on_equipment_gained 追加入席
    干扰(本锁只断言入栏与零箱,后果面非辖域)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        EQUIP_ACQUIRE_CONSEQUENCES,
    )
    pool = [n for n in sorted(equips_by_category(cat))
            if n not in EQUIP_ACQUIRE_CONSEQUENCES]
    assert pool, f'{cat} 池全被后果表占用?取样前提失配,须随批改'
    item = pool[0]
    gs = _make_gs(bench=[], equips=[])
    _hold_card(gs)
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏(零转换标记)'
    assert gs.equips.value == [item], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱(不转换)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_no_card_zero_interception(rows_sink: _RowSink) -> None:
    """不持卡零转换(设计 §4 锁 4):同调用无卡时照常入栏(守卫零副
    作用;同族他卡持卡也不触发——持卡判定 ∩ 转换登记表,表外卡零涉)。"""
    item = sorted(equips_by_category('简易'))[0]
    gs = _make_gs(bench=[], equips=[])
    gs.write_logic(gs.active_strategies, ['规模效应'], produced_by='test-seed',
                   evidence='t:card', sig=_LSIG)
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed and out.detail == '', '照常入栏'
    assert gs.equips.value == [item], '入栏恰 +1'
    assert _box_slots(gs) == [], '零箱'


def test_pick_chain_self_conversion_net_one_box(rows_sink: _RowSink) -> None:
    """自我转换(设计 §4 锁 1+5):选卡链 gain_invest_strategy 落地——
    注册先于效果,效果条目2 掷随机简易(掷序恰 1 抽,采样名经预验证)→ 原语
    守卫命中 → 净得 1 箱(equips 零增 + bench +1);效果串恒登记采样名
    (发放事实与落位成败解耦,T-136 同判);此为卡面字面语义(「将要
    获得」含本卡自身给予)非特例豁免。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    pick = roll_random_equip(random.Random(_SEED), '简易')
    assert pick in equips_by_category('简易'), '预验证:采样名 ∈ 简易池'
    gs = _make_gs(bench=[], equips=[])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=random.Random(_SEED))
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表(先于效果)'
    assert out.effects == (f'strategy_random_equip:{pick}',), \
        '效果串恰 1 条(采样名恒登记)'
    assert gs.equips.value == [], '采样名被转换消费,零入栏'
    boxes = _box_slots(gs)
    assert len(boxes) == 1 and boxes[0].item == '简易武装箱', '净得 1 箱'
    assert bench_units_of(gs) == [], '单位域不变'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_rng_draw_count_identical_with_and_without_card() -> None:
    """掷序不变(设计 §4 锁 6):同 seed 持/不持卡两局随机数消耗一致
    (转换确定事件零 rng 消费;对照局 = 同族随机简易效果条目卡 打捞人才库+,
    无转换效果条目)。状态副本差异仅在写入内容:持卡局 bench +1 箱 equips 空,
    对照局 equips +1 简易件。"""
    gs_a = _make_gs(bench=[], equips=[])
    rng_a = random.Random(_SEED)
    gain_invest_strategy(gs_a, None, _CARD, rand=False, sig=_LSIG,
                         rng=rng_a)
    gs_b = _make_gs(bench=[], equips=[])
    rng_b = random.Random(_SEED)
    gain_invest_strategy(gs_b, None, '打捞人才库+', rand=False, sig=_LSIG,
                         rng=rng_b)
    assert rng_a.getstate() == rng_b.getstate(), \
        '转换零 rng 消费(两局掷序一致)'
    assert gs_a.equips.value == [] and len(_box_slots(gs_a)) == 1, \
        '持卡局:箱替代装备(状态副本差异 = 写入内容)'
    assert len(gs_b.equips.value or []) == 1 and _box_slots(gs_b) == [], \
        '不持卡对照局:简易件照常入栏'
