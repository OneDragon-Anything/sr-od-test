"""全员晋升(id 102701)具名装备授予腿锁(镜像 src = kernel/cw_gain_effects.py
的 ``_make_named_equip_grant_effect`` + ``PICK_INVEST_EFFECTS`` 直书登记行;
按被测方法拆目录规范落位——test_gain_chain.py 超线冻结禁追加,新增测试落
新镜像,先例 = 同目录姊妹镜像文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-119-quanyuan-jinsheng.md(定稿)§4 锁 1/2/3 + REVIEW-T119 五裁决点默认案:
- 腿语义 = 卡文句 2「获得2个【拆装扳手】」:具名确定发放
  ``gain_equipment(rand=False)`` ×2(gain-chain.md §5:卡文无随机词;与
  env 侧即时装备支 rand=True 系两通道分野,正本 = fields.md §3.2.15
  rand 两通道分野注记),效果串逐件一条含 placed(拒落可审计);
- 精密金面前置 fail-closed:已持精密拆装扳手 → 整腿零容器写 + 申报行
  留证(宣言 kind = ``NAMED_EQUIP_PRECISE_DECL``,语义申报非缺陷告警)+
  效果串仍逐件登记(placed=False)+ gold 零写钉死(官方真值 = 改 +1 金
  不进栏,金面未建模,接入调用归获得回执覆盖批);
- 工厂泛化守卫:精密前置按物判(判据映射挂在发放物上)——非扳手发放物
  不受精密在场影响(卡级前置分支禁遗传,后继卡直呼工厂不受污染);
- 板面重写句(同卡另一建模面)零改动:注册/词表/桥负写端由存量锁
  ``test_upgrade_all_and_other_bridges_unchanged``(test_effect_inventory)
  承载,本文件只在锁 1 顺带钉「获得链全程 bench/deployed 零写」。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    NAMED_EQUIP_PRECISE_DECL,
    _make_named_equip_grant_effect,
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


def test_named_equip_grant_leg_places_wrenches(rows_sink: _RowSink) -> None:
    """腿行为主锁(设计 §4 锁 1):gain_invest_strategy 全链(rand=False)
    → equips 恰 +2 拆装扳手、逐件各一笔写(write_seq 恰 +3 = 注册 1 + 效果条目 2;
    ②段账本登记 session=None 跳过)、来源 = 确定面 logic、效果串逐件一条含
    placed=True;板面域(bench/deployed)零写 = 板面重写句不经本腿;
    正常路径零申报行。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    out = gain_invest_strategy(gs, None, '全员晋升', rand=False, sig=_LSIG)
    assert out.placed
    assert gs.active_strategies.value == ['全员晋升'], '注册入表'
    assert gs.equips.value == ['拆装扳手', '拆装扳手'], '逐件入栏恰 2 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence == 'pick_invest_named_equip#equip', \
        '腿写端 evidence(逐件各 #equip 后缀一笔)'
    assert gs.write_seq - seq_before == 3, \
        '写数恰 3 = 注册 1 + 装备效果条目 2(②段账本登记 session=None 跳过;' \
        '板面重写桥零写契约由 test_effect_inventory 存量锁承载)'
    assert out.effects == (
        'named_equip_grant:拆装扳手(placed=True)',
        'named_equip_grant:拆装扳手(placed=True)',
    ), '效果串逐件一条含 placed'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化(板面重写句不经本腿)'
    assert gs.deployed.value is None, 'deployed 未观察保持未写(板面零建模)'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_named_equip_grant_precision_gate_fail_closed(
        rows_sink: _RowSink) -> None:
    """精密前置 fail-closed(设计 §4 锁 2):预置精密拆装扳手 1 件 → 整腿
    零容器写(write_seq 不变,锁 2 主断言)+ 申报行恰一行(宣言 kind,语义
    申报非缺陷)+ 效果串仍逐件登记(placed=False,发放事实恒登记)+
    gold 零写钉死(值与来源双不动,金面未建模禁写)+ equips 原值不动。"""
    gs = _make_gs(equips=['精密拆装扳手'], gold=10)
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '全员晋升', rand=False, sig=_LSIG)
    assert effects == (
        'named_equip_grant:拆装扳手(placed=False)',
        'named_equip_grant:拆装扳手(placed=False)',
    ), '效果串仍逐件登记,placed=False 拒入栏可审计'
    assert gs.write_seq == seq_before, '整腿零容器写(fail-closed)'
    assert gs.equips.value == ['精密拆装扳手'], 'equips 原值不动'
    assert gs.gold.value == 10 and gs.gold.source == 'observation', \
        'gold 零写钉死(金面改道未建模,真值归观察/接入调用覆盖批)'
    assert rows_sink.kinds() == [NAMED_EQUIP_PRECISE_DECL], '申报行恰一行'


def test_named_equip_grant_gate_by_item_not_global(
        rows_sink: _RowSink) -> None:
    """工厂泛化守卫(精密前置按物判):精密在场 + 非扳手发放物 → 工厂
    照常入栏零申报行(卡级前置分支禁遗传——判据映射挂在发放物上,后继
    卡直呼工厂不受污染);直呼形态隔离验证,不经注册表。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    leg = _make_named_equip_grant_effect('生命之花', 1)
    effects = leg(gs, sig=_LSIG, rng=random.Random(0))
    assert effects == ['named_equip_grant:生命之花(placed=True)'], \
        '非扳手物不受精密在场影响,照常入栏(直呼工厂返回效果串列表)'
    assert gs.write_seq == seq_before + 1, '发放写恰一笔'
    assert gs.equips.value == ['精密拆装扳手', '生命之花'], '库尾追加'
    assert rows_sink.kinds() == [], '非扳手物零申报行'


def test_named_equip_grant_unobserved_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落分支(设计 §4 锁 3):equips 未观察(None)直构 → 原语拒落零写
    + 效果串仍逐件登记(placed=False,拒落可审计)+ 零申报行(拒落档与
    精密 fail-closed 档相区分:后者有申报行,前者是原语既有语义静默档)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '全员晋升', rand=False, sig=_LSIG)
    assert effects == (
        'named_equip_grant:拆装扳手(placed=False)',
        'named_equip_grant:拆装扳手(placed=False)',
    ), '效果串恒 2 条,placed=False 拒落可审计'
    assert gs.write_seq == seq_before, '拒落零写'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'
