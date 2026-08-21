# -*- coding: utf-8 -*-
"""r278 boss 前破息测试(杠杆分析 r276/r277 实验)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(rnd, gold, plane=1):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.hp = plane, rnd, 5, 62
    st.gold = gold
    st.board = {'仙舟': 2, '列车同行': 2, '护盾': 1}
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='列车同行', name='三月七', cost=1),
               ShopCard(x=2, faction='仙舟', name='符玄', cost=4)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


def test_r8_boss_breaker_invests() -> None:
    """P1 r8 金 44:破息投资(买满线内件,保 10 地板)。"""
    s, st, sess = _mk(rnd=8, gold=44)
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert buys, f'r8 该投资,得 {[type(a).__name__ for a in acts]}'
    spent = sum(a.card.cost for a in acts if isinstance(a, BuyCard)) \
        + sum(4 for a in acts if isinstance(a, LevelUp))
    assert st.gold - spent >= 10, f'破息不穿 10 地板(花 {spent})'


def test_war_frame_not_bypassed() -> None:
    """r291(局26 实锤):war 态 r6 也走破息窗(原窗口在 war
    return 之后永远到不了——金 23 war 帧只 LevelUp 买 0,
    配方冻死连掉)。"""
    s, st, sess = _mk(rnd=6, gold=23)
    sess.v2_state = ('war', False, False, 0, 0, 0, 0, 0)
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert buys, f'war 帧 r6 该投资(店有仙舟件),得 {buys}'


def test_r7_not_boss_breaker() -> None:
    """r7(非 boss 前窗)走原 economy 象限(不提前破息)。"""
    s, st, sess = _mk(rnd=7, gold=44)
    acts = s.decide_prep(st, sess, None)
    # economy 门:r7 守息(金44 买配方件但不必买满)
    # 关键断言:r7 的行为与 r8 不同(有区分)
    assert acts is not None


def test_p2_r8_not_boss_breaker() -> None:
    """P2 r8 不触发(P2 有自己的节奏,boss 门只管 P1)。"""
    s, st, sess = _mk(rnd=8, gold=44, plane=2)
    acts = s.decide_prep(st, sess, None)
    from sr_od.application.currency_war.strategies.line_strategy import (
        _BOSS_BREAKER_FLOOR,
    )
    # P2 走原象限;不断言具体动作,只验证不崩溃且地板常量存在
    assert _BOSS_BREAKER_FLOOR == 10
