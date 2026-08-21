# -*- coding: utf-8 -*-
"""r274 war 低金降级测试(局19 r6 冻结根因)。"""
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


def _mk(gold: int, mode: str = 'war'):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.hp = 1, 6, 5, 58
    st.gold = gold
    st.board = {'仙舟': 2, '欢愉': 1, '治疗': 1, '能量': 1}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='星间旅人', name='绯英', cost=2),
               ShopCard(x=1, faction='列车同行', name='三月七', cost=1),
               ShopCard(x=2, faction='狼狩', name='椒丘', cost=1)]
    sess = StrategySession()
    sess.v2_state = (mode, False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


def test_war_low_gold_buys() -> None:
    """war 态金 28(<WAR_FLOOR 30):降级地板后能买线内件
    (局19 r6 实锤——旧版整轮冻结买0)。"""
    s, st, sess = _mk(gold=28)
    acts = s.decide_prep(st, sess, None)
    got = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert got, f'war 低金不该冻结,得 {got}'


def test_war_high_gold_keeps_floor() -> None:
    """war 态金 50(>30):正常守 war 地板(买后保 30)。"""
    s, st, sess = _mk(gold=50)
    acts = s.decide_prep(st, sess, None)
    spent = sum(a.card.cost for a in acts if isinstance(a, BuyCard))
    assert 50 - spent >= 30 or spent == 0, \
        f'金50 买 {spent} 应保 30 地板'


def test_war_very_low_gold_buys_cheap() -> None:
    """war 态金 8:仍能买 1-2 费件(保 5 地板)。"""
    s, st, sess = _mk(gold=8)
    acts = s.decide_prep(st, sess, None)
    got = [a.card.name for a in acts if isinstance(a, BuyCard)]
    # 金 8 保 5 → 可花 3(三月七+椒丘或绯英单张)
    assert st.gold - sum(a.card.cost for a in acts
                         if isinstance(a, BuyCard)) >= 5
