# -*- coding: utf-8 -*-
"""r308 节点感知连胜 EV 测试(用户指正:按节点算)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(rnd: int, streak: int, node: str):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, rnd, 5, 14, 60
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='忘归人', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.last_streak = streak
    sess.node_type_current = node
    sess.last_state = st
    return s, st, sess


def test_early_battle_keeps_floor() -> None:
    """r308:r3 battle(剩 6)息成本>奖励 EV → 守 10 地板
    (r307 的无条件降地板是错的——用户指正)。"""
    s, st, sess = _mk(rnd=3, streak=3, node='battle')
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '忘归人' not in buys, f'r3 battle 该攒息,得 {buys}'


def test_late_encounter_lowers_floor() -> None:
    """r7 encounter(剩 2)保连胜 EV 优 → 降地板 5。"""
    s, st, sess = _mk(rnd=7, streak=3, node='encounter')
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '忘归人' in buys, f'r7 遭遇连胜 3 该降地板,得 {buys}'


def test_reward_node_never_invests() -> None:
    """reward 节点无战力要求,连胜零成本 → 不降地板(不用投资)。
    r354 语义修正(同 r307 streak0):原「不买」是 LevelUp 分食
    预算副作用;总成本门后 reward 帧升不完不提案 → 集中买可
    放板面件。reward 帧的真语义=不为连胜**降地板投资**;板面
    阵营件在标准预算内买是堆深非破息。断言:无 LevelUp +
    若买则买的是板面阵营件(金14-地板10=4 预算内 3 费)。"""
    s, st, sess = _mk(rnd=8, streak=3, node='reward')
    acts = s.decide_prep(st, sess, None)
    lvs = [a for a in acts if type(a).__name__ == 'LevelUp']
    assert not lvs, f'reward 帧升不完级不提案 LvUp:{[type(a).__name__ for a in acts]}'
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert all(b in ('忘归人',) for b in buys), \
        f'只允许板面阵营件(仙舟2),得 {buys}'
