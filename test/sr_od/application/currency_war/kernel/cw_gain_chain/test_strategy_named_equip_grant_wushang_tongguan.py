"""无伤通关(id 103001)具名装备授予腿锁(镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「无伤通关」;具名装备授予族后继卡,
族模式卡 = 全员晋升——工厂语义锁住同目录姊妹镜像 test_strategy_named_equip_
grant.py,本文件只锁本卡登记面 + 行为面 + 零建模边界,按被测方法拆目录规范
落位,先例 = 同目录姊妹镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-122-wushang-tongguan.md(定稿)§4 锁面 + REVIEW-T122 §四 ③/④ 裁决默认案:
- 即时腿 = 卡文句 2「立即获得1个【生命之花】」:登记行直书
  ``_make_named_equip_grant_effect('生命之花', 1)``,具名确定发放
  ``gain_equipment(rand=False)`` 单件入栏,效果串恰一条含 placed
  (gain-chain.md §5:卡文无随机词);
- 条件金腿 = 卡文句 1「战斗结束时，若此次战斗中没有角色陷入过无法战斗状态，
  获得1金币。」实机(live)和模拟器(sim)两边真值皆盲零建模(权威版本 = invest_effects.md §8 型③成员;
  记录模型不经 instant_gold 消费,fields.md §4.1 观察覆盖兜底)——金零写
  钉死进腿锁 + STRATEGY_EFFECTS 反向锁钉死「零建模是有意裁决非漏登记」;
- 精密金面前置按物判(判据映射只挂拆装扳手):生命之花 gate 恒 None 走
  纯发放循环,精密在场照常入栏零申报行(卡级前置分支零遗传的登记面回归,
  与姊妹镜像的工厂直呼形态互补)。
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
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs(*, equips: list[str] | None = None,
             gold: int | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;本卡只涉 equips/gold
    两域,bench 恒空场 = 板面域零写对照)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1)),
             BenchSlot(kind='empty')]
    slots += [BenchSlot(kind='empty')] * (9 - len(slots))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    if gold is not None:
        gs.observe(gs.gold, gold, sig=_SIG_OBS)
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


def test_wushang_tongguan_grant_leg_places_flower(
        rows_sink: _RowSink) -> None:
    """登记面 + 腿行为主锁:gain_invest_strategy 全链(rand=False)→ 注册
    入表 + equips 恰 +1 生命之花、写数恰 +2(注册 1 + 腿 1;②段账本登记
    session=None 跳过)、来源 = 确定面 logic、效果串恰一条含 placed=True
    (效果串仅 named_equip_grant 前缀——金腿零建模不进效果体);条件金腿
    零建模钉死(gold 值与来源双不动);板面域(bench/deployed)零写;
    正常路径零申报行。"""
    assert '无伤通关' in PICK_INVEST_EFFECTS, '登记面已登记'
    gs = _make_gs(equips=[], gold=10)
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, '无伤通关', rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == ['无伤通关'], '注册入表'
    assert gs.equips.value == ['生命之花'], '具名单件入栏恰 1 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '腿写端 evidence(#equip 后缀一笔)'
    assert gs.write_seq - seq_before == 2, \
        '写数恰 2 = 注册 1 + 装备效果条目 1(②段账本登记 session=None 跳过)'
    assert out.effects == ('named_equip_grant:生命之花(placed=True)',), \
        '效果串恰一条含 placed'
    assert gs.gold.value == 10 and gs.gold.source == 'observation', \
        '条件金腿零建模钉死(金面禁直写,真值归观察覆盖兜底)'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化'
    assert gs.deployed.value is None, 'deployed 未观察保持未写(板面零建模)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_wushang_tongguan_precision_gate_not_applies(
        rows_sink: _RowSink) -> None:
    """精密前置按物判的登记面回归:预置精密拆装扳手 1 件,经注册表分派获得
    无伤通关 → 生命之花不命中判据映射(gate 恒 None)走纯发放循环,照常
    入栏零申报行(卡级前置分支零遗传——姊妹镜像已验工厂直呼形态,本锁钉
    注册表分派路径同判)。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '无伤通关', rand=False, sig=_LSIG)
    assert effects == ('named_equip_grant:生命之花(placed=True)',), \
        '精密在场不受污染,照常入栏'
    assert gs.equips.value == ['精密拆装扳手', '生命之花'], '库尾追加'
    assert gs.write_seq == seq_before + 1, '发放写恰一笔'
    assert rows_sink.kinds() == [], '纯发放循环零申报行(无 fail-closed 档)'


def test_wushang_tongguan_unobserved_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 原语拒落零写 + 效果串仍登记
    (placed=False,拒落可审计)+ 零申报行(拒落档 = 原语既有语义静默档,
    与精密 fail-closed 申报档区分)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '无伤通关', rand=False, sig=_LSIG)
    assert effects == ('named_equip_grant:生命之花(placed=False)',), \
        '效果串恒 1 条,placed=False 拒落可审计'
    assert gs.write_seq == seq_before, '拒落零写'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'


def test_wushang_tongguan_condition_gold_zero_modeling_boundary() -> None:
    """条件金腿零建模反向锁(设计 §4 锁 4 现值基准改形:BATTLE_END 枚举成员
    已随死代码清偿移除,反向基准改挂 STRATEGY_EFFECTS 键集):「无伤通关」∉
    STRATEGY_EFFECTS——条件金腿零建模是有意裁决非漏登记(触发事件「角色
    陷入无法战斗」sim 无生产点/live 结算屏无观察识别标志,权威版本 = invest_effects.
    md §8 型③成员点名 + effect-domain.md §7.4 候选点名在卷;启用 = 各自
    建模批先立规格条目再接事件源,防后续批静默补条目破坏观察覆盖兜底口径)。"""
    assert '无伤通关' not in STRATEGY_EFFECTS, \
        '零建模边界:条件腿无 STRATEGY_EFFECTS 条目(有意裁决非漏登记)'
