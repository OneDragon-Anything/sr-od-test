"""策略延时发放到点原语测试(镜像 src = kernel/cw_gain_chain.py 的
discharge_due_strategy_grants)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 4(kernel 原语
面;sim 窗口接线与世界真值归 sim/cw_sim_backend 侧文件)+ 裁决点 3/4
默认案。直构形态先例 = 同目录 test_check_strategy_battle_grants.py:
- 未到点(remaining > 0)零发放零写;
- 到点(remaining <= 0)→ 装备腿入栏 + 弹除 + 效果串
  delayed_grant:<item>(placed=…)+ 队列回写 evidence strategy_grant_due
  (姊妹双卡参数化:人才激励 / 人才激励+,T-107 批扩面);
- 分道判据(monkeypatch 临时占席道具条目)→ gain_bench_item 落席;
- 许诺特权 = 占席分道首个真实注册条目(真成员回归锁:备战落位/席满
  溢出落位/溢出位被占零写留证,三态全真成员直测);
- 发放拒落(equips 未观察)→ 零写 + 条目仍弹除(到期即消费)+ 回写行
  留存证据;
- 注册表漂移防御(队列卡名查行失败)→ 零发放 + 条目保留。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_gain_chain
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    DEFECT_OVERFLOW_TAKEN,
    discharge_due_strategy_grants,
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
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '人才激励'
_ITEM = '员工投影仪'

_XUNUO = '许诺特权'
_XUNUO_ITEM = '特权武装箱'

_XIANKUI = '先亏后盈'
_XIANKUI_ITEM = '简易武装箱'


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


def _empty_slots(n: int = 9) -> list[BenchSlot]:
    return [BenchSlot(kind='empty')] * n


def _gs(*, equips: list[str] | None, bench_slots: list[BenchSlot] | None,
        queue: tuple) -> GameState:
    """equips/bench/队列直置(equips=None / bench_slots=None = 未观察
    拒落域)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True   # 确定发放 = 锁确定面写通道(先例同款)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       evidence='t:equips', sig=_LSIG)
    if bench_slots is not None:
        gs.observe(gs.bench, BenchView(slots=bench_slots, capacity=9),
                   sig=_SIG_OBS)
    if queue:
        gs.write_logic(gs.pending_strategy_grants, queue,
                       produced_by='test-seed', evidence='t:queue',
                       sig=_LSIG)
    return gs


def test_not_due_zero_grant_zero_write() -> None:
    """未到点:remaining 全 > 0 → 零发放零写(队列原值,装备栏零动)。"""
    gs = _gs(equips=[], bench_slots=None, queue=((_CARD, 2),))
    seq_before = gs.write_seq
    assert discharge_due_strategy_grants(gs, rand=False, sig=_LSIG) == ()
    assert gs.pending_strategy_grants.value == ((_CARD, 2),), '未到点被弹除'
    assert gs.equips.value == [], '未到点误入栏'
    assert gs.write_seq == seq_before, '未到点出现写行'


@pytest.mark.parametrize('card', [_CARD, '人才激励+'])
def test_due_grants_equipment_ejects_entry(card: str) -> None:
    """到点发放真值(姊妹双卡参数化,逐名经真实注册表查行):remaining
    = 0 → 装备腿尾追入栏 + 条目弹除 + 效果串 delayed_grant:<item>
    (placed=True)+ 队列回写 evidence strategy_grant_due(确定面),
    evidence 值含触发卡名(同款发放物经卡名可分)。"""
    gs = _gs(equips=[], bench_slots=None, queue=((card, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_ITEM}(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [_ITEM], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert gs.equips.source == 'logic' \
        and gs.pending_strategy_grants.source == 'logic', '确定发放走确定面'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        f'队列回写 evidence: {gs.pending_strategy_grants.evidence}'
    assert gs.equips.evidence == f'strategy_grant_due:{card}#equip', \
        f'发放 evidence: {gs.equips.evidence}'


def test_due_routing_bench_item_branch(monkeypatch) -> None:
    """分道判据(锁机制):注册表临时条目发放物 ∈ 占席词表 → 占席道具
    腿落席(带名槽件),不走装备栏——两词表归属即分道,零第二源。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        StrategyDelayedGrant,
    )
    monkeypatch.setitem(
        cw_gain_chain.STRATEGY_DELAYED_GRANTS, '占席测试卡',
        StrategyDelayedGrant(id='000000', delay_nodes=1,
                             item='简易武装箱'))
    gs = _gs(equips=[], bench_slots=_empty_slots(),
             queue=(('占席测试卡', 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == ('delayed_grant:简易武装箱(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [], '占席道具误入装备栏'
    slots = gs.bench.value.slots
    landed = [s for s in slots if s is not None and s.kind == 'supply_box']
    assert len(landed) == 1 and landed[0].item == '简易武装箱', '未落席'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'


def test_grant_rejected_zero_write_entry_still_ejected() -> None:
    """发放拒落(equips 未观察直构域):零写 + 条目仍弹除(到期即消费,
    裁决点 4 默认案 = 环境通道弹除语义同构)+ 回写行留存证据(世界偏穷
    有界:每条至多 1 件)。"""
    gs = _gs(equips=None, bench_slots=None, queue=((_CARD, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_ITEM}(placed=False)',), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (), '拒落条目未弹除'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        '弹除回写行缺留存证据'


def test_registry_miss_defense_retains_entry() -> None:
    """注册表漂移防御(正常不可达):队列卡名查注册表失败 → 零发放 +
    条目保留不弹除(零写,队列原值)。"""
    gs = _gs(equips=[], bench_slots=None, queue=(('未注册的卡', 0),))
    seq_before = gs.write_seq
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (), '漂移条目误发放'
    assert gs.pending_strategy_grants.value == (('未注册的卡', 0),), \
        '漂移条目被弹除'
    assert gs.write_seq == seq_before, '漂移分支出现写行'


# ============================================================ 占席分道
# 真成员回归锁(许诺特权 = BENCH_ITEM_NAMES 分道首个真实注册条目;
# 上方 test_due_routing_bench_item_branch 仅以 monkeypatch 假想条目
# 锁过分道机制,真成员占席道具全落位三态由下方三锁直测)


def test_due_bench_item_real_member_places_bench(
        rows_sink: _RowSink) -> None:
    """许诺特权到点 → 备战空槽落位(真成员主态):supply_box 槽件带名
    落席 ∧ 条目弹除 ∧ 效果串 delayed_grant:特权武装箱(placed=True)
    ∧ 确定发放走确定面 ∧ 落位写 evidence = strategy_grant_due:许诺
    特权#place ∧ 正常路径零留证。真成员直测锁分道真值(monkeypatch
    分道锁只证机制不证真成员词表归属)。"""
    gs = _gs(equips=[], bench_slots=_empty_slots(),
             queue=((_XUNUO, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_XUNUO_ITEM}(placed=True)',), \
        f'效果串: {effects}'
    slots = gs.bench.value.slots
    landed = [s for s in slots if s is not None and s.kind == 'supply_box']
    assert len(landed) == 1 and landed[0].item == _XUNUO_ITEM, \
        f'特权武装箱未落席: {slots}'
    assert gs.equips.value == [], '占席道具误入装备栏'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert gs.bench.source == 'logic', '确定发放走确定面'
    assert gs.bench.evidence == f'strategy_grant_due:{_XUNUO}#place', \
        f'落位 evidence: {gs.bench.evidence}'
    assert rows_sink.kinds() == [], '正常落位零留证'


def test_due_bench_item_real_member_bench_full_overflow(
        rows_sink: _RowSink) -> None:
    """许诺特权到点席满 → 溢出落位两字段(道具与角色同款溢出语义,
    2026-09-24 实机真值):overflow_warning=True ∧ overflow_card =
    特权武装箱(身份 = 道具名)∧ 备战席零变动 ∧ 效果串 placed=True
    ∧ 零留证(既定语义)。"""
    gs = _gs(equips=[],
             bench_slots=[BenchSlot(kind='unit',
                                    unit=Unit(char_id=f'填席{i}', star=1))
                          for i in range(9)],
             queue=((_XUNUO, 0),))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_XUNUO_ITEM}(placed=True)',), \
        f'效果串: {effects}'
    assert gs.overflow_warning.value is True, '席满溢出告警未写'
    assert gs.overflow_card.value == _XUNUO_ITEM, \
        f'溢出位身份应为道具名: {gs.overflow_card.value!r}'
    slots = gs.bench.value.slots
    assert all(s is not None and s.kind == 'unit' for s in slots), \
        '备战席零变动(道具落溢出位非备战槽)'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert rows_sink.kinds() == [], '席满溢出落位是既定语义,零留证'


def test_due_bench_item_real_member_overflow_taken(
        rows_sink: _RowSink) -> None:
    """许诺特权到点席满 ∧ 溢出位已被占 → 零写 + 留证(DEFECT_OVERFLOW_
    TAKEN)+ 条目仍弹除(到期即消费,该件世界性丢失留证于 defect 行):
    bench/overflow 两域零写、效果串 placed=False。"""
    gs = _gs(equips=[],
             bench_slots=[BenchSlot(kind='unit',
                                    unit=Unit(char_id=f'填席{i}', star=1))
                          for i in range(9)],
             queue=((_XUNUO, 0),))
    gs.write_logic(gs.overflow_warning, True, produced_by='test-seed',
                   evidence='t:ovf', sig=_LSIG)
    gs.write_logic(gs.overflow_card, '先到的道具', produced_by='test-seed',
                   evidence='t:ovf', sig=_LSIG)
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_XUNUO_ITEM}(placed=False)',), \
        f'效果串: {effects}'
    assert gs.overflow_card.value == '先到的道具', '溢出位被覆写'
    assert all(s is not None and s.kind == 'unit'
               for s in gs.bench.value.slots), '备战席出现写'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], \
        f'零写留证行: {rows_sink.kinds()}'


# ============================================================ count 循环
# 真成员回归锁(先亏后盈 count=2 = 数量 >1 首例:同拍队列双条目,到点
# 逐条独立发放/独立席满判定——上面三态锁均为单条目,本区锁 count>1 形)


def test_due_count2_places_two_boxes_same_window(
        rows_sink: _RowSink) -> None:
    """先亏后盈同窗双条目同拍发放 2 件(备战空席):两箱各落一槽
    ∧ 弹除 ×2(队列清空)∧ 效果串恰两条 placed=True。"""
    gs = _gs(equips=[], bench_slots=_empty_slots(),
             queue=((_XIANKUI, 0), (_XIANKUI, 0)))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_XIANKUI_ITEM}(placed=True)',
                       f'delayed_grant:{_XIANKUI_ITEM}(placed=True)'), \
        f'效果串(两件): {effects}'
    landed = [s for s in gs.bench.value.slots
              if s is not None and s.kind == 'supply_box']
    assert len(landed) == 2, f'两箱未齐落: {gs.bench.value.slots}'
    assert all(s.item == _XIANKUI_ITEM for s in landed), '落位身份漂移'
    assert gs.equips.value == [], '占席道具误入装备栏'
    assert gs.pending_strategy_grants.value == (), '到期条目未全弹除'
    assert rows_sink.kinds() == [], '正常落位零留证'


def test_due_count2_full_bench_overflow_then_overflow_taken(
        rows_sink: _RowSink) -> None:
    """先亏后盈双条目席满两态(逐条独立判定):首条溢出落位(两字段,
    overflow_card = 简易武装箱)、次条溢出位已被占 → 零写留证
    (DEFECT_OVERFLOW_TAKEN);两条目同拍全弹除(到期即消费),效果串
    placed=True + placed=False 各一条——占席语义天然支持「一箱溢出
    一箱丢失」的分条异态。"""
    gs = _gs(equips=[],
             bench_slots=[BenchSlot(kind='unit',
                                    unit=Unit(char_id=f'填席{i}', star=1))
                          for i in range(9)],
             queue=((_XIANKUI, 0), (_XIANKUI, 0)))
    effects = discharge_due_strategy_grants(gs, rand=False, sig=_LSIG)
    assert effects == (f'delayed_grant:{_XIANKUI_ITEM}(placed=True)',
                       f'delayed_grant:{_XIANKUI_ITEM}(placed=False)'), \
        f'效果串(溢出+丢失两态): {effects}'
    assert gs.overflow_warning.value is True, '席满溢出告警未写'
    assert gs.overflow_card.value == _XIANKUI_ITEM, \
        f'溢出位身份应为道具名: {gs.overflow_card.value!r}'
    assert all(s is not None and s.kind == 'unit'
               for s in gs.bench.value.slots), '备战席出现写'
    assert gs.pending_strategy_grants.value == (), '到期条目未全弹除'
    assert rows_sink.kinds() == [DEFECT_OVERFLOW_TAKEN], \
        f'溢出位占零写留证行: {rows_sink.kinds()}'
