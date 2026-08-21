# -*- coding: utf-8 -*-
"""r245 稳定性第二批:锁线形态对齐(P2 桥 core 并入线内件)。"""
from sr_od.application.currency_war.cw_state import GameState, ShopCard
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(plane: int = 2):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = plane, 7, 30, 80
    st.board = {'列车同行': 2}
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    return s, st, sess


def test_p2_shield_core_buyable():
    """r245 风险2:锁 jizi 后 P2 期砂金(护盾桥 core)可买
    (静态 opportunistic 只有 P1 视角名单,形态需求随位面
    动态扩展——P2 列车4+护盾3 成型不再缺件)。"""
    s, st, sess = _mk(plane=2)
    assert s._line_wants(
        ShopCard(x=0, faction='公司', name='砂金', cost=2), st, sess)
    assert s._line_wants(
        ShopCard(x=1, faction='夜之半神', name='丹恒·腾荒', cost=2),
        st, sess)


def test_irrelevant_still_rejected():
    """无关节(万敌夜半)仍拒(并集不是全放行)。"""
    s, st, sess = _mk(plane=2)
    assert not s._line_wants(
        ShopCard(x=0, faction='夜之半神', name='万敌', cost=1), st, sess)


def test_p1_pool_used_on_p1():
    """P1 期并的是 P1 池 core(仙舟桥件),不是 P2 的。"""
    s, st, sess = _mk(plane=1)
    assert s._line_wants(
        ShopCard(x=0, faction='仙舟', name='藿藿', cost=1), st, sess)
    # P2 桥 core(砂金)在 P1 也可买——桥 core 全并集
    # (3费以下都便宜,P1 末攒 P2 形态件是设计意图)
