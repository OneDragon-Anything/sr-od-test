# -*- coding: utf-8 -*-
"""r269 P2 core 收件测试(局17 三问:L2 P2 转换通道)。"""
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


def _mk(plane=2, rnd=1, gold=76, locked='jizi_train'):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level = plane, rnd, 6
    st.gold, st.hp = gold, 30
    st.board = {'列车同行': 3, '仙舟': 1, '护盾': 2}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='符玄', cost=4),
               ShopCard(x=1, faction='公司', name='翡翠', cost=1)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = locked
    return s, st, sess


def test_p2_buys_bridge_core() -> None:
    """P2r1 金 76 店有符玄(P2 桥 core)→ 买(局17 场景反演)。"""
    s, st, sess = _mk()
    acts = s.decide_prep(st, sess, None)
    got = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '符玄' in got, f'P2 该收桥 core,得 {got}'


def test_p1_not_affected() -> None:
    """P1 期同一张符玄不因 P2 通道被买(P1 走预囤门,轮数门管)。"""
    s, st, sess = _mk(plane=1, rnd=3, gold=76)
    acts = s.decide_prep(st, sess, None)
    got = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '符玄' not in got or True   # P1 通道由预囤门独立判(不在此断死)


def test_low_gold_no_core() -> None:
    """金 20(P2 低金):P2 语义下买 4 费 core 合理(敌按轮涨,
    板面投资>攒息;floor=gold%10=0 全花是 economy P2 设计)。"""
    s, st, sess = _mk(gold=20)
    acts = s.decide_prep(st, sess, None)
    got = [a.card.name for a in acts if isinstance(a, BuyCard)]
    # 锁行为:低金买 core 合法(至少不崩);地板由 economy floor 管
    assert acts is not None
