"""report_action_sell_deployed_param 坐标域扩展测试(镜像 src =
kernel/cw_action_report/sell_deployed.py;unified-deploy-order §4
D4-2/D5-2:扩格帧后排 7-9 可直卖——上报侧直读动态视图,旧定长 10
截断桥退役)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_sell_deployed_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_ACT = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _gs_with_back8(back: list[Unit | None], gold: int = 10) -> GameState:
    """后排 8 格扩格局种子(宝钻/召唤物扩容形态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(
        slots=[BenchSlot(kind='empty')] * 9, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(front_slots=[None] * 4,
                                         back_slots=list(back)),
               sig=_SIG_OBS)
    gs.observe(gs.gold, gold, sig=_SIG_OBS)
    return gs


def test_expanded_back_row_slot_7_sellable() -> None:
    """扩格帧后排第 7 槽(idx=4+6=10,旧定长 10 坐标系外)可直卖:
    视图摘槽 + 退金入账,桥截断边界退役。"""
    back = [Unit(char_id='三月七', star=1)] + [None] * 7
    back[6] = Unit(char_id='花火', star=1)   # 后排第 7 槽
    gs = _gs_with_back8(back)
    out = report_action_sell_deployed_param(
        gs, type('P', (), {'deployed_idx': 10, 'expect': '',
                           'reason': '', 'income': None})(), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.back_slots[6] is None
    assert gs.deployed.value.back_slots[0].char_id == '三月七'
    assert gs.gold.value > 10   # 退金入账


def test_out_of_dynamic_range_refused() -> None:
    """越出动态容量(后排 8 格局 idx=12)拒零写。"""
    gs = _gs_with_back8([Unit(char_id='三月七', star=1)] + [None] * 7)
    out = report_action_sell_deployed_param(
        gs, type('P', (), {'deployed_idx': 12, 'expect': '',
                           'reason': '', 'income': None})(), _SIG_ACT)
    assert out.applied is False
    assert out.reason == 'deployed_idx_out_of_range:12'


def test_base_back_row_semantics_unchanged() -> None:
    """基线 6 格局后排(idx 4-9)语义不变(前排 0-3 同款零改)。"""
    gs = _gs_with_back8([Unit(char_id='刃', star=1)] + [None] * 5)
    out = report_action_sell_deployed_param(
        gs, type('P', (), {'deployed_idx': 4, 'expect': '刃',
                           'reason': '', 'income': None})(), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.back_slots[0] is None
