"""策略延时 offer 倒计时递减效果条目测试(镜像 src = kernel/cw_game_state.py 的
_tick_pending_strategy_offers + _tick_effect_boundary_impl 接入调用)。

测试面依据 = 迭代设计 designs/T-98-huangjin-qihuo.md §4 锁 3(3 条):
- 计数起点 = 拿卡节点第 N 后继节点窗(拿卡窗内登记不递减,后继推进
  逐次减 1,第 5 后继窗减到 0);
- 同节点重复 tick 零递减(与效果账本 advance_node 同一 advanced 位闸);
- remaining=0 悬置不越减(到点条目待呈现,递减效果条目永不写负);
- 空队列 tick 零写。

驱动口 = advance_node_effective(序位前进唯一落账入口,尾段自带
tick_effect_boundary);先消耗拿卡节点复现「登记在窗内、递减在下一
advance」的真实时序。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    _tick_pending_strategy_offers,
    advance_node_effective,
    tick_effect_boundary,
)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestDriver',
                      mode='compute')


def _advance(gs: GameState, plane: int, round_num: int) -> None:
    assert advance_node_effective(gs, (plane, round_num), actor='TestDriver',
                                  sig=_lsig(), source='logic'), \
        f'推进被去重守卫挡下: {(plane, round_num)}'


def _gs_with_card_at(consume_plane: int, consume_round: int,
                     remaining: int | None) -> GameState:
    """拿卡时序状态容器:先消耗拿卡节点(该节点 tick 已过,效果账本去重位
    钉在拿卡窗),再登记队列——复现「登记在节点窗内,递减自下一后继
    advance 起」。remaining=None = 不登记(空队列形态)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _advance(gs, consume_plane, consume_round)
    if remaining is not None:
        gs.write_logic(gs.pending_strategy_offers,
                       (('黄金期货', remaining),),
                       produced_by='test-seed', evidence='t:queue',
                       sig=_lsig())
    return gs


def test_counting_start_and_same_node_dedup() -> None:
    """计数起点 + 同节点去重(锁 3 前两条):登记节点窗内 tick 零递减
    (时序锁:登记在窗内,递减在下一次 advance);后继推进逐次减 1;
    同节点重复 tick 零递减;恰在第 5 后继窗减到 0(「5个节点后」= 拿卡
    节点的第 5 后继节点窗,效果账本「后继 N 节点」口径对齐)。"""
    gs = _gs_with_card_at(1, 1, remaining=5)
    tick_effect_boundary(gs)   # 拿卡窗内重复 tick(同节点去重位闸)
    assert gs.pending_strategy_offers.value == (('黄金期货', 5),), \
        '登记当节点递减 = 计数起点错口径'
    _advance(gs, 1, 2)
    assert gs.pending_strategy_offers.value == (('黄金期货', 4),)
    tick_effect_boundary(gs)   # 同节点重复 tick
    assert gs.pending_strategy_offers.value == (('黄金期货', 4),), \
        '同节点重复 tick 递减 = advanced 位闸失效'
    _advance(gs, 1, 3)
    _advance(gs, 1, 4)
    _advance(gs, 1, 5)
    assert gs.pending_strategy_offers.value == (('黄金期货', 1),)
    _advance(gs, 1, 6)
    assert gs.pending_strategy_offers.value == (('黄金期货', 0),), \
        f'第 5 后继窗应减到 0: {gs.pending_strategy_offers.value}'


def test_zero_entry_suspended_no_over_decrement() -> None:
    """remaining=0 悬置不越减(锁 3 第三条):到点条目待呈现,后续节点
    推进不再递减(永不写负),错过不悬空。"""
    gs = _gs_with_card_at(1, 1, remaining=0)
    _advance(gs, 1, 2)
    _advance(gs, 1, 3)
    assert gs.pending_strategy_offers.value == (('黄金期货', 0),), \
        f'到点条目被越减: {gs.pending_strategy_offers.value}'


def test_empty_queue_tick_zero_write() -> None:
    """空队列 tick 零写:递减效果条目队空早退,无队列行(write_logic 无同值
    去重,省行惯例 = 调用方早退)。"""
    gs = _gs_with_card_at(1, 1, remaining=None)
    seq_before = gs.write_seq
    _tick_pending_strategy_offers(gs)
    assert gs.pending_strategy_offers.value is None, '空队列被写'
    assert gs.write_seq == seq_before, '空队列 tick 出现写行'
