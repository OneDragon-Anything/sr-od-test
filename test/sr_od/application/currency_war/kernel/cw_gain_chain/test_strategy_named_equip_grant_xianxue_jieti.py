"""鲜血阶梯(id 351201)具名装备授予效果条目锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「鲜血阶梯」;具名装备授予族后继卡,
族模式卡 = 全员晋升——工厂语义锁住同目录姊妹镜像 test_strategy_named_equip_
grant.py,单件先例 = 赌神·银 test_strategy_named_equip_grant_dushen_yin.py,
按被测方法拆目录规范落位)。

测试面依据 = 原稿锁面
原稿锁面§7-② 锁 2/锁 3/锁 4 + 原稿评审锁(§ 号 = 原稿节序)§7:
- 效果条目1「获得【斩首行动】」= 登记行直书
  ``_make_named_equip_grant_effect('斩首行动', 1)``,具名确定发放
  ``gain_equipment(rand=False)`` 单件入栏,效果串恰 1 条含 placed
  (evidence 断言用前缀匹配——原语内追加 ``#equip`` 后缀,精确匹配假红,
  同族口径);
- 锁 4 变体精确名:「斩首行动」子串四变体(斩首行动/白昼·斩首行动/
  极·白昼·斩首行动/斩首行动·特权)唯一真发放物 = 基础名——发放名
  字面量精确断言,工厂参数漂移或变体误引在此红;
- 效果条目2「每消灭一名精英/首领敌人伤害增幅永久提高8%」= 击杀触发族型③
  零登记零建模(触发事件逐击杀两边皆盲,占位登记即判读失真),本文件
  零建模效果条目锁 = 负面由 PICK 键集闭集/五注册表现值锁承载(零 SE/零 GRANTS
  条目已在注册表现值锁面),不另立哨;
- 双持好运来链上拦截 = 既有转换守卫真值(类目制 '进阶'→'好运令牌',
  转换域锁 test_gain_equipment_conversion.py 承载),本文件不重复锁;
- 本卡无金句零金币效果条目(gold 域零写断言覆盖);装备非占席不入 bench,
  板面域(bench/deployed)零写。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
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

_CARD = '鲜血阶梯'
_ITEM = '斩首行动'


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察;本卡只涉 equips 域,bench 恒空场
    = 板面域零写对照)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1)),
             BenchSlot(kind='empty')]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


class _RowSink:
    """缺陷台账行收集(镜像姊妹文件同名 fixture,装配 + 必达收尾)。"""

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


def test_xianxue_jieti_grant_leg_places_equipment(
        rows_sink: _RowSink) -> None:
    """效果条目1 放置行为主锁(§7-② 锁 2):gain_invest_strategy 全链(rand=False)
    → 注册入表 + equips 恰 +1 斩首行动、写数恰 2(注册 1 + 效果条目 1;②段账本
    登记 session=None 跳过)、来源 = 确定面 logic;零金写(本卡无金句);
    板面域(bench/deployed)零写;正常路径零申报行。前提守卫:斩首行动
    ∉ 后果表(破前提时获得后果链追加效果串与写入——守卫先红,勿盲改)。"""
    assert _ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '斩首行动 ∉ 后果表(单条效果串前提)'
    assert _CARD in PICK_INVEST_EFFECTS, '登记面已登记'
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value.count(_ITEM) == 1, '选卡即得:具名单件入栏恰 1 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence.startswith('pick_invest_named_equip'), \
        '效果条目写端 evidence 前缀(原语内追加 #equip 后缀,前缀匹配防假红)'
    assert gs.write_seq - seq_before == 2, \
        '写数恰 2 = 注册 1 + 装备效果条目 1(②段账本登记 session=None 跳过)'
    assert gs.gold.value is None, '本卡无金句零金写'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化(装备非占席不入席)'
    assert gs.deployed.value is None, 'deployed 未观察保持未写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_xianxue_jieti_effect_steps_shape(rows_sink: _RowSink) -> None:
    """效果条目1 效果串形态锁(§7-② 锁 3):on_strategy_gained 效果串恰 1 条
    ``named_equip_grant:斩首行动(placed=True)``——逐件一条携带 placed
    (前缀 named_equip_grant 分域可审计,与 box_grant/equip_grant/
    strategy_random_equip 分列)。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (f'named_equip_grant:{_ITEM}(placed=True)',), (
        '效果串恰 1 条逐件一条携带 placed'
    )
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_xianxue_jieti_exact_variant_name(rows_sink: _RowSink) -> None:
    """效果条目1 变体精确名锁(§7-② 锁 4):发放名 == '斩首行动' 精确串(整表
    字面量相等断言,非 count 语义)——工厂参数漂移或子串四变体误引
    (白昼·斩首行动/极·白昼·斩首行动/斩首行动·特权)在此红。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert gs.equips.value == [_ITEM], '发放名精确 = 斩首行动(四变体防误引)'
    assert rows_sink.kinds() == [], '正常路径零申报行'
