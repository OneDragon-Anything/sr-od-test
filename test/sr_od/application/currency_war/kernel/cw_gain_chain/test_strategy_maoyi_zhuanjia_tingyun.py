"""贸易专家:停云(id 360401)顾问族混发卡组合登记行锁(镜像 src =
kernel/cw_gain_effects.py 的 ``PICK_INVEST_EFFECTS['贸易专家:停云']`` 组合
登记行 + kernel/cw_investments.py 的 STRATEGY_GRANTS 同卡条目 items_immediate
补缺 + cw_gain_effects._STRATEGY_BOX_GRANTS 同名行;按被测方法拆目录规范落位
——test_gain_chain.py 超线冻结禁追加,先例 = 姊妹顾问卡 test_strategy_
qiongyu_zhuanjia_qingque.py〔advisor+具名授予联立〕与武装突入
test_strategy_wuzhuang.py〔多箱逐件〕、精密拆装·银 test_strategy_compose_
grant_jingmi_caizhuang_yin.py〔扳手效果条目门表轻断言〕)。

测试面依据 = 原稿锁面
原稿锁面§4 锁面(卡面官方原文:
「获得专家顾问【停云】，并使其在本局游戏中加入商店。并获得4个【简易武装箱】、
【精密拆装扳手】和10金币。」——四效果条目:顾问解锁效果条目 = 登记面 advisor=True 获得
链自动;箱×4 = 登记面 items_immediate 四元素元组 + 镜像表同名行;扳手×1 =
具名装备工厂 rand=False 确定发放;金币效果条目 10 金 = STRATEGY_ECONOMY 已登记,状态副本
写端缺口维持族级待办 = 零金写申报):

- 联立效果串全序:恰 6 条 = advisor_unlock 1 → box_grant 4 →
  named_equip_grant 1(获得链 advisor 效果条目先于效果体分派,组合条目序 =
  卡文语序箱→扳手);
- ×4 = 四元素元组逐件独立落位(非全有全无):席满变体锁箱 1 溢出落位 +
  箱 2..4 溢出位被占零写留证三态;
- 精密金面前置不辖本效果条目:发放物 = 精密扳手本体 ∉ 门表(门表只挂基础拆装
  扳手),精密在场二次持有照常入栏零自我拦截(T-145 收窄判据回归);
- 拒落负支:equips 未观察 → 扳手效果条目零写 placed=False 可审计,箱条目/解锁效果条目
  域零耦合照写。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EQUIP_ACQUIRE_CONSEQUENCES,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_OVERFLOW_TAKEN,
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    _NAMED_EQUIP_PRECISE_GATES,
    _STRATEGY_BOX_GRANTS,
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
    STRATEGY_ECONOMY,
    STRATEGY_GRANTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')

_CARD = '贸易专家:停云'
_BOX = '简易武装箱'
_WRENCH = '精密拆装扳手'
_SEED = 20261214


def _make_gs(*, bench_units: int = 1,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供拒落分支;bench_units = 预置
    入席单位数,席满变体传 9)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots = [BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1))
             for _ in range(bench_units)]
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


def test_maoyi_tingyun_row_single_source() -> None:
    """登记面单一源:GRANTS 条目(顾问效果条目 + 箱×4 元组)已登记 + 镜像表同名行
    与登记面 items 逐对相等 + PICK 组合键已登记 + 金币效果条目经济注册行已登记(零金写
    = 状态副本写端缺口维持族级待办的申报前提,破前提时主锁零金写断言语义变化);
    箱/扳手均 ∉ 后果表(获得零级联 = 「效果串恒 6 条」前提守卫);扳手本体
    ∉ 精密门表(gate 恒 None 注册面结构前提)。"""
    assert _CARD in PICK_INVEST_EFFECTS, '组合登记行已登记'
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.advisor is True and grant.chars_immediate == ('停云',), \
        '顾问解锁登记面镜像(advisor 型,入池可刷零新增登记)'
    assert grant.items_immediate == (_BOX,) * 4, '箱×4 卡文直读(元素重复约定)'
    assert _STRATEGY_BOX_GRANTS[_CARD] == (_BOX,) * 4, \
        '镜像表同名行与登记面 items 逐对相等'
    assert STRATEGY_ECONOMY[_CARD].instant_gold == 10, \
        '金币效果条目经济注册行已登记(状态副本写端缺口维持族级待办,零金写申报前提)'
    assert _BOX not in EQUIP_ACQUIRE_CONSEQUENCES \
        and _WRENCH not in EQUIP_ACQUIRE_CONSEQUENCES, \
        '箱/扳手 ∉ 后果表(效果串恒 6 条前提)'
    assert _WRENCH not in _NAMED_EQUIP_PRECISE_GATES, \
        '扳手本体 ∉ 精密门表(gate 恒 None,零自我拦截)'


def test_maoyi_tingyun_chain_full_order(rows_sink: _RowSink) -> None:
    """行为主锁(联立效果串全序):gain_invest_strategy 全链(rand=False,
    固定种子)→ 注册入表 + 解锁写 + 4 箱逐件落席 + 扳手入栏;效果串全序恰
    6 条 = advisor_unlock 1 → box_grant 4 → named_equip_grant 1(advisor
    效果条目先于效果体分派,组合条目序 = 卡文语序箱→扳手);确定发放走确定面;
    写数恰 7 = 注册 1 + 解锁 1 + 箱条目 4 + 扳手 1(②段账本登记 session=None
    跳过);rng 零消费;零金写(instant_gold 经济聚合面已登记,状态副本写端缺口
    维持族级待办的申报不对称);板面域零写;正常路径零申报行。"""
    gs = _make_gs(bench_units=1, equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    rng0 = random.Random(_SEED)
    rng_state0 = rng0.getstate()
    out = gain_invest_strategy(gs, None, _CARD, rand=False, sig=_LSIG,
                               rng=rng0)
    assert out.placed
    assert gs.active_strategies.value == [_CARD], '注册入表'
    assert out.effects == (
        f'advisor_unlock:{_CARD}:停云',
        *(f'box_grant:{_BOX}(placed=True)',) * 4,
        f'named_equip_grant:{_WRENCH}(placed=True)',
    ), f'联立效果串全序恰 6 条(解锁→逐箱→扳手): {out.effects}'
    assert gs.unlocked_experts.value == ('停云',), '专家解锁权威写'
    assert gs.unlocked_experts.evidence == \
        f'on_strategy_gained:{_CARD}#expert_unlock', \
        '解锁写 evidence 前缀(获得链 advisor 效果条目申报形态)'
    assert gs.unlocked_experts.source == 'logic', '解锁确定事实走确定面'
    slots = gs.bench.value.slots
    assert sum(1 for s in slots if s.kind == 'supply_box') == 4, \
        '备战空槽 supply_box 恰 4'
    assert sum(1 for s in slots
               if getattr(s, 'item', None) == _BOX) == 4, \
        '落席箱身份 = 道具名(名面真值)'
    assert gs.bench.source == 'logic', '箱条目确定发放走确定面'
    assert gs.equips.value == [_WRENCH], '扳手入栏恰 1 件'
    assert gs.equips.evidence.startswith('pick_invest_named_equip'), \
        '扳手效果条目写端 evidence 前缀(原语内追加后缀,前缀匹配防假红)'
    assert gs.write_seq - seq_before == 7, \
        '写数恰 7 = 注册 1 + 解锁 1 + 箱条目 4 + 扳手 1'
    assert rng0.getstate() == rng_state0, '零随机面(rng 不消费)'
    assert gs.gold.value is None, \
        '零金写(instant_gold 经济聚合面已登记,状态副本写端族级待办的申报不对称)'
    assert len(bench_units_of(gs)) == 1, '单位域不变(道具非角色)'
    assert gs.deployed.value is None, 'deployed 未观察保持未写'
    assert rows_sink.kinds() == [], '正常路径零申报行'


def test_maoyi_tingyun_precision_gate_not_inherited(
        rows_sink: _RowSink) -> None:
    """精密前置不辖本效果条目(收窄判据回归):已持精密扳手 → 本卡选卡扳手效果条目照常
    发放二次持有零申报行(金面规则只辖「再获得拆装扳手」,发放精密自身
    gate 恒 None——误挂 gate/误挂持精密拒发在此红)。"""
    gs = _make_gs(bench_units=1, equips=[_WRENCH])
    gs.prep_anchored = True
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'advisor_unlock:{_CARD}:停云',
        *(f'box_grant:{_BOX}(placed=True)',) * 4,
        f'named_equip_grant:{_WRENCH}(placed=True)',
    ), '效果串恒 6 条全 placed=True(非 fail-closed 档)'
    assert gs.equips.value == [_WRENCH, _WRENCH], \
        '精密在场不拦扳手效果条目,库尾照常追加二次持有'
    assert rows_sink.kinds() == [], '精密在场零申报行(gate 恒 None)'


def test_maoyi_tingyun_unobserved_equips_reject_auditable(
        rows_sink: _RowSink) -> None:
    """拒落负支:equips 未观察(None)直构 → 扳手效果条目原语拒落零写 + 效果串仍
    登记(placed=False,拒落可审计);箱条目/解锁效果条目与 equips 观察态域零耦合
    照写;零申报行(拒落档 = 原语既有语义静默档)。"""
    gs = _make_gs(bench_units=1)
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'advisor_unlock:{_CARD}:停云',
        *(f'box_grant:{_BOX}(placed=True)',) * 4,
        f'named_equip_grant:{_WRENCH}(placed=False)',
    ), '效果串恒 6 条,扳手效果条目 placed=False 拒落可审计'
    assert gs.unlocked_experts.value == ('停云',), '解锁效果条目照写(域零耦合)'
    assert sum(1 for s in gs.bench.value.slots
               if getattr(s, 'item', None) == _BOX) == 4, \
        '箱条目照写(域零耦合)'
    assert gs.equips.value is None, '扳手效果条目拒落零写'
    assert gs.write_seq - seq_before == 5, \
        '写数恰 5 = 解锁写 + 箱条目 4(拒落零写)'
    assert rows_sink.kinds() == [], '拒落档零申报行(非 fail-closed 档)'


def test_maoyi_tingyun_bench_full_x4_independent(
        rows_sink: _RowSink) -> None:
    """席满 ×4 逐件独立三态(非全有全无):bench 满 9 → 箱 1 溢出落位
    (overflow_card 身份 = 道具名)+ 箱 2..4 溢出位被占零写 + DEFECT 留证
    ×3;扳手效果条目不受备战域影响照常入栏。"""
    gs = _make_gs(bench_units=9, equips=[])
    gs.prep_anchored = True
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_LSIG)
    assert effects == (
        f'advisor_unlock:{_CARD}:停云',
        f'box_grant:{_BOX}(placed=True)',
        *(f'box_grant:{_BOX}(placed=False)',) * 3,
        f'named_equip_grant:{_WRENCH}(placed=True)',
    ), '箱 1 溢出落位 + 箱 2..4 溢出位被占 + 扳手照发'
    assert gs.overflow_warning.value is True, '席满溢出落位(告警在场)'
    assert gs.overflow_card.value == _BOX, '溢出位身份 = 道具名'
    assert gs.equips.value == [_WRENCH], '扳手效果条目不受备战域影响'
    assert gs.write_seq - seq_before == 4, \
        '写数恰 4 = 解锁 1 + 溢出两字段 2 + 扳手 1(被占零写)'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN] * 3, \
        '箱 2..4 溢出位被占零写留证 ×3(逐件独立,禁全有全无)'
