# -*- coding: utf-8 -*-
"""r307 连胜 EV 接入决策测试(用户定调:真值先接入,后续对不上再改)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_economy import streak_gold
from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def test_streak_gold_single_source() -> None:
    """真值表单一源在 cw_economy(sim/策略共用)。"""
    assert streak_gold(0) == 1
    assert streak_gold(6) == 4


def test_streak_floor_lowered_in_breaker() -> None:
    """连胜≥2 → 破息地板降 5(保连胜 EV>攒息)。
    边界:金 14(地板 10 → 预算 4 买不起 3 费;地板 5 → 预算 9 买得起)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 6, 5, 14, 60
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='忘归人', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.last_streak = 3   # 连胜 3(奖励档 2)
    sess.last_state = st
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '忘归人' in buys, f'连胜 3 金 14 该降地板投资,得 {buys}'


def test_broken_streak_keeps_floor() -> None:
    """连胜 0-1(断)→ 地板 10 不变(原语义)。同边界对照:金 14。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 6, 5, 14, 60
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='忘归人', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.last_streak = 0   # 无连胜
    sess.last_state = st
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '忘归人' not in buys, f'无连胜金 14 该守 10 地板,得 {buys}'
