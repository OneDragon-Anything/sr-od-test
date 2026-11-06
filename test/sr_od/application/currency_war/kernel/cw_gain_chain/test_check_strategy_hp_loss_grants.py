"""策略卡损血档位触发发放检查效果条目测试(镜像 src = kernel/cw_gain_chain.py
的 check_strategy_hp_loss_grants)。

测试面依据 = 迭代设计 designs/T-142-baoxian.md §4 锁 2 +
REVIEW-T142(直构形态先例 = 同目录 test_check_strategy_win_gold_grants.py
的状态容器直置):
- 桶边界矩阵:19 → 0 桶余 19 / 20 → 1 桶余 0 / 45 → 2 桶余 5(累积
  余数结转,「每损失20点」按全程累计读法,发放刻取模);
- 不持卡零写零累积不追溯(先损后拿卡,拿卡前损血不入账);
- 非正损血零过(胜局/奖励关恒胜/扑满豁免形态,零写零累积);
- 表载值单源:期望金/装备件数从 STRATEGY_HP_LOSS_GRANTS 表载值现算,
  期望装备名 = 同种子 rng 对同池重放(禁手抄池清单,T-116 家族口径)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_hp_loss_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_HP_LOSS_GRANTS,
    equips_by_category,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='TestDriver', mode='compute')

_CARD = '保险'
_THRESH, _GOLD_EACH, _CAT, _CNT = STRATEGY_HP_LOSS_GRANTS[_CARD]

#: 固定种子(采样名失配 = 换种子,禁手抄池清单)。
_EQ_SEED = 20261101


def _gs(*, card: str | None = _CARD) -> GameState:
    """直构 gs(节点 P1r3 观察定 evidence 帧;equips/gold 观察定发放
    承载;card=None = 未持卡)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=1, round_num=3, kind='battle'),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    if card is not None:
        gs.write_logic(gs.active_strategies, [card],
                       produced_by='test-seed', evidence='t:card',
                       sig=_LSIG)
    return gs


def _expected_pick(seed: int) -> str:
    return random.Random(seed).choice(equips_by_category(_CAT))


def test_below_threshold_accumulates_remainder() -> None:
    """锁 2 桶边界:19 → 0 桶,余 19 留存累积器(跨战结转载体;金零写、
    装备零写、发放刻取模未触——accum 值 = 19 本身)。"""
    gs = _gs()
    before = gs.write_seq
    gold, equips = check_strategy_hp_loss_grants(gs, 19, logic_sig=_LSIG,
                                                 rng=random.Random(_EQ_SEED))
    assert (gold, equips) == (0, []), '不足阈值误发放'
    assert gs.strategy_hp_loss_accum.value == 19, '余数未入累积器'
    assert gs.gold.value == 10 and gs.equips.value == [], '不足阈值误写'
    assert gs.strategy_hp_loss_accum.evidence \
        == 'strategy_hp_loss:accum:p1r3', 'evidence 帧漂移'
    assert gs.write_seq > before, '累积入账未落'


def test_exact_threshold_one_bucket() -> None:
    """锁 2 桶边界:20 → 1 桶余 0,发放刻取模回写 0;金 = 表载每档金,
    装备 = 表载件数(名 = 同种子重放采样值,∈ 简易池派生集)。"""
    gs = _gs()
    pick = _expected_pick(_EQ_SEED)
    gold, equips = check_strategy_hp_loss_grants(gs, _THRESH,
                                                 logic_sig=_LSIG,
                                                 rng=random.Random(_EQ_SEED))
    assert gold == _GOLD_EACH, '金值漂移(表载每档金)'
    assert equips == [pick], '装备发放漂移(表载件数 × 采样值)'
    assert gs.strategy_hp_loss_accum.value == 0, '发放刻未取模'
    assert gs.gold.value == 10 + _GOLD_EACH, '金写漂移'
    assert gs.equips.value == [pick], '装备入栏漂移'


def test_two_buckets_remainder_five() -> None:
    """锁 2 桶边界:45 → 2 桶余 5(累积余数结转「每 N 个 X」族口径;
    金 = 2 × 表载每档金,装备逐档发放,余 5 留存)。"""
    gs = _gs()
    pick = _expected_pick(_EQ_SEED)
    gold, equips = check_strategy_hp_loss_grants(gs, 45, logic_sig=_LSIG,
                                                 rng=random.Random(_EQ_SEED))
    assert gold == _GOLD_EACH * 2, '多桶金值漂移'
    assert equips == [pick, pick], '逐档装备发放漂移'
    assert gs.strategy_hp_loss_accum.value == 5, '余数结转漂移'
    assert len(gs.equips.value) == 2 * _CNT, '每档件数漂移'


def test_no_card_zero_write_and_no_retroactive() -> None:
    """锁 2 持卡域:未持卡损血 → 零写零累积(accum 未观察保持 None);
    拿卡后损血自 0 起算(先损后拿卡不追溯——30 = 0+30 恰 1 桶,非
    60 = 2 桶)。"""
    gs = _gs(card=None)
    before = gs.write_seq
    gold, equips = check_strategy_hp_loss_grants(gs, 30, logic_sig=_LSIG,
                                                 rng=random.Random(_EQ_SEED))
    assert (gold, equips) == (0, []), '未持卡误发放'
    assert gs.strategy_hp_loss_accum.value is None, '未持卡误入账'
    assert gs.write_seq == before, '未持卡误写'
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_LSIG)
    gold, equips = check_strategy_hp_loss_grants(gs, 30, logic_sig=_LSIG,
                                                 rng=random.Random(_EQ_SEED))
    assert gold == _GOLD_EACH and len(equips) == _CNT, \
        '拿卡后未发放(不追溯语义下 30 = 0+30 恰 1 桶)'
    assert gs.strategy_hp_loss_accum.value == 10, '不追溯语义破坏(应 30%20)'


def test_nonpositive_hp_lost_zero_pass() -> None:
    """锁 2 首序短路:hp_lost ≤ 0(胜局/奖励关恒胜/扑满豁免形态)→
    零写零累积(写序不变 = 全短路)。"""
    gs = _gs()
    before = gs.write_seq
    for lost in (0, -5):
        assert check_strategy_hp_loss_grants(
            gs, lost, logic_sig=_LSIG, rng=random.Random(_EQ_SEED)) == (0, [])
    assert gs.strategy_hp_loss_accum.value is None, '非正损血误入账'
    assert gs.write_seq == before, '非正损血误写'
