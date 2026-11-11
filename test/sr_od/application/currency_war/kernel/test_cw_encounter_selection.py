"""结算观测环数据面测试(镜像 src = kernel/cw_encounter_selection.py;
T-33 英雄登场 _RingRow.hp_after 扩字段批)。

测试面依据 = 迭代 T-33 英雄登场设计(已退役账本
invest-effects-calc/设计稿(原件已退役;判据 = 本文件锁面申报))§2.4 数据面 +
§4 锁 8:
- **hp_after 入行**:live 单一写端 record_settlement_row 现成持有
  RoundOutcome.hp_after(kernel/cw_performance.py),由丢弃改入行——
  完胜判定「相邻两结算帧 hp 差分」基准的 live 写端;
- **同键合并语义不因新字段破坏**:后到行缺值(None)不覆盖先行行已有
  值,先行行缺值由后到行带上(与 killed/progress_fill_ratio 同款合并
  优先级);
- **深度旋转不因新字段破坏**:11 行入环淘汰最旧行,hp_after 随行携带;
- 环消费方零扰:既有读口(last_normal_battles/last_row/EncounterLog)
  行为逐位不变(新字段 = 尾部追加,构造点带默认值)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_encounter_selection import (
    SETTLEMENT_RING_DEPTH,
    record_settlement_row,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_performance import (
    RoundOutcome,
)

_SIG = ChannelSig(family='logic_action', actor='T', mode='compute')


def _make_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _offer(gs: GameState, outcome: RoundOutcome, plane: int,
           round_num: int) -> str:
    return record_settlement_row(gs, outcome, plane=plane,
                                 round_num=round_num,
                                 node_type=outcome.node_type,
                                 difficulty_node=None, encounter_tier=None)


def test_hp_after_recorded_via_production_writer() -> None:
    """hp_after 入行(T-33 设计 §4 锁 8 live 半边):record_settlement_row
    把 RoundOutcome.hp_after 带入环行(last_row 读口可读);None 透传
    (读缺不硬塞,宁缺勿造)。"""
    gs = _make_gs()
    verdict = _offer(gs, RoundOutcome(round_num=1, plane=1,
                                      node_type='普通战斗', comp_tag='',
                                      killed=True, hp_after=80), 1, 1)
    assert verdict == 'ring'
    row = gs.settlement_ring.last_row()
    assert row is not None and row.hp_after == 80, 'hp_after 入行'
    gs2 = _make_gs()
    _offer(gs2, RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                             comp_tag='', killed=True, hp_after=None), 1, 1)
    assert gs2.settlement_ring.last_row().hp_after is None, 'None 透传'


def test_merge_semantics_carry_new_field_without_overwrite() -> None:
    """同键合并不因新字段破坏(T-33 设计 §4 锁 8):同 (plane, round)
    两路入环——先行行 hp_after 已有值,后到缺值不覆盖(与既有字段同款
    优先级);先行行缺值由后到行带上;killed 等既有字段合并语义逐位
    不变。"""
    gs = _make_gs()
    _offer(gs, RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                            comp_tag='', killed=True, hp_after=80,
                            progress_fill_ratio=0.5), 2, 1)
    verdict = _offer(gs, RoundOutcome(round_num=1, plane=2,
                                      node_type='普通战斗', comp_tag='',
                                      killed=None, hp_after=None,
                                      progress_fill_ratio=None), 2, 1)
    assert verdict == 'merged'
    row = gs.settlement_ring.last_row()
    assert (row.killed, row.hp_after, row.progress_fill_ratio) == \
        (True, 80, 0.5), '后到缺值不覆盖先行值(新字段同款)'
    gs2 = _make_gs()
    _offer(gs2, RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                             comp_tag='', killed=None, hp_after=None), 2, 1)
    _offer(gs2, RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                             comp_tag='', killed=True, hp_after=66), 2, 1)
    row2 = gs2.settlement_ring.last_row()
    assert (row2.killed, row2.hp_after) == (True, 66), \
        '先行缺值由后到行带上(补全语义)'


def test_rotation_eviction_rides_new_field() -> None:
    """深度旋转不因新字段破坏(T-33 设计 §4 锁 8):深度 10,第 11 行
    入环淘汰最旧行;尾行 hp_after 完整可读,环长度恒 = 深度。"""
    gs = _make_gs()
    for i in range(SETTLEMENT_RING_DEPTH + 1):
        _offer(gs, RoundOutcome(round_num=i + 1, plane=1,
                                node_type='普通战斗', comp_tag='',
                                killed=True, hp_after=100 - i), 1, i + 1)
    assert len(gs.settlement_ring) == SETTLEMENT_RING_DEPTH, '深度恒定'
    tail = gs.settlement_ring.last_row()
    assert (tail.round_num, tail.hp_after) == \
        (SETTLEMENT_RING_DEPTH + 1, 100 - SETTLEMENT_RING_DEPTH), \
        '尾行随旋转携带 hp_after'
