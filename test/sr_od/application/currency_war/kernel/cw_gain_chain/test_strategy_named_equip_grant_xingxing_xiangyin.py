"""星星相印(id 104001)具名装备授予腿锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「星星相印」;具名装备授予族后继卡,
族模式卡 = 全员晋升——工厂语义锁住同目录姊妹镜像 test_strategy_named_equip_
grant.py,本文件只锁本卡登记面 + 行为面,按被测方法拆目录规范落位,先例 =
同目录姊妹镜像文件 test_strategy_named_equip_grant_wushang_tongguan.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-135-xingxing-
xiangyin.md(定稿)§4 锁 4 + REVIEW-T135 §四 ④:
- 效果条目 2 = 卡文句 2「立刻获得1个【员工投影仪】」:登记行直书
  ``_make_named_equip_grant_effect('员工投影仪', 1)``,具名确定发放
  ``gain_equipment(rand=False)`` 单件入栏,效果串恰一条含 placed;
- 精密金面前置按物判(判据映射只挂拆装扳手):员工投影仪 gate 恒 None
  走纯发放循环,精密在场照常入栏零申报行(卡级前置分支零遗传);
- 合成金腿(卡文句 1)= STRATEGY_EFFECTS ON_MERGE 条目 + 合成事件发放
  腿另路(kernel),两条效果条目异族不入本文件辖域(金腿行为面 = 姊妹镜像
  test_check_strategy_star_merge_gold.py)。
"""
from __future__ import annotations

import pytest

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

_CARD = '星星相印'
_ITEM = '员工投影仪'


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;本卡装备腿只涉
    equips 域,bench 恒空场 + gold 未读 = 金腿域零干扰对照)。"""
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


def test_xingxing_xiangyin_grant_leg_places_projector(
        rows_sink: _RowSink) -> None:
    """登记面 + 腿行为主锁:gain_invest_strategy 全链(rand=False)→ 注册
    入表 + equips 恰 +1 员工投影仪、写数恰 +2(注册 1 + 腿 1;②段账本
    登记 session=None 跳过)、来源 = 确定面 logic、效果串恰一条含
    placed=True;金腿异族不入效果体(gold 未读保持未读,零金写);
    板面域(bench/deployed)零写;正常路径零申报行。"""
    assert _CARD in PICK_INVEST_EFFECTS, '登记面在册'
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert gs.equips.value == [_ITEM], '具名单件入栏恰 1 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '腿写端 evidence(#equip 后缀一笔)'
    assert gs.write_seq - seq_before == 2, \
        '写数恰 2 = 注册 1 + 装备腿 1(②段账本登记 session=None 跳过)'
    assert out.effects == (f'named_equip_grant:{_ITEM}(placed=True)',), \
        '效果串恰一条含 placed'
    assert gs.gold.value is None, '金腿异族不入效果体(装备腿零金写)'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化'
    assert gs.deployed.value is None, 'deployed 未观察保持未写(板面零建模)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_xingxing_xiangyin_precision_gate_not_applies(
        rows_sink: _RowSink) -> None:
    """精密前置按物判的登记面回归:预置精密拆装扳手 1 件,经注册表分派
    获得星星相印 → 员工投影仪不命中判据映射(gate 恒 None)走纯发放
    循环,照常入栏零申报行(工厂泛化——T-122 裁决点 5 前置判定项级
    声明,卡级前置分支零遗传)。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (f'named_equip_grant:{_ITEM}(placed=True)',), \
        '精密在场不受污染,照常入栏'
    assert gs.equips.value == ['精密拆装扳手', _ITEM], '库尾追加'
    assert gs.write_seq == seq_before + 1, '发放写恰一笔'
    assert rows_sink.kinds() == [], '纯发放循环零申报行(无 fail-closed 档)'


def test_xingxing_xiangyin_unobserved_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 原语拒落零写 + 效果串仍
    登记(placed=False,拒落可审计)+ 零申报行(拒落档 = 原语既有语义
    静默档,与精密 fail-closed 申报档区分)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (f'named_equip_grant:{_ITEM}(placed=False)',), \
        '效果串恒 1 条,placed=False 拒落可审计'
    assert gs.write_seq == seq_before, '拒落零写'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'


def test_xingxing_xiangyin_acquire_no_cascade() -> None:
    """获得零级联锚:员工投影仪 ∉ EQUIP_ACQUIRE_CONSEQUENCES(表 =
    分身墨镜/分身墨镜Max/数据拷贝仪Max 三键现值)——获得零后果是
    设计转引事实,注册面复测钉死(表扩员波及时本锁先红触发重申报)。"""
    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        EQUIP_ACQUIRE_CONSEQUENCES,
    )
    assert _ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, '获得零级联(表外件)'
