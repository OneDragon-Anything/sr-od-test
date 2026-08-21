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
    """连胜≥2 且硬节点(遭遇/boss)→ 破息地板降 5。
    r308 修正:早 battle(胜率高)不降——节点感知判据。
    边界:金 14(地板 10 → 预算 4 买不起 3 费;地板 5 → 预算 9 买得起)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 7, 5, 14, 60
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='忘归人', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.last_streak = 3
    sess.node_type_current = 'encounter'   # r308:节点上下文
    sess.last_state = st
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '忘归人' in buys, f'r7 遭遇连胜 3 该降地板投资,得 {buys}'


def test_broken_streak_keeps_floor() -> None:
    """连胜 0-1(断)→ 地板 10 不变(原语义)。同边界对照:金 14 r7。
    r354 语义修正:原「不买」实为 LevelUp(单击价门)分食预算的
    副作用——总成本门后升不完不提案,预算流给买牌;r352 集中买
    放行板面阵营件(仙舟 2 在板,gap=1)。地板本意=保息;金 14
    已破息线,无息可保,买板面件堆深更优。断言改:不提案
    LevelUp(半吊子经验禁)+ 买的是板面阵营件(投资有方向)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 7, 5, 14, 60
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='忘归人', cost=3)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.last_streak = 0   # 无连胜
    sess.node_type_current = 'encounter'
    sess.last_state = st
    acts = s.decide_prep(st, sess, None)
    lvs = [a for a in acts if type(a).__name__ == 'LevelUp']
    assert not lvs, f'升不完级(金14 vs 总成本20+)不得提案 LevelUp:{acts}'
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert buys == ['忘归人'], \
        f'破息线金 14 该买板面阵营件(仙舟2 gap=1),得 {buys}'
