"""全都要族选卡时点检查测试(cw_effect_inventory 分目录镜像;被测 =
check_strategy_take_all_supply,调用点行为面归 kernel/cw_action_report/
test_pick_supply.py)。

锁面(卡面 id 131001「下1个补给阶段选择后，额外获得所有未选择的角色
及装备」/ id 203501「下2个……」/ id 331701「补给阶段选择后……」无限定
词 = recurring,官方原文,语义权威版本 = 全都要族设计稿§2.3):
- 门序:未持卡零写零一次性标志位 / 持卡 ∧ 配额耗尽零写(计数一次性标志位) / 兜底形态(源
  None/空)零发放但配额照耗(A 案事件消耗制);
- 全捞主锁:全未选列逐列发放 + evidence 串 + 置一次性标志位(计数复合键)+ 消费
  即清 + 零 rng;
- 金卡特有:配额两拍(第 3 拍零写零消耗)+ 0 列空转拍 + 双持独立性;
- 彩卡特有:recurring 三拍各发各阶段(无早退)+ None 配额零配额格(sim
  形态零簿记正面断言/0 列空转零写零格耗)+ 三卡同持互不早退;
- 列形态:席满拒落不阻断 / 席未观察 / 孤儿簇仅装备腿;
- 归一失败:fail-closed 已解析件照常入账。
"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel import cw_action_report as ar_mod
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    STRATEGY_TAKE_ALL_ASSUMPTION_KEYS,
    check_strategy_take_all_supply,
)
from sr_od.application.currency_war.kernel.cw_events import (
    SupplyOption,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
)

# sig 形态 = 调用点真值:补给选定上报的调用方签名(动作 op 内构造)。
_SIG = ChannelSig(family='logic_action', actor='CwActionPickSupplyOp',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='test', mode='read')

_COLS = (
    SupplyOption(idx=0, char='希儿', equip='光能电池', extra_equips=()),
    SupplyOption(idx=1, char='', equip='折叠小刀', extra_equips=()),
)


def _take_all_gs(*, bench_entries: list[Unit] | None = None,
                 bench_unobserved: bool = False,
                 cards: tuple[str, ...] = ('全都要·银',),
                 unchosen: tuple[SupplyOption, ...] | None = _COLS,
                 latched: bool = False) -> GameState:
    """直构容器(bench/equips/持卡/未选集/一次性标志位按参;bench_unobserved = 域未
    观察形态;cards = () 未持卡;unchosen None = 无未选定案;latched = 银
    卡一次性标志位预置耗尽态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if not bench_unobserved:
        slots = [BenchSlot(kind='unit', unit=u) for u in (bench_entries or ())]
        slots += [BenchSlot(kind='empty')] * (BENCH_CAPACITY_DEFAULT
                                              - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots,
                                       capacity=BENCH_CAPACITY_DEFAULT),
                   sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if cards:
        gs.observe(gs.active_strategies, list(cards), sig=_SIG_OBS)
    if latched:
        gs.write_logic(gs.strategy_conditional_done,
                       ('take_all#全都要·银#1',),
                       produced_by='test-seed', sig=_SIG)
    if unchosen is not None:
        gs.write_logic(gs.unchosen_supply, unchosen, produced_by='test-seed',
                       sig=_SIG)
    return gs


def _take_all_run(gs: GameState) -> None:
    """检查函数运行(零采样腿,无 rng 注入面——固定 seed 零扰面本体)。"""
    check_strategy_take_all_supply(gs, _SIG)


def _bench_names(gs: GameState) -> list[str]:
    return [s.unit.char_id for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_take_all_gate_order_zero_write_arms() -> None:
    """门序锁·零写臂:未持卡 → 零写零一次性标志位(未持卡局全链零变化);持卡 ∧
    配额耗尽(银一次性标志位预置计数 1/配额 1)→ 零写(计数形封账,重复出口重入
    全静默)。"""
    for kwargs in ({'cards': ()}, {'latched': True}):
        gs = _take_all_gs(**kwargs)
        seq = gs.write_seq
        latch_before = gs.strategy_conditional_done.value
        _take_all_run(gs)
        assert gs.write_seq == seq, f'门序零写({kwargs})'
        assert gs.strategy_conditional_done.value == latch_before, \
            f'零一次性标志位写({kwargs})'


def test_take_all_fallback_round_consumes_quota_zero_grant() -> None:
    """门序锁·兜底形态臂(A 案事件消耗制):持卡 ∧ 一次性标志位未设 ∧ 源 None/空
    → 零发放(发放侧门)但配额照耗(选择事件即耗,首个 applied 出口含
    内容全未知兜底轮;漏记列由观察覆盖承接);耗尽残迹 = 计数复合键。"""
    for unchosen in (None, ()):
        gs = _take_all_gs(unchosen=unchosen)
        _take_all_run(gs)
        assert _bench_names(gs) == [], f'零发放(unchosen={unchosen!r})'
        assert gs.equips.value == [], '装备域零写'
        assert gs.strategy_conditional_done.value == \
            ('take_all#全都要·银#1',), \
            f'配额照耗(A 案簿记,unchosen={unchosen!r})'


def test_take_all_grants_all_columns_consume_clear_and_zero_rng(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全捞主锁:持卡 + 未选 2 列(列 0 = 角色+装备 / 列 1 = 孤儿簇仅装备)
    → 两列全发放:char 腿入席 1★、装备腿 owned 恒规范名;char 腿 evidence
    = ``strategy_take_all:<名>@1star``(效果串落点 = 随机写 evidence 本身);
    置一次性标志位 + 字段清(消费即清)+ 二次调用零写(重入幂等);rng 消费 = 0
    (「所有」= 零采样,采样入口计数桩断言零调用);发放面 = 随机态通道
    (bench/equips logic_rand),一次性标志位与消费即清 = 逻辑态。"""
    calls: list[str] = []

    def _counting_rng(tool: str, fallback) -> random.Random:
        calls.append(tool)
        return random.Random(1)

    monkeypatch.setattr(ar_mod, 'action_sampling_rng', _counting_rng)
    gs = _take_all_gs()
    _take_all_run(gs)
    assert _bench_names(gs) == ['希儿'], 'char 腿入席(全未选列逐列)'
    assert gs.equips.value == ['光能电池', '折叠小刀'], \
        f'装备腿按列内容入账: {gs.equips.value}'
    assert gs.bench.evidence == 'strategy_take_all:希儿@1star', \
        f'char 腿 evidence 串: {gs.bench.evidence}'
    assert gs.strategy_conditional_done.value == \
        ('take_all#全都要·银#1',), '置一次性标志位(计数复合键)'
    assert gs.unchosen_supply.value is None, '消费即清'
    assert calls == [], f'零 rng 消费(零采样): {calls}'
    assert gs.bench.source == 'logic_rand', 'char 腿随机态通道'
    assert gs.equips.source == 'logic_rand', '装备腿随机态通道'
    assert gs.unchosen_supply.source == 'logic', '消费即清 = 逻辑态'
    assert gs.strategy_conditional_done.source == 'logic', '一次性标志位 = 逻辑态'
    seq = gs.write_seq
    _take_all_run(gs)
    assert gs.write_seq == seq, '二次调用零写(一次性标志位门封账,重入幂等)'


def test_take_all_color_recurring_three_picks_each_stage() -> None:
    """彩卡特有·recurring 三拍锁(无配额域恒放行,recurring 无早退——与
    金卡第 3 拍零写对照互证):持彩卡连续三次选择,各拍发各阶段全未选列
    (各拍构造不同列,发放物 = 该拍快照内容);recurring 无封账面,done
    域三拍恒空(零 ``take_all#全都要·彩#*`` 键),消费即清逐拍;char-only
    列臂 = 第三拍零装备写零缺陷。"""
    stages = (
        _COLS,
        (SupplyOption(idx=0, char='停云', equip='折叠小刀',
                      extra_equips=()),),
        (SupplyOption(idx=0, char='刃', equip='', extra_equips=()),),
    )
    gs = _take_all_gs(cards=('全都要·彩',), unchosen=None)
    expect_bench: list[str] = []
    for no, stage in enumerate(stages, 1):
        gs.write_logic(gs.unchosen_supply, stage, produced_by='test-seed',
                       sig=_SIG)
        seq = gs.write_seq
        _take_all_run(gs)
        expect_bench += [c.char for c in stage if c.char]
        assert _bench_names(gs) == expect_bench, \
            f'拍 {no} 各发各阶段: {_bench_names(gs)}'
        assert tuple(gs.strategy_conditional_done.value or ()) == (), \
            f'拍 {no} 零配额格(recurring 无封账面)'
        assert gs.unchosen_supply.value is None, f'拍 {no} 消费即清'
        assert gs.write_seq != seq, f'拍 {no} 发生写(无早退)'
    assert gs.equips.value == ['光能电池', '折叠小刀', '折叠小刀'], \
        f'装备腿按拍累积: {gs.equips.value}'


def test_take_all_color_none_quota_zero_latch_arms() -> None:
    """彩 None 分支零配额格锁:持彩卡事件后 ``strategy_conditional_done`` 域
    无 ``take_all#全都要·彩#*`` 键(域恒空正面断言;银卡同形态对照得一
    笔无害簿记键,存量兜底锁互证)。兜底形态(源 None = sim 决策未接恒
    None 形态,S2 零簿记)零发放零簿记全链零写;0 列空转拍零写零副作用零
    格耗(银/金 0 列空转照耗格,本卡无格可耗)。"""
    gs = _take_all_gs(cards=('全都要·彩',), unchosen=None)
    seq = gs.write_seq
    _take_all_run(gs)
    assert tuple(gs.strategy_conditional_done.value or ()) == (), \
        '彩零簿记键(sim 形态正面断言,域恒空)'
    assert gs.write_seq == seq, '兜底形态全链零写(None 配额无消耗)'
    assert _bench_names(gs) == [] and gs.equips.value == [], '零发放'

    gs_empty = _take_all_gs(cards=('全都要·彩',), unchosen=())
    seq_empty = gs_empty.write_seq
    _take_all_run(gs_empty)
    assert gs_empty.write_seq == seq_empty, '0 列空转零写(零格耗)'
    assert tuple(gs_empty.strategy_conditional_done.value or ()) == (), \
        '零配额格'


def test_take_all_column_shapes_full_bench_and_unobserved() -> None:
    """列形态锁:席满(bench 满 9)→ 列 0 char 腿拒落零写且装备腿照发、
    后续列(列 1)不阻断;席未观察 → bench 保持 None 拒落(detail=
    'bench_unobserved' 语义)装备腿照发;孤儿簇列(char='')仅装备腿
    (主锁列 1 臂已覆盖,此臂显式单列)。"""
    full = [Unit(char_id=n, star=1) for n in
            ('希儿', '符玄', '花火', '停云', '刃', '杰帕德', '娜塔莎',
             '丹恒', '三月七')]
    gs_full = _take_all_gs(bench_entries=full)
    _take_all_run(gs_full)
    assert _bench_names(gs_full) == [u.char_id for u in full], '席满拒落零写'
    assert gs_full.equips.value == ['光能电池', '折叠小刀'], \
        '装备腿照发 + 后续列不阻断'
    assert gs_full.unchosen_supply.value is None, '消费即清'

    gs_unobs = _take_all_gs(bench_unobserved=True)
    _take_all_run(gs_unobs)
    assert gs_unobs.bench.value is None, '席未观察零写'
    assert gs_unobs.equips.value == ['光能电池', '折叠小刀'], '装备腿照发'

    gs_orphan = _take_all_gs(unchosen=(_COLS[1],))
    _take_all_run(gs_orphan)
    assert _bench_names(gs_orphan) == [], '孤儿簇列零角色腿'
    assert gs_orphan.equips.value == ['折叠小刀'], '仅装备腿'

    # 彩卡臂(None 配额走同发放分支,零配额格伴随):席满 char 腿拒落装备腿
    # 照发不阻断;席未观察同形。
    gs_color_full = _take_all_gs(cards=('全都要·彩',), bench_entries=full)
    _take_all_run(gs_color_full)
    assert _bench_names(gs_color_full) == [u.char_id for u in full], \
        '彩席满拒落零写'
    assert gs_color_full.equips.value == ['光能电池', '折叠小刀'], \
        '彩装备腿照发 + 后续列不阻断'
    assert tuple(gs_color_full.strategy_conditional_done.value or ()) == (), \
        '彩零配额格伴随'
    gs_color_unobs = _take_all_gs(cards=('全都要·彩',), bench_unobserved=True)
    _take_all_run(gs_color_unobs)
    assert gs_color_unobs.bench.value is None, '彩席未观察零写'
    assert gs_color_unobs.equips.value == ['光能电池', '折叠小刀'], \
        '彩装备腿照发'


def test_take_all_unresolved_name_fail_closed_resolved_survives() -> None:
    """归一失败锁:未选列件名归一失败('')→ 件禁猜 equips 值不变翻来源
    留证 fail-closed(kind = ``strategy_take_all_name_unresolved``),
    同列已解析件照常入账(不整批弃)。"""
    col = (SupplyOption(idx=0, char='', equip='乱码装备XYZ',
                        extra_equips=('折叠小刀',)),)
    gs = _take_all_gs(unchosen=col)
    consume_defect_sink()
    _take_all_run(gs)
    assert gs.equips.value == ['折叠小刀'], '已解析件照常入账'
    kinds = [r['kind'] for r in consume_defect_sink()]
    assert 'strategy_take_all_name_unresolved' in kinds, f'缺陷留证: {kinds}'
    assert gs.unchosen_supply.value is None, '消费即清'


def test_take_all_gold_quota_two_picks_then_exhausted() -> None:
    """金卡特有·配额两拍锁(门序计数三态 0/1/2)+ 全捞主锁金卡臂:持金卡
    (配额 2)两次选择各发该阶段全未选列(2 列构造形态;实机持卡局常态
    ≤1 列、下限 0 列——效果条目1 −2 压缩域,族级注记)一次性标志位 0→1→2;第 3 次选择
    零写零消耗(配额恰 2,非 ≥2 早退于第 2 拍——布尔形会把已耗 1 格误判
    耗尽 = 静默漏发,计数形统一已登记)。"""
    gs = _take_all_gs(cards=('全都要·金',), unchosen=None)
    gs.write_logic(gs.unchosen_supply, _COLS, produced_by='test-seed',
                   sig=_SIG)
    _take_all_run(gs)
    assert _bench_names(gs) == ['希儿'], '拍 1 全捞(char 腿)'
    assert gs.equips.value == ['光能电池', '折叠小刀'], '拍 1 装备腿'
    assert gs.strategy_conditional_done.value == \
        ('take_all#全都要·金#1',), '一次性标志位 0→1(计数复合键)'
    assert gs.unchosen_supply.value is None, '消费即清'
    gs.write_logic(gs.unchosen_supply, _COLS, produced_by='test-seed',
                   sig=_SIG)
    _take_all_run(gs)
    assert gs.strategy_conditional_done.value == (
        'take_all#全都要·金#1', 'take_all#全都要·金#2'), '一次性标志位 1→2'
    gs.write_logic(gs.unchosen_supply, _COLS, produced_by='test-seed',
                   sig=_SIG)
    seq = gs.write_seq
    _take_all_run(gs)
    assert gs.write_seq == seq, '第 3 拍零写(配额耗尽)'
    assert gs.strategy_conditional_done.value == (
        'take_all#全都要·金#1', 'take_all#全都要·金#2'), \
        '耗尽残迹 = done 键簿记留域(审计可考),零新追加'


def test_take_all_gold_empty_column_round_consumes_quota() -> None:
    """0 列空转拍锁(域规模下限局:效果条目1 −2 后在屏 1 列选定后未选 0 列):
    unchosen=() → 零发放 + 配额照耗(A 案事件消耗制 fail-visible 申报,
    域行为仍正确);两拍耗尽后第三拍零写。"""
    gs = _take_all_gs(cards=('全都要·金',), unchosen=())
    _take_all_run(gs)
    assert _bench_names(gs) == [] and gs.equips.value == [], '0 列零发放'
    assert gs.strategy_conditional_done.value == \
        ('take_all#全都要·金#1',), '配额照耗'
    _take_all_run(gs)
    assert gs.strategy_conditional_done.value == (
        'take_all#全都要·金#1', 'take_all#全都要·金#2'), '第二拍照耗'
    seq = gs.write_seq
    _take_all_run(gs)
    assert gs.write_seq == seq, '耗尽后零写(重入幂等)'


def test_take_all_multi_hold_independent_quotas() -> None:
    """同持独立性锁(存量双持锁扩三卡形):银(配额 1)+金(配额 2)+彩
    (None 无界)同持 → 同一选择事件三卡各发各的未选列、互不早退(内容
    同源重复 = 卡面叠加语义零判重闸,单槽场字段共享一次清);银一次性标志位满后金
    部分耗尽态(1/2)照常发放、彩恒放行(布尔形银键存在会误杀金卡剩余格
    = 静默漏发,计数形分卡独立计数;None 配额卡无耗尽态无此雷);彩全程
    零配额格,done 域仅 int 卡键。"""
    gs = _take_all_gs(cards=('全都要·银', '全都要·金', '全都要·彩'),
                      unchosen=_COLS)
    _take_all_run(gs)
    # 三卡各发一遍:同名 1★ 三副本 → 合成级联收束 2★(拍 1 即合并,
    # 双持拍 1 两副本不合并的对照面 = 存量双持锁)。
    assert _bench_names(gs) == ['希儿'], \
        f'三持各发一遍(级联合并收束): {_bench_names(gs)}'
    assert gs.bench.value.slots[0].unit.star == 2, '三副本合成产物星级'
    assert gs.equips.value == ['光能电池', '折叠小刀'] * 3, \
        f'装备腿各发一遍: {gs.equips.value}'
    assert tuple(gs.strategy_conditional_done.value or ()) == (
        'take_all#全都要·银#1', 'take_all#全都要·金#1'), \
        'int 卡各置各的一次性标志位,彩零配额格(域恰两键)'
    assert gs.unchosen_supply.value is None, '消费即清'
    gs.write_logic(gs.unchosen_supply, _COLS, produced_by='test-seed',
                   sig=_SIG)
    _take_all_run(gs)
    # 拍 2:银一次性标志位满零发,金第二拍 + 彩第一拍各发一遍(2× 1★ 入席,不足
    # 三副本零合并;2★ 星组独立不参与)。
    assert _bench_names(gs) == ['希儿', '希儿', '希儿'], \
        f'金/彩各发一遍互不早退: {_bench_names(gs)}'
    assert tuple(gs.strategy_conditional_done.value or ()) == (
        'take_all#全都要·银#1',
        'take_all#全都要·金#1', 'take_all#全都要·金#2'), \
        '银键不追加(满),金追加,彩键空间恒空'


def test_take_all_producer_attribution_and_assumption_keys(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """写端归属锁:随机态发放写行 producer = 'CwScreenSupplyNode'(未选域
    发放写端家族值,与打捞腿同归属,防缺省归因混淆)+ 披露键静态常量已登记
    (无运行时 setdefault 动作,两键:钻归属零建模 / sim fail-closed)。"""
    gs = _take_all_gs()
    captured: list[tuple] = []
    real_rand = GameState.write_logic_rand

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), kw.get('produced_by')))
        return real_rand(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic_rand', _spy)
    _take_all_run(gs)
    assert captured, '随机态写行在捕获窗'
    assert all(p == 'CwScreenSupplyNode' for _, p in captured), \
        f'producer 归因: {captured}'
    assert STRATEGY_TAKE_ALL_ASSUMPTION_KEYS == (
        'strategy_take_all_unchosen_diamond_pending',
        'strategy_take_all_sim_failclosed_decision_leg',
    )
