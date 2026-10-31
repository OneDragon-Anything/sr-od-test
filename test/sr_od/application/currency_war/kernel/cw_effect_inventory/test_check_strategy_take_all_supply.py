"""全都要·银选卡时点检查测试(cw_effect_inventory 分目录镜像;被测 =
check_strategy_take_all_supply,挂点行为面归 kernel/cw_action_report/
test_pick_supply.py)。

锁面(卡面 id 131001 官方原文「下1个补给阶段选择后，额外获得所有未选择
的角色及装备」,语义正本 = 全都要族设计稿 §2.3):
- 门序:未持卡零写零闩 / 持卡 ∧ 闩已设零写 / 兜底形态(源 None/空)零发放
  但闩被设(A 案事件消耗制);
- 全捞主锁:全未选列逐列发放 + evidence 串 + 闩设 + 消费即清 + 零 rng;
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

# sig 形态 = 挂点真值:补给选定上报的调用方签名(动作 op 内构造)。
_SIG = ChannelSig(family='logic_action', actor='CwActionPickSupplyOp',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='test', mode='read')

_COLS = (
    SupplyOption(idx=0, char='希儿', equip='光能电池', extra_equips=()),
    SupplyOption(idx=1, char='', equip='折叠小刀', extra_equips=()),
)


def _take_all_gs(*, bench_entries: list[Unit] | None = None,
                 bench_unobserved: bool = False, card: bool = True,
                 unchosen: tuple[SupplyOption, ...] | None = _COLS,
                 latched: bool = False) -> GameState:
    """直构容器(bench/equips/持卡/未选集/闩按参;bench_unobserved = 域未
    观察形态;unchosen None = 无未选定案;latched = 闩预置)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if not bench_unobserved:
        slots = [BenchSlot(kind='unit', unit=u) for u in (bench_entries or ())]
        slots += [BenchSlot(kind='empty')] * (BENCH_CAPACITY_DEFAULT
                                              - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots,
                                       capacity=BENCH_CAPACITY_DEFAULT),
                   sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if card:
        gs.observe(gs.active_strategies, ['全都要·银'], sig=_SIG_OBS)
    if latched:
        gs.write_logic(gs.strategy_conditional_done, ('全都要·银',),
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
    """门序锁·零写臂:未持卡 → 零写零闩(未持卡局全链零变化);持卡 ∧
    闩已设 → 零写(一次性封账,重复出口重入全静默)。"""
    for kwargs in ({'card': False}, {'latched': True}):
        gs = _take_all_gs(**kwargs)
        seq = gs.write_seq
        latch_before = gs.strategy_conditional_done.value
        _take_all_run(gs)
        assert gs.write_seq == seq, f'门序零写({kwargs})'
        assert gs.strategy_conditional_done.value == latch_before, \
            f'零闩写({kwargs})'


def test_take_all_fallback_round_consumes_quota_zero_grant() -> None:
    """门序锁·兜底形态臂(A 案事件消耗制):持卡 ∧ 闩未设 ∧ 源 None/空
    → 零发放(发放侧门)但闩被设(选择事件即耗,首个 applied 出口含
    内容全未知兜底轮;漏记列由观察覆盖承接)。"""
    for unchosen in (None, ()):
        gs = _take_all_gs(unchosen=unchosen)
        _take_all_run(gs)
        assert _bench_names(gs) == [], f'零发放(unchosen={unchosen!r})'
        assert gs.equips.value == [], '装备域零写'
        assert gs.strategy_conditional_done.value == ('全都要·银',), \
            f'闩已设(A 案簿记,unchosen={unchosen!r})'


def test_take_all_grants_all_columns_consume_clear_and_zero_rng(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """全捞主锁:持卡 + 未选 2 列(列 0 = 角色+装备 / 列 1 = 孤儿簇仅装备)
    → 两列全发放:char 腿入席 1★、装备腿 owned 恒规范名;char 腿 evidence
    = ``strategy_take_all:<名>@1star``(效果串落点 = 随机写 evidence 本身);
    闩设 + 字段清(消费即清)+ 二次调用零写(重入幂等);rng 消费 = 0
    (「所有」= 零采样,采样入口计数桩断言零调用);发放面 = 随机态通道
    (bench/equips logic_rand),闩与消费即清 = 逻辑态。"""
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
    assert gs.strategy_conditional_done.value == ('全都要·银',), '闩设'
    assert gs.unchosen_supply.value is None, '消费即清'
    assert calls == [], f'零 rng 消费(零采样): {calls}'
    assert gs.bench.source == 'logic_rand', 'char 腿随机态通道'
    assert gs.equips.source == 'logic_rand', '装备腿随机态通道'
    assert gs.unchosen_supply.source == 'logic', '消费即清 = 逻辑态'
    assert gs.strategy_conditional_done.source == 'logic', '闩 = 逻辑态'
    seq = gs.write_seq
    _take_all_run(gs)
    assert gs.write_seq == seq, '二次调用零写(闩门封账,重入幂等)'


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


def test_take_all_producer_attribution_and_assumption_keys(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """写端归属锁:随机态发放写行 producer = 'CwScreenSupplyNode'(未选域
    发放写端家族值,与打捞腿同归属,防缺省归因混淆)+ 披露键静态常量在册
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
