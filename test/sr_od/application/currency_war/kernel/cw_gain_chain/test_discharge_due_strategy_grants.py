"""策略延时发放到点原语测试(镜像 src = kernel/cw_gain_chain.py 的
discharge_due_strategy_grants)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 4(kernel 原语
面;sim 窗口接入调用与状态副本里的值归 sim/cw_sim_backend 侧文件)+ 裁决点 3/4
默认案。直构形态先例 = 同目录 test_check_strategy_battle_grants.py:
- 未到点(remaining > 0)零发放零写;
- 到点(remaining <= 0)→ 装备效果条目入栏 + 弹除 + 效果串
  delayed_grant:<item>(placed=…)+ 队列回写 evidence strategy_grant_due
  (姊妹双卡参数化:人才激励 / 人才激励+,T-107 批扩面);
- 分道判据(monkeypatch 临时占席道具条目)→ gain_bench_item 落席;
- 许诺特权 = 占席分道首个真实注册条目(真成员回归锁:备战落位/席满
  溢出落位/溢出位被占零写留证,三态全真成员直测);
- 好运令牌·银 = 装备分道真成员回归锁(延时-only 载体下装备分道首例,
  T-146 批:到点 equips 追加好运令牌 + 弹除 + 效果串;栏未观察 →
  拒落零写 + 条目仍弹除 + 回写行留存证据);
- 发放拒落(equips 未观察)→ 零写 + 条目仍弹除(到期即消费)+ 回写行
  留存证据;
- 注册表漂移防御(队列卡名查行失败)→ 零发放 + 条目保留;
- 确定行零扰动(是钻石总会发光扩形批 T-148:锁「扩形不越权」)→ 族
  确定行(现值六行,含周期 repeat 行)发放路径 rng 前后状态零变;
- 是钻石总会发光 = 随机 choice-set 采样行首例(sim 直构注入固定 rng):
  两 seed 分别命中红钻/蓝钻、队列弹除、效果串随选中物、发放子链
  rand=True 随机态通道 + 队列弹除行确定面 + 同 seed 重跑逐位一致;
- 回收计划 = 随机类别池行首例(designs/T-237-huishou-jihua.md §4 锁 3,
  T-148 批扩形同构):两固定 seed 分别命中不同简易件、采样 ∈ 简易池
  派生集禁手抄清单、发放子链 rand=True 随机态通道 + 队列弹除行确定面
  + 同 seed 重跑逐位一致;类别池空 = 注册表漂移防御(池随注册表传导,
  import 期哨在先,运行期兜底)→ 零发放 + 条目保留。
- 好运令牌·彩 = 周期型 repeat 行(周期型首例,REVIEW-T374.md §4 锁 4):
  到点发放(无论落位成败)后同参重排队,队列长度恒 1 自续至局终——
  拒落亦重排(周期自续贴卡面「每累计……获得」语义);既有单发行
  弹除即止零变。
"""
from __future__ import annotations

import random

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

_SHIZUAN = '是钻石总会发光'

_HUISHOU = '回收计划'


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
    assert discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG) == ()
    assert gs.pending_strategy_grants.value == ((_CARD, 2),), '未到点被弹除'
    assert gs.equips.value == [], '未到点误入栏'
    assert gs.write_seq == seq_before, '未到点出现写行'


@pytest.mark.parametrize(('card', 'item'), [
    (_CARD, _ITEM),
    ('人才激励+', _ITEM),
    ('好运令牌·银', '好运令牌'),
])
def test_due_grants_equipment_ejects_entry(card: str, item: str) -> None:
    """到点发放真值(真注册装备分道成员参数化,逐名经真实注册表查行):
    remaining
    = 0 → 装备效果条目尾追入栏 + 条目弹除 + 效果串 delayed_grant:<item>
    (placed=True)+ 队列回写 evidence strategy_grant_due(确定面),
    evidence 值含触发卡名(同款发放物经卡名可分;好运令牌·银 = 卡名
    与发放物异名,效果串按物名/evidence 按卡名各归其位)。"""
    gs = _gs(equips=[], bench_slots=None, queue=((card, 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == (f'delayed_grant:{item}(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [item], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
    assert gs.equips.source == 'logic' \
        and gs.pending_strategy_grants.source == 'logic', '确定发放走确定面'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        f'队列回写 evidence: {gs.pending_strategy_grants.evidence}'
    assert gs.equips.evidence == f'strategy_grant_due:{card}#equip', \
        f'发放 evidence: {gs.equips.evidence}'


def test_due_routing_bench_item_branch(monkeypatch) -> None:
    """分道判据(锁机制):注册表临时条目发放物 ∈ 占席词表 → 占席道具
    效果条目落席(带名槽件),不走装备栏——两词表归属即分道,零第二源。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        StrategyDelayedGrant,
    )
    monkeypatch.setitem(
        cw_gain_chain.STRATEGY_DELAYED_GRANTS, '占席测试卡',
        StrategyDelayedGrant(id='000000', delay_nodes=1,
                             item='简易武装箱'))
    gs = _gs(equips=[], bench_slots=_empty_slots(),
             queue=(('占席测试卡', 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:简易武装箱(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == [], '占席道具误入装备栏'
    slots = gs.bench.value.slots
    landed = [s for s in slots if s is not None and s.kind == 'supply_box']
    assert len(landed) == 1 and landed[0].item == '简易武装箱', '未落席'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'


def test_grant_rejected_zero_write_entry_still_ejected() -> None:
    """发放拒落(equips 未观察直构域):零写 + 条目仍弹除(到期即消费,
    裁决点 4 默认案 = 环境通道弹除语义同构)+ 回写行留存证据(状态副本偏穷
    有界:每条至多 1 件)。"""
    gs = _gs(equips=None, bench_slots=None, queue=((_CARD, 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == (f'delayed_grant:{_ITEM}(placed=False)',), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (), '拒落条目未弹除'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        '弹除回写行缺留存证据'


def test_due_haoyun_equips_unobserved_reject_ejected_with_evidence() -> None:
    """好运令牌·银 栏未观察拒落(装备分道新实成员的 placed=False 面,
    T-146 批):equips 未观察直构 → 零写(装备栏保持未观察)∧ 条目仍
    弹除(到期即消费)∧ 效果串 delayed_grant:好运令牌(placed=False)
    ∧ 弹除回写行留存 evidence——真成员查行经注册表 item 值(卡名与
    发放物异名,查行键 = 队列卡名),拒落语义与机制锁(上方通用锁)
    同构,本锁证新实成员在该分支零特例。"""
    gs = _gs(equips=None, bench_slots=None, queue=(('好运令牌·银', 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:好运令牌(placed=False)',), \
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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
    TAKEN)+ 条目仍弹除(到期即消费,该件状态副本丢失,留证于 defect 行):
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
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


# ============================================================ 随机 choice-set
# 采样行(是钻石总会发光,族内首个随机发放行,T-148 批)+ 确定行零扰动
# 回归(扩形不越权)


@pytest.mark.parametrize('card', [
    '人才激励', '人才激励+', '许诺特权', '先亏后盈', '好运令牌·银',
    '好运令牌·彩',
])
def test_deterministic_rows_rng_untouched(card: str) -> None:
    """确定行零扰动回归(锁「扩形不越权」):族内既有全部确定行到点
    发放路径不消费 rng——发放前后 rng.getstate 逐位相等,同 seed 下
    既有卡行为与 rng 消耗序列零变(本卡扩形只辖 choice-set 行,签名
    +rng 必传对确定行是零语义形参)。"""
    if card == '许诺特权' or card == '先亏后盈':
        gs = _gs(equips=[], bench_slots=_empty_slots(), queue=((card, 0),))
    else:
        gs = _gs(equips=[], bench_slots=None, queue=((card, 0),))
    rng = random.Random(7)
    state_before = rng.getstate()
    discharge_due_strategy_grants(
        gs, rand=False, rng=rng, sig=_LSIG)
    assert rng.getstate() == state_before, \
        f'{card} 确定行消费 rng(扩形越权)'


def test_due_choice_set_samples_both_diamonds_by_seed() -> None:
    """是钻石总会发光 到点采样发放(sim 直构注入固定 rng,随机 choice-set
    行首例):两固定 seed 分别命中红钻/蓝钻(seed 按实际 rng 流定向选取,
    ``rng.choice`` 序列均匀语义,禁值漂移断言)→ equips 尾追选中件 ∧
    队列弹除 ∧ 效果串 delayed_grant:<选中物>(placed=True)∧ 发放行走
    随机态面(采样行内部 rand=True,效果体含采样纪律)∧ 队列弹除行走
    确定面(队列只载卡名随调用方 rand 透传)∧ 同 seed 重跑逐位一致
    (同 seed 确定性)。"""
    for seed, expected in ((1, '红钻'), (0, '蓝钻')):
        assert random.Random(seed).choice(('红钻', '蓝钻')) == expected, \
            f'seed={seed} 定向失效(禁值漂移断言,须换 seed)'
        gs = _gs(equips=[], bench_slots=None, queue=((_SHIZUAN, 0),))
        effects = discharge_due_strategy_grants(
            gs, rand=False, rng=random.Random(seed), sig=_LSIG)
        assert effects == (f'delayed_grant:{expected}(placed=True)',), \
            f'seed={seed} 效果串: {effects}'
        assert gs.equips.value == [expected], \
            f'seed={seed} 装备栏: {gs.equips.value}'
        assert gs.equips.source == 'logic_rand', \
            f'seed={seed} 发放类效果条目未走随机态面(采样行 rand=True 覆盖失效)'
        assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
        assert gs.pending_strategy_grants.source == 'logic', \
            '队列弹除行未走确定面(只载卡名应随调用方 rand 透传)'
        assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
            f'队列回写 evidence: {gs.pending_strategy_grants.evidence}'
        assert gs.equips.evidence == \
            f'strategy_grant_due:{_SHIZUAN}#equip', \
            f'发放 evidence: {gs.equips.evidence}'


def test_due_choice_set_same_seed_bitwise_reproducible() -> None:
    """是钻石总会发光 同 seed 重跑逐位一致(sim 状态副本里的值确定性):
    两个独立构造的同构局,同 seed 各自发放 → 效果串/装备栏/队列终态
    逐位相等(采样在窗口内现掷,同 seed 重放同结果)。"""
    finals = []
    for _run in range(2):
        gs = _gs(equips=[], bench_slots=None, queue=((_SHIZUAN, 0),))
        effects = discharge_due_strategy_grants(
            gs, rand=False, rng=random.Random(0), sig=_LSIG)
        finals.append((effects, gs.equips.value,
                       gs.pending_strategy_grants.value))
    assert finals[0] == finals[1], f'同 seed 重跑漂移: {finals}'


# ============================================================ 随机类别池
# 采样行(回收计划,族内首个类别池发放行,T-237 批;直构形态 = 上方
# choice-set 采样锁同构,差异 = 池源 equips_by_category 注册表派生)


def test_due_category_pool_samples_by_seed() -> None:
    """回收计划 到点采样发放(随机类别池行首例,sim 直构注入固定 rng):
    两固定 seed 分别命中不同简易件(seed 按实际 rng 流定向选取,
    ``rng.choice`` 序列均匀语义,禁值漂移断言)→ equips 尾追选中件 ∧
    队列弹除 ∧ 效果串随选中物 ∧ 发放行走随机态面(类别池行内部
    rand=True,效果体含采样纪律)∧ 队列弹除行走确定面(队列只载卡名
    随调用方 rand 透传)∧ 同 seed 重跑逐位一致。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    pool = equips_by_category('简易')
    for seed in (1, 0):
        expected = random.Random(seed).choice(pool)
        gs = _gs(equips=[], bench_slots=None, queue=((_HUISHOU, 0),))
        effects = discharge_due_strategy_grants(
            gs, rand=False, rng=random.Random(seed), sig=_LSIG)
        assert effects == (f'delayed_grant:{expected}(placed=True)',), \
            f'seed={seed} 效果串: {effects}'
        assert gs.equips.value == [expected], \
            f'seed={seed} 装备栏: {gs.equips.value}'
        assert gs.equips.source == 'logic_rand', \
            f'seed={seed} 发放类效果条目未走随机态面(类别池行 rand=True 失效)'
        assert gs.pending_strategy_grants.value == (), '到期条目未弹除'
        assert gs.pending_strategy_grants.source == 'logic', \
            '队列弹除行未走确定面(只载卡名应随调用方 rand 透传)'
        assert gs.equips.evidence == \
            f'strategy_grant_due:{_HUISHOU}#equip', \
            f'发放 evidence: {gs.equips.evidence}'
    # 两 seed 异件(采样值域覆盖 8 件池 ≥2 成员的直接证据,禁值漂移)。
    assert random.Random(1).choice(pool) != random.Random(0).choice(pool), \
        'seed 定向失效(两 seed 同件,须换 seed)'


def test_due_category_pool_same_seed_bitwise_reproducible() -> None:
    """回收计划 同 seed 重跑逐位一致(类别池行状态副本里的值确定性,与
    choice-set 行同构面)。"""
    finals = []
    for _run in range(2):
        gs = _gs(equips=[], bench_slots=None, queue=((_HUISHOU, 0),))
        effects = discharge_due_strategy_grants(
            gs, rand=False, rng=random.Random(1), sig=_LSIG)
        finals.append((effects, gs.equips.value,
                       gs.pending_strategy_grants.value))
    assert finals[0] == finals[1], f'同 seed 重跑漂移: {finals}'


def test_due_category_pool_empty_defense_retains_entry(monkeypatch) -> None:
    """类别池空防御(注册表漂移运行期兜底,import 期哨在先,正常不可达):
    池 = equips_by_category(注册表 category 等值过滤)空 → 零发放 +
    log + 条目保留不弹除(查行失败防御同形,零写)。"""
    monkeypatch.setattr(cw_gain_chain, 'equips_by_category',
                        lambda category: ())
    gs = _gs(equips=[], bench_slots=None, queue=((_HUISHOU, 0),))
    seq_before = gs.write_seq
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == (), '池空条目误发放'
    assert gs.pending_strategy_grants.value == ((_HUISHOU, 0),), \
        '池空条目被弹除'
    assert gs.write_seq == seq_before, '池空分支出现写行'


# ============================================================ 周期 repeat 行
# (好运令牌·彩,周期型首例:到点发放后同参重排队,队列长度恒 1 自续;
# 单发行弹除即止语义零变,上方通用锁辖)


def test_due_repeat_row_requeues_same_params() -> None:
    """好运令牌·彩 到点发放后同参重排队(周期型首例主态):remaining=0 →
    装备效果条目入栏 + 效果串 delayed_grant:好运令牌(placed=True)+ 队列回写
    恰 (('好运令牌·彩', 4),)(同参 (卡名, delay_nodes=4),队列长度恒 1
    自续,非弹除清空)+ 弹除回写行 evidence strategy_grant_due + 发放行
    evidence 值含触发卡名(卡名与发放物异名各归其位)。"""
    gs = _gs(equips=[], bench_slots=None, queue=(('好运令牌·彩', 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:好运令牌(placed=True)',), \
        f'效果串: {effects}'
    assert gs.equips.value == ['好运令牌'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 4),), \
        f'重排队列: {gs.pending_strategy_grants.value}'
    assert gs.pending_strategy_grants.evidence == 'strategy_grant_due', \
        f'队列回写 evidence: {gs.pending_strategy_grants.evidence}'
    assert gs.equips.evidence == 'strategy_grant_due:好运令牌·彩#equip', \
        f'发放 evidence: {gs.equips.evidence}'


def test_due_repeat_row_requeues_on_reject() -> None:
    """好运令牌·彩 拒落亦重排(周期自续,裁决默认案;REVIEW-T374.md §3
    裁决点 2 附项):equips 未观察拒落(placed=False 零写)→ 条目仍以
    同参重排队(周期效果条目自续,贴卡面「每累计……获得」重复至局终语义,
    「拒落即止」备选与卡面冲突已裁否)——单发行同域弹除即止(上方
    test_grant_rejected_zero_write_entry_still_ejected)不被本行越权。"""
    gs = _gs(equips=None, bench_slots=None, queue=(('好运令牌·彩', 0),))
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:好运令牌(placed=False)',), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 4),), \
        f'拒落态重排队列: {gs.pending_strategy_grants.value}'
