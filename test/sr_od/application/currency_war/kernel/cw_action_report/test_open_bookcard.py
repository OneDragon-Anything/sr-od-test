"""open_bookcard 开卡上报 kind 硬门测试(镜像 src =
kernel/cw_action_report/open_bookcard.py;同 src 语义兄弟测试 =
operations/test_overlay.py S6 登记/声明段与 test_world_decl.py 行 6 出口
〔只读复用,本文件只锁 kind 正确性门〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(已退役账本
effects-calc/设计稿(原件已退役;判据 = 本文件锁面申报))§1 事实面 + §4 锁 4
(kernel 半):bookcard 槽上报 applied=True + 槽腾空 + expert_invite 登记
(登记 = 弹窗出现事实,呈现/分发归外循环);反例 = supply_box 身份槽 →
applied=False bookcard_slot_missing 零写零登记(kind 正确性 = 开启链前置,
历史教训防线:原先统一降级 supply_box 时策略器开卡臂对着卡槽必败)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_open_bookcard_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    seed_opening_state,
)

_SIG = ChannelSig(family='logic_action', actor='OpenBookcardTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='OpenBookcardTest')


def _make_gs(slots: list[BenchSlot]) -> GameState:
    """种子初始值 + 指定槽位表观察。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    return gs


def test_open_bookcard_applies_frees_slot_and_registers() -> None:
    """正分支(设计 §4 锁 4):bookcard 槽(带名)已登记 → slot=None 自动定位
    上报 applied=True,该槽腾空(empty),expert_invite 已登记。"""
    slots = [BenchSlot(kind='empty'),
             BenchSlot(kind='bookcard', item='专家邀请函'),
             BenchSlot(kind='supply_box', item='简易武装箱')]
    slots += [BenchSlot(kind='empty')] * 6
    gs = _make_gs(slots)
    out = report_action_open_bookcard_param(
        gs, SimpleNamespace(slot=None), _SIG)
    assert out.applied
    freed = gs.bench.value.slots[1]
    assert freed.kind == 'empty', '开卡即腾位'
    kinds = [p.kind for p in gs.screen_changes.pending]
    assert kinds == ['expert_invite'], f'已登记: {kinds}'


def test_open_bookcard_supply_box_slot_rejected_zero_write() -> None:
    """反分支(设计 §4 锁 4):仅 supply_box 身份槽 → applied=False
    bookcard_slot_missing,bench 零写、零登记(kind 硬门 = 开启链前置)。"""
    slots = [BenchSlot(kind='supply_box', item='简易武装箱')] \
        + [BenchSlot(kind='empty')] * 8
    gs = _make_gs(slots)
    out = report_action_open_bookcard_param(
        gs, SimpleNamespace(slot=None), _SIG)
    assert out.applied is False
    assert out.reason == 'bookcard_slot_missing'
    assert gs.bench.value.slots[0].kind == 'supply_box', 'bench 零写'
    assert gs.screen_changes.pending == [], '零登记'
