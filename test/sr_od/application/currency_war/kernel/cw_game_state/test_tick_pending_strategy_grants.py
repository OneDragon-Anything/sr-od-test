"""策略延时发放倒计时递减效果条目测试(镜像 src = kernel/cw_game_state.py 的
_tick_pending_strategy_grants + _tick_effect_boundary_impl 接入调用)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 3(3 条)+
锁 9(P2 末冻结直构)+ T-107 展开卡批(designs/T-107-rencai-jili-plus.md
§4 锁 3 参数化 +本卡变体、锁 4 双卡并存独立倒计时):
- 计数起点 = 拿卡节点第 N 后继节点窗(拿卡窗内登记不递减,后继推进
  逐次减 1,第 N 后继窗减到 0——「N个节点后」;姊妹双卡参数化
  人才激励@4 / 人才激励+@3);
- 同节点重复 tick 零递减(与效果账本 advance_node 同一 advanced 位闸);
- remaining=0 悬置不越减(到点条目待发放,递减效果条目永不写负);
- 空队列 tick 零写;
- P2 末冻结:后继 = None(P3 未观测)→ 终局事件零效果 tick,队列原样
  零发放零弹除(裁决点 5 申报);
- 双卡并存:队列两条目逐条独立倒计时互不干扰,到点发放经
  discharge_due_strategy_grants 作观测口(发放原语本体镜像域 =
  kernel/cw_gain_chain/test_discharge_due_strategy_grants.py)。

驱动口 = advance_node_effective(序位前进唯一落账入口,尾段自带
tick_effect_boundary);先消耗拿卡节点复现「登记在窗内、递减在下一
advance」的真实时序。"""
from __future__ import annotations

import random

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    discharge_due_strategy_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    _tick_pending_strategy_grants,
    advance_node_effective,
    report_node_advance,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
    sequence_next,
)

_LSIG = ChannelSig(family='logic_action', actor='TestDriver',
                   mode='compute')
_OBS_LSIG = ChannelSig(family='logic_action', actor='TestDriver',
                       mode='compute')

_CARD = '人才激励'
_CARD_PLUS = '人才激励+'


def _advance(gs: GameState, plane: int, round_num: int) -> None:
    assert advance_node_effective(gs, (plane, round_num), actor='TestDriver',
                                  sig=_LSIG, source='logic'), \
        f'推进被去重守卫挡下: {(plane, round_num)}'


def _gs_with_queue(consume_plane: int, consume_round: int,
                   queue: tuple, equips: list[str] | None = None) -> GameState:
    """拿卡时序状态容器:先消耗拿卡节点(该节点 tick 已过,效果账本去重位
    钉在拿卡窗),再登记队列——复现「登记在节点窗内,递减自下一后继
    advance 起」。equips=None = 装备栏未观察(拒落域);到点发放观测
    需显式传已观察装备栏(如 [])。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    _advance(gs, consume_plane, consume_round)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       evidence='t:equips', sig=_LSIG)
    gs.write_logic(gs.pending_strategy_grants, queue,
                   produced_by='test-seed', evidence='t:queue',
                   sig=_LSIG)
    return gs


def _gs_with_card_at(consume_plane: int, consume_round: int, card: str,
                     remaining: int | None) -> GameState:
    """单卡薄壳:remaining=None = 不登记(空队列形态)。"""
    if remaining is None:
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        _advance(gs, consume_plane, consume_round)
        return gs
    return _gs_with_queue(consume_plane, consume_round,
                          ((card, remaining),))


@pytest.mark.parametrize(('card', 'delay'), [
    (_CARD, 4),
    (_CARD_PLUS, 3),
])
def test_counting_start_and_same_node_dedup(card: str,
                                            delay: int) -> None:
    """计数起点 + 同节点去重(锁 3 前两条,姊妹双卡参数化):登记节点
    窗内 tick 零递减(时序锁:登记在窗内,递减在下一次 advance);后继
    推进逐次减 1;同节点重复 tick 零递减;恰在第 delay 后继窗减到 0
    (「N个节点后」= 拿卡节点的第 N 后继节点窗,效果账本「后继 N 节点」
    口径对齐)。"""
    gs = _gs_with_card_at(1, 1, card, remaining=delay)
    tick_effect_boundary(gs)   # 拿卡窗内重复 tick(同节点去重位闸)
    assert gs.pending_strategy_grants.value == ((card, delay),), \
        '登记当节点递减 = 计数起点错口径'
    _advance(gs, 1, 2)
    assert gs.pending_strategy_grants.value == ((card, delay - 1),)
    tick_effect_boundary(gs)   # 同节点重复 tick
    assert gs.pending_strategy_grants.value == ((card, delay - 1),), \
        '同节点重复 tick 递减 = advanced 位闸失效'
    for _r in range(3, delay + 1):
        _advance(gs, 1, _r)
    assert gs.pending_strategy_grants.value == ((card, 1),)
    _advance(gs, 1, delay + 1)
    assert gs.pending_strategy_grants.value == ((card, 0),), \
        f'第 {delay} 后继窗应减到 0: {gs.pending_strategy_grants.value}'


def test_zero_entry_suspended_no_over_decrement() -> None:
    """remaining=0 悬置不越减(锁 3 第三条):到点条目待发放,后续节点
    推进不再递减(永不写负),错过不悬空。"""
    gs = _gs_with_card_at(1, 1, _CARD, remaining=0)
    _advance(gs, 1, 2)
    _advance(gs, 1, 3)
    assert gs.pending_strategy_grants.value == ((_CARD, 0),), \
        f'到点条目被越减: {gs.pending_strategy_grants.value}'


def test_empty_queue_tick_zero_write() -> None:
    """空队列 tick 零写:递减效果条目队空早退,无队列行(write_logic 无同值
    去重,省行惯例 = 调用方早退)。"""
    gs = _gs_with_card_at(1, 1, _CARD, remaining=None)
    seq_before = gs.write_seq
    _tick_pending_strategy_grants(gs)
    assert gs.pending_strategy_grants.value is None, '空队列被写'
    assert gs.write_seq == seq_before, '空队列 tick 出现写行'


def test_dual_cards_plus_fires_third_window_sister_suspended() -> None:
    """双卡并存独立倒计时(T-107 锁 4①):同局双持(人才激励@4 +
    人才激励+@3)推进 3 次 → '+' 条目减到 0、姊妹条目 remaining=1
    悬置;到点发放仅 '+' 入栏弹除,姊妹条目原样保留——两条目逐条
    独立倒计时/独立到点,队列 (卡名, remaining) 元组结构零判重闸。"""
    gs = _gs_with_queue(1, 1, ((_CARD, 4), (_CARD_PLUS, 3)), equips=[])
    for _r in range(2, 5):
        _advance(gs, 1, _r)
    assert gs.pending_strategy_grants.value \
        == ((_CARD, 1), (_CARD_PLUS, 0)), \
        f'第 3 后继窗队列: {gs.pending_strategy_grants.value}'
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:员工投影仪(placed=True)',), \
        f'到点发放: {effects}'
    assert gs.equips.value == ['员工投影仪'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == ((_CARD, 1),), \
        '姊妹条目被误弹除'


def test_dual_cards_sister_fires_fourth_window_after_plus() -> None:
    """双卡并存独立倒计时(T-107 锁 4②):'+' 弹除后再推进 1 次 →
    姊妹条目到点发放弹除、队列清空——两件投影仪各随各窗入栏(同款
    发放物经卡名 evidence 可分,本锁锁时序与弹除)。"""
    gs = _gs_with_queue(1, 1, ((_CARD, 4), (_CARD_PLUS, 3)), equips=[])
    for _r in range(2, 5):
        _advance(gs, 1, _r)
    discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    _advance(gs, 1, 5)
    assert gs.pending_strategy_grants.value == ((_CARD, 0),)
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:员工投影仪(placed=True)',), \
        f'姊妹窗发放: {effects}'
    assert gs.equips.value == ['员工投影仪', '员工投影仪'], \
        f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (), '姊妹条目未弹除'


def test_huishou_countdown_zero_sampling_then_due_category_sample() -> None:
    """回收计划 @5 全链(随机类别池行,T-237 批):登记 5 拍 → 递减 5
    窗减到 0(第 N 后继窗口径对既有行同源)且递减全程 rng 零采样(随机
    值不预掷:倒计时 = 确定推算,掷骰时点 = 到点发放窗——rng.getstate
    跨 5 次 advance 逐位相等的行为证据)→ 到点窗发放采样 ∈ 简易池派生
    集(禁值漂移断言)+ 弹除。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )
    pool = equips_by_category('简易')
    gs = _gs_with_queue(1, 1, (('回收计划', 5),), equips=[])
    rng = random.Random(7)
    state_after_queue = rng.getstate()
    for _r in range(2, 7):
        _advance(gs, 1, _r)
    assert gs.pending_strategy_grants.value == (('回收计划', 0),), \
        f'第 5 后继窗应减到 0: {gs.pending_strategy_grants.value}'
    assert rng.getstate() == state_after_queue, \
        '递减全程消费 rng(随机值预掷,掷骰时点漂移)'
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=rng, sig=_LSIG)
    chosen = random.Random(7).choice(pool)
    assert effects == (f'delayed_grant:{chosen}(placed=True)',), \
        f'到点发放: {effects}'
    assert gs.equips.value == [chosen], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (), '到期条目未弹除'


def test_p2_end_freeze_no_grant_no_eject() -> None:
    """锁 9(P2 末冻结直构):P2 末节点后继 = None(P3 未观测,场字段
    未注册第 3 位面)→ 终局上报零效果 tick——倒计时跨 P2 末的条目冻结
    不发放不弹除(裁决点 5 申报;发放归 sim 窗口效果条目,本域零状态副本写)。"""
    seqs = resolve_plane_node_seqs('')
    seq2 = seqs[2]
    last_r = len(seq2)
    assert sequence_next((2, last_r), {1: seqs[1], 2: seq2}) is None, \
        '前置:P2 末后继应为 None(P3 未注册)'
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic(gs.node_seq_by_plane, {1: seqs[1], 2: seq2},
                   produced_by='test-seed', evidence='t:seqs', sig=_LSIG)
    gs.write_logic(gs.pending_strategy_grants, ((_CARD, 1),),
                   produced_by='test-seed', evidence='t:queue', sig=_LSIG)
    advance_node_effective(gs, (2, last_r), actor='TestDriver', sig=_OBS_LSIG,
                           source='observation')
    assert gs.pending_strategy_grants.value == ((_CARD, 0),), \
        'P2 末节点 tick 递减形态漂移'
    seq_before = gs.write_seq
    out = report_node_advance(gs, trigger='settle_confirm', sig=_LSIG)
    assert out.applied and out.reason == 'match_end', \
        f'P2 末上报应为终局事件: {out.reason}'
    assert gs.pending_strategy_grants.value == ((_CARD, 0),), \
        '终局事件后队列被弹除/改写'
    assert gs.write_seq == seq_before, '终局事件出现效果写行'


def test_repeat_cycle_fires_fourth_and_eighth_window() -> None:
    """好运令牌·彩 周期全链(登记@4 + tick 递减 + 到点发放 + repeat 回队,
    REVIEW-T374.md §4 锁 4):拿卡后登记 4 拍 → 第 4 后继窗减到 0 → 到点
    发放 1 件入栏 ∧ 队列以同参重排队 (('好运令牌·彩', 4),)(非弹除
    清空)→ 再推进 4 窗减到 0 → 第 8 后继窗再发 1 件 ∧ 队列仍恒 1 条目
    ——拿卡后每 4 节点窗各 1 件至局终的周期语义(计数起点 = 拿卡节点
    后继窗,家族口径);tick 递减效果条目零改动,递减对重排队条目与首登条目
    同形。"""
    gs = _gs_with_queue(1, 1, (('好运令牌·彩', 4),), equips=[])
    for _r in range(2, 6):
        _advance(gs, 1, _r)
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 0),), \
        f'第 4 后继窗应减到 0: {gs.pending_strategy_grants.value}'
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:好运令牌(placed=True)',), \
        f'第 4 窗发放: {effects}'
    assert gs.equips.value == ['好运令牌'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 4),), \
        f'首发后重排队列: {gs.pending_strategy_grants.value}'
    for _r in range(6, 10):
        _advance(gs, 1, _r)
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 0),), \
        f'第 8 后继窗应减到 0: {gs.pending_strategy_grants.value}'
    effects = discharge_due_strategy_grants(
        gs, rand=False, rng=random.Random(0), sig=_LSIG)
    assert effects == ('delayed_grant:好运令牌(placed=True)',), \
        f'第 8 窗再发: {effects}'
    assert gs.equips.value == ['好运令牌', '好运令牌'], \
        f'装备栏(两件): {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('好运令牌·彩', 4),), \
        f'再发后队列长度应恒 1: {gs.pending_strategy_grants.value}'
