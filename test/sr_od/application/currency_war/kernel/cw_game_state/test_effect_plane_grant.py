"""位面开始桥 + 中途拿卡补发桥测试(cw_game_state 分目录镜像;「现在
以及每个位面开始时」族位面段刷新支)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.3/§2.4/§4(锁 3/
锁 4 裁定 B 改形)+ 用户裁定书 T-182 节(2026-11-01 用户决定:中途拿卡时
当前已开始的位面,其位面段奖励照常发放〔全额〕,后续位面照常):
- 位面开始桥发放真值(锁 3):持卡局 (2,1)/(3,1) 推进拍 free_refresh_left
  各 +2(evidence ``effect_plane@frame``、produced_by 带卡名);非位面
  首节点((2,2))拍零增量;
- 桥幂等锁(锁 4):同 (plane,1) 锚定补推(推进原语 candidate <= effective
  零推进)刷新支零双发;
- 零值形态:未持卡局全零(None 基不动);补发桥零字段条目 no-op;
- 补发桥(锁 3 裁定 B 半):登记拍全额补发当前已开始位面的位面段刷新
  (+2 非 +1〔全额非按比例〕);node 缺席 = 保守零补发;补发后后续位面
  开始照常走位面开始桥,两桥同字段不重复(补发拍 + 位面开始拍各 +2)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    advance_node_effective,
    apply_effect_plane_refire_grant,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestPlaneGrant', mode='read')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='TestPlaneGrant',
                        mode='compute')

_SPEC = STRATEGY_EFFECTS['固定理财']


def _make_gs(*, with_card: bool = True) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if with_card:
        gs.effects.register_strategy(_SPEC, acquired_key=(1, 3))
    return gs


def _observe_node(gs: GameState, plane: int, round_num: int) -> None:
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num,
                                kind='battle'),
               evidence='t:seed', sig=_SIG_OBS)


def _advance(gs: GameState, pos: tuple[int, int]) -> bool:
    return advance_node_effective(gs, pos, actor='TestPlaneGrant',
                                  sig=_SIG_LOGIC, source='logic')


def test_plane_start_bridge_grants_each_plane_first_node() -> None:
    """发放真值(锁 3):(2,1)/(3,1) 推进拍各 +2,(2,2) 非位面首节点拍
    零增量;evidence/produced_by 落位面开始桥形态。"""
    gs = _make_gs()
    assert gs.free_refresh_left.value is None, 'None 基 = 未发放'
    assert _advance(gs, (2, 1))
    assert gs.free_refresh_left.value == 2, '位面开始拍 +2'
    assert gs.free_refresh_left.source == 'logic'
    assert gs.free_refresh_left.evidence == 'effect_plane@2-1'
    before = gs.free_refresh_left.value
    assert _advance(gs, (2, 2))
    assert gs.free_refresh_left.value == before, '非位面首节点零增量'
    assert _advance(gs, (3, 1))
    assert gs.free_refresh_left.value == before + 2, '后续位面开始照常 +2'


def test_plane_start_bridge_replay_zero_double() -> None:
    """桥幂等锁(锁 4):同 (2,1) 锚定补推(推进原语 candidate <= effective
    去重返回 False)→ 刷新支零双发。"""
    gs = _make_gs()
    assert _advance(gs, (2, 1))
    assert gs.free_refresh_left.value == 2
    assert not _advance(gs, (2, 1)), '同序位补推零推进'
    assert gs.free_refresh_left.value == 2, '重放零双发'


def test_plane_start_bridge_no_card_zero() -> None:
    """未持卡局全零:位面开始推进拍零 Field 行(None 基不动)。"""
    gs = _make_gs(with_card=False)
    assert _advance(gs, (2, 1))
    assert gs.free_refresh_left.value is None, '未持卡零发放'


def test_refire_bridge_full_amount_at_pick() -> None:
    """补发桥(裁定 B 半):登记拍全额补发当前已开始位面的位面段刷新
    (+2 全额非按比例),evidence ``effect_plane_refire@frame``、
    produced_by 带卡名。"""
    gs = _make_gs()
    _observe_node(gs, 2, 3)   # (2,3) 窗内登记:P2 已开始
    apply_effect_plane_refire_grant(gs, _SPEC, frame='2-3')
    assert gs.free_refresh_left.value == 2, '登记拍全额补发 +2'
    assert gs.free_refresh_left.source == 'logic'
    assert gs.free_refresh_left.evidence == 'effect_plane_refire@2-3'


def test_refire_bridge_node_absent_zero() -> None:
    """node 缺席(局外/未观察形态)= 保守零补发(禁猜)。"""
    gs = _make_gs()
    apply_effect_plane_refire_grant(gs, _SPEC, frame='')
    assert gs.free_refresh_left.value is None, 'node 缺席零补发'


def test_refire_bridge_zero_field_noop() -> None:
    """零字段条目 no-op(零 Field 行):免战牌 payload 无
    free_refresh_per_plane。"""
    gs = _make_gs()
    _observe_node(gs, 2, 3)
    apply_effect_plane_refire_grant(gs, STRATEGY_EFFECTS['免战牌'],
                                    frame='2-3')
    assert gs.free_refresh_left.value is None, '零字段 no-op'


def test_refire_then_next_plane_start_both_legs() -> None:
    """两桥分工不重叠:补发拍(+2,P2 段)后,后续位面开始 (3,1) 照常
    走位面开始桥再 +2——同字段两笔,evidence 分键可辨。"""
    gs = _make_gs()
    _observe_node(gs, 2, 3)
    apply_effect_plane_refire_grant(gs, _SPEC, frame='2-3')
    assert _advance(gs, (3, 1))
    assert gs.free_refresh_left.value == 4, '补发拍 + 位面开始拍各 +2'
    assert gs.free_refresh_left.evidence == 'effect_plane@3-1', \
        '后笔 = 位面开始桥 evidence'
