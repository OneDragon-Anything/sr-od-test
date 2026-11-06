"""琼玉专家:青雀(id 360301)顾问入商店族具名装备授予效果条目锁(镜像 src =
kernel/cw_gain_effects.py 的 ``PICK_INVEST_EFFECTS`` 直书登记行
「琼玉专家:青雀」;顾问解锁效果条目 = cw_investments.STRATEGY_GRANTS 同卡行
advisor=True 登记面零改动复核,本文件锁效果体效果条目与两条效果条目联立全序;按被测
方法拆目录规范落位,同形模板 = 停云顾问 test_strategy_tingyun.py
〔advisor+具名授予联立〕与升级锅炉 test_strategy_named_equip_grant_
shengji_guolu.py〔同物冶金炉 ×2〕)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-415-qiongyu-zhuanjia-qingque.md(定稿)§4 锁面(卡面官方原文:
「获得装备着3个随机星徽的专家顾问【青雀】，并使其在本局游戏中加入
商店。获得2个【冶金炉】。」——顾问效果条目/入商店效果条目已登记零动作,冶金炉效果条目 =
本卡唯一机制件):

- 效果条目2 = 登记行直书 ``_make_named_equip_grant_effect('冶金炉', 2)``,
  具名确定发放 ``gain_equipment(rand=False)`` 循环 2 次逐件一条入栏;
- 联立效果串全序:恰 3 条 = advisor_unlock 1 → named_equip_grant 2
  (获得链 advisor 效果条目先于效果体分派,顺序与卡文语序一致);
- 双顾问去重:摸个鱼吧I 同解锁青雀,解锁原语只增去重,跨卡/同卡两形态
  同锁;
- 穿戴效果条目「装备着3个随机星徽」零建模 = 本文件零穿戴断言面,拒落形态锁
  覆盖 equips 未观察负支。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _STRATEGY_RANDOM_EQUIP_GRANTS,
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
    STRATEGY_GRANTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '琼玉专家:青雀'
_ITEM = '冶金炉'
_SEED = 20261214


def _make_gs(*, equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;bench 恒观测单单位
    场 = 板面域零写对照,顾问卡不入席负证载体)。"""
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


def test_qiongyu_qingque_row_single_source() -> None:
    """登记面单一源:具名授予行已登记 + 顾问解锁登记面镜像已登记(advisor 型
    chars_immediate 直读);泛化表零本卡键(防回退撞键);冶金炉 ∉ 后果表
    (获得零级联 = 「效果串恒 2 条」前提守卫,破前提时获得后果链追加效果
    串,守卫先红勿盲改断言数)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '登记行已登记'
    assert _CARD not in _STRATEGY_RANDOM_EQUIP_GRANTS, \
        '泛化表零本卡键(撞键形态禁回退)'
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.advisor is True and grant.chars_immediate == ('青雀',), \
        '顾问解锁登记面镜像(advisor 型,入池可刷零新增登记)'
    assert _ITEM not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '冶金炉 ∉ 后果表(获得零级联前提)'


def test_qiongyu_qingque_chain_unlock_then_two_furnaces(
        rows_sink: _RowSink) -> None:
    """行为主锁(联立效果串全序):gain_invest_strategy 全链(rand=False,
    固定种子)→ 注册入表 + 解锁写 + equips 恰 +2 冶金炉;效果串全序恰
    3 条 = advisor_unlock 1 → named_equip_grant 2(advisor 效果条目先于效果体
    分派,与卡文语序顾问先/冶金炉后一致);解锁 evidence 前缀断言;确定
    发放走确定面;写数恰 4 = 注册 1 + 解锁 1 + 炉效果条目 2(②段账本登记
    session=None 跳过);rng 零消费;板面域零写;零金写(本卡无金句);
    正常路径零申报行。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert out.effects == (
        f'advisor_unlock:{_CARD}:青雀',
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), f'联立效果串全序恰 3 条(解锁→逐件授予): {out.effects}'
    assert gs.unlocked_experts.value == ('青雀',), '专家解锁权威写'
    assert gs.unlocked_experts.evidence == \
        f'on_strategy_gained:{_CARD}#expert_unlock', \
        '解锁写 evidence 前缀(获得链 advisor 效果条目申报形态)'
    assert gs.unlocked_experts.source == 'logic', '解锁确定事实走确定面'
    assert gs.equips.value == [_ITEM, _ITEM], '冶金炉双件入栏恰 2 件'
    assert gs.equips.source == 'logic', '确定发放走确定面'
    assert gs.equips.evidence.startswith('pick_invest_named_equip'), \
        '效果条目写端 evidence 前缀(原语内追加 #equip 后缀,前缀匹配防假红)'
    assert gs.write_seq - seq_before == 4, \
        '写数恰 4 = 注册 1 + 解锁 1 + 炉效果条目 2(账本登记 session=None 跳过)'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
    assert gs.gold.value is None, '本卡无金句零金写'
    assert len(bench_units_of(gs)) == 1, 'bench 零变化(顾问入商店非送单位)'
    assert gs.deployed.value is None, 'deployed 未观察保持未写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_qiongyu_qingque_precision_gate_not_inherited(
        rows_sink: _RowSink) -> None:
    """工厂形状锁(精密前置按物判):已持精密拆装扳手 → 本卡选卡照常 +2 炉
    零申报行(精密金面规则只辖「再获得拆装扳手」改金,冶金炉无该规则——
    登记行直呼工厂产品无卡级前置分支;误挂 gate 会在此红,升级锅炉同款
    机械化回归)。"""
    gs = _make_gs(equips=['精密拆装扳手'])
    gs.prep_anchored = True
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert out.placed
    assert gs.equips.value == ['精密拆装扳手', _ITEM, _ITEM], \
        '精密在场不拦炉效果条目,库尾照常追加 2 件'
    assert out.effects == (
        f'advisor_unlock:{_CARD}:青雀',
        f'named_equip_grant:{_ITEM}(placed=True)',
        f'named_equip_grant:{_ITEM}(placed=True)',
    ), '效果串恒 3 条全 placed=True(非 fail-closed 档)'
    assert rows_sink.kinds() == [], '精密在场零申报行(gate 恒 None)'


def test_qiongyu_qingque_unobserved_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 效果条目2 原语拒落零写 + 效果串仍
    逐件登记(placed=False ×2,拒落可审计);顾问解锁效果条目不受扰照写(equips
    观察态与解锁域零耦合);零申报行(拒落档 = 原语既有语义静默档)。"""
    gs = _make_gs()
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'advisor_unlock:{_CARD}:青雀',
        f'named_equip_grant:{_ITEM}(placed=False)',
        f'named_equip_grant:{_ITEM}(placed=False)',
    ), '效果串恒 3 条,炉效果条目逐件 placed=False 拒落可审计'
    assert gs.unlocked_experts.value == ('青雀',), '解锁效果条目照写(域零耦合)'
    assert gs.equips.value is None, '效果条目2 拒落零写'
    assert gs.write_seq - seq_before == 1, '写数恰 1 = 解锁写(拒落零写)'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'


def test_qiongyu_qingque_double_advisor_dedup(rows_sink: _RowSink) -> None:
    """双顾问去重锁(同锁跨卡/同卡两形态):同局先拿摸个鱼吧I(同 advisor
    解锁青雀)再拿本卡 → 解锁只增去重仍恰单份(去重命中零写早退,写数恰
    3 = 注册 1 + 炉效果条目 2);本卡重复拿取 → 解锁幂等单份,效果分支照走零
    幂等闸(工厂幂等不设防申报:每次获得各发 count 件)。"""
    gs = _make_gs(equips=[])
    gs.prep_anchored = True
    gain_invest_strategy(gs, None, '摸个鱼吧I', rand=False, sig=_LSIG)
    assert gs.unlocked_experts.value == ('青雀',), '首拿解锁单份'
    seq_mid = gs.write_seq
    gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert gs.unlocked_experts.value == ('青雀',), \
        '跨卡双顾问解锁去重单份(只增去重零重复追加)'
    assert gs.write_seq - seq_mid == 3, \
        '写数恰 3 = 注册 1 + 炉效果条目 2(解锁去重命中零写早退)'
    seq_late = gs.write_seq
    gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG)
    assert gs.unlocked_experts.value == ('青雀',), \
        '同卡重复拿取解锁幂等单份'
    assert gs.equips.value == [_ITEM, _ITEM, _ITEM, _ITEM], \
        '效果分支照走零幂等闸(每次获得各发 2 件,工厂幂等不设防申报)'
    assert gs.write_seq > seq_late, '持卡面去重注册跳写,效果分支照常'
    assert rows_sink.kinds() == [], '去重路径零申报行'
