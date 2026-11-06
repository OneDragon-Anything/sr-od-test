"""升级锅炉(id 230801)具名装备授予腿锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「升级锅炉」;具名装备授予族后继卡,
族模式卡 = 全员晋升——工厂语义锁住同目录姊妹镜像 test_strategy_named_equip_
grant.py,同物 ×2 先例 = 小复制 test_strategy_named_equip_grant_xiaofuzhi.py,
按被测方法拆目录规范落位)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-239-shengji-guolu.md(定稿)§4 锁 5 G 形态 + 同目录裁定册
PENDING-DECISIONS.md T-239 小节(用户裁定 2026-11-02 拍案 G 选卡即得):
- 卡文两句分治:句②「获得2个【冶金炉】」= **选卡即得**(获得句后置于条件
  句亦判即得——「立刻标记」家族口径的反例首例),登记行直书
  ``_make_named_equip_grant_effect('冶金炉', 2)``,具名确定发放
  ``gain_equipment(rand=False)`` 循环 2 次逐件一条入栏,效果串恰两条各含
  placed;evidence 断言用前缀匹配(原语内追加 ``#equip`` 后缀,精确匹配
  假红——同族口径);
- 工厂形状(精密前置按物判,判据映射只挂拆装扳手):冶金炉 gate 恒 None
  走纯发放循环——已持精密拆装扳手时本卡照常 +2 炉零申报行(卡级前置
  分支禁遗传;工厂若误把精密前置遗传给炉发放物会在此红,T-137 买彩票+
  同型机械化回归);
- 句①升格修饰面零建模 = 炉上报链零改动:本卡注册只增选卡拍发放腿,
  持卡面对烧炉变异链零分支(张力归 v0 校准批,不在本锁面);
- 本卡无金句零金币效果条目(gold 域零写断言覆盖);实机(live)和模拟器(sim)两边同链:sim 选卡经同一
  ``gain_invest_strategy`` 链零新代码(炉 ×2 自动入 gs.equips;sim 局
  死库存零使用系已登记边界申报),本文件锁 kernel 链 = 实机和模拟器两边公共段。
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

_CARD = '升级锅炉'
_ITEM = '冶金炉'


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;本卡只涉 equips 域,
    bench 恒空场 = 板面域零写对照)。"""
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


def test_shengji_guolu_grant_leg_places_two_furnaces(
        rows_sink: _RowSink) -> None:
    """选卡行为主锁(§4 锁 5 G 形态):gain_invest_strategy 全链(rand=False)
    → 注册入表 + equips 恰 +2 冶金炉、写数恰 +3(注册 1 + 效果条目 2;②段账本
    登记 session=None 跳过)、来源 = 确定面 logic、效果串恰两条逐件一条
    各含 placed=True;零金写(本卡无金句);板面域(bench/deployed)零写;
    正常路径零申报行。前提守卫:冶金炉 ∉ 后果表(破前提时获得后果链追加
    效果串,「效果串恒 2 条」失效——守卫先红,勿盲改断言数)。"""
    assert _ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '冶金炉 ∉ 后果表(效果串恒 2 条前提)'
    assert _CARD in PICK_INVEST_EFFECTS, '登记面在册'
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == [_ITEM, _ITEM], '选卡即得:具名双件入栏恰 2 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence.startswith('pick_invest_named_equip'), \
        '腿写端 evidence 前缀(原语内追加 #equip 后缀,前缀匹配防假红)'
    assert gs.write_seq - seq_before == 3, \
        '写数恰 3 = 注册 1 + 装备效果条目 2(②段账本登记 session=None 跳过)'
    assert out.effects == (
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), '效果串恰两条逐件一条各含 placed'
    assert gs.gold.value is None, '本卡无金句零金写'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化'
    assert gs.deployed.value is None, 'deployed 未观察保持未写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_shengji_guolu_precision_gate_not_inherited(
        rows_sink: _RowSink) -> None:
    """工厂形状锁(精密前置按物判):已持精密拆装扳手 → 本卡选卡照常 +2 炉
    零申报行(精密金面规则只辖「再获得拆装扳手」改金,冶金炉无该规则——
    登记行直呼工厂产品无卡级前置分支;误挂 gate 会在此红,同族机械化
    回归 = T-137 买彩票+ 锁 6 反向形态同款)。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.equips.value == ['精密拆装扳手', _ITEM, _ITEM], \
        '精密在场不拦炉腿,库尾照常追加 2 件'
    assert gs.write_seq - seq_before == 3, '写数恰 3(注册 1 + 炉效果条目 2)'
    assert out.effects == (
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), '效果串恒 2 条 placed=True(非 fail-closed 档)'
    assert rows_sink.kinds() == [], '精密在场零申报行(gate 恒 None)'


def test_shengji_guolu_unobserved_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 原语拒落零写 + 效果串仍逐件
    登记(placed=False ×2,拒落可审计)+ 零申报行(拒落档 = 原语既有语义
    静默档,与精密 fail-closed 申报档区分)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'named_equip_grant:{_ITEM}(placed=False)',
        f'named_equip_grant:{_ITEM}(placed=False)',
    ), '效果串恒 2 条逐件一条,placed=False 拒落可审计'
    assert gs.write_seq == seq_before, '拒落零写'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'
