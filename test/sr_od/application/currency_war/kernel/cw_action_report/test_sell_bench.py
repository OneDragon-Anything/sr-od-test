"""sell_bench 溢出腿入位身份守恒测试(镜像 src =
kernel/cw_action_report/sell_bench.py;同 src 兄弟测试 =
kernel/test_gain_chain.py 卖牌段〔在册超限文件,只读复用不追加〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.4.3 + §4 锁 5:
溢出往返身份守恒——overflow_warning + overflow_card='专家邀请函' → 卖牌
腾槽入位 = bookcard 带名槽件;='简易武装箱' → supply_box 带名(回归);
角色名 → unit 腿(回归)。入位构造 = 词表守卫保留 + 查映射带名槽件
(身份守恒闭环:发放带名落席 → 溢出字符串(名字本身)→ 入位槽带名)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_sell_bench_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    seed_opening_state,
)

_SIG = ChannelSig(family='logic_action', actor='SellBenchTest', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='SellBenchTest')


def _make_gs_full_bench() -> GameState:
    """种子底座 + 9 满席(1★ 希儿 ×9,无装备无三连)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='unit', unit=Unit(char_id='希儿', star=1))
               for _ in range(9)], capacity=9), sig=_SIG_OBS)
    return gs


def _sell_slot0(gs: GameState) -> None:
    out = report_action_sell_bench_param(
        gs, SimpleNamespace(bench_idx=0, expect='', reason='t'), _SIG)
    assert out.applied


def test_sell_absorbs_overflow_bookcard_named_slot() -> None:
    """溢出邀请函入位(设计 §2.4.3 + §4 锁 5):席满 + 溢出位 = 专家邀请函
    → 卖牌腾槽入位 = bookcard 带名槽件(kind+item 逐位),溢出两字段成对
    清写——邀请函全旅程 bookcard/名不漂。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '专家邀请函', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert (slot.kind, slot.item) == ('bookcard', '专家邀请函'), \
        f'入位带名槽件: {(slot.kind, slot.item)}'
    assert gs.overflow_card.value == '' \
        and gs.overflow_warning.value is False, '溢出两字段成对清写'


def test_sell_absorbs_overflow_box_named_slot_regression() -> None:
    """溢出箱入位回归(设计 §4 锁 5):溢出位 = 简易武装箱 → supply_box
    带名槽件(原写死 supply_box 行为逐位等价 + 名字随行)。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '简易武装箱', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert (slot.kind, slot.item) == ('supply_box', '简易武装箱')


def test_sell_absorbs_overflow_char_unit_leg_regression() -> None:
    """角色腿回归(设计 §4 锁 5):溢出位 = 角色名(词表外)→ 入位 unit
    槽件星级 1 兜底;item 恒 None(词表守卫保留,行为不变)。"""
    gs = _make_gs_full_bench()
    gs.observe(gs.overflow_card, '银狼', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    _sell_slot0(gs)
    slot = gs.bench.value.slots[0]
    assert slot.kind == 'unit' and slot.unit is not None
    assert (slot.unit.char_id, slot.unit.star) == ('银狼', 1)
    assert slot.item is None, 'unit 槽 item 恒 None'
