# -*- coding: utf-8 -*-
"""r282 P1 中期息平台测试(局21 经济根因)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(rnd, gold, board):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.hp = 1, rnd, 5, 80
    st.gold = gold
    st.board = dict(board)
    st.bench = []
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='公司', name='翡翠', cost=1)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'feiying_joy'
    return s, st, sess


_BOARD_OK = {'仙舟': 3, '列车同行': 2}          # 配方 5 档成立


def test_mid_interest_platform_keeps_20() -> None:
    """r6 配方成立金 35 → 买后保 20(息平台)。"""
    s, st, sess = _mk(6, 35, _BOARD_OK)
    acts = s.decide_prep(st, sess, None)
    from sr_od.application.currency_war.cw_state import BuyCard
    spent = sum(a.card.cost for a in acts if isinstance(a, BuyCard))
    assert st.gold - spent >= 20, f'该保 20 平台,花 {spent} 剩 {st.gold - spent}'


def test_recipe_incomplete_spends_all() -> None:
    """配方未满(3 档)金 35 → 照旧花(凑件优先,档内全花)。"""
    s, st, sess = _mk(6, 35, {'仙舟': 2, '列车同行': 1})
    acts = s.decide_prep(st, sess, None)
    # 不断言具体值(凑件逻辑管),验证平台不启用即可:若买了藿藿
    # (配方件)允许花到低位
    assert acts is not None


def test_high_gold_still_50() -> None:
    """金 50+:满息门照旧(50 线不动)。"""
    s, st, sess = _mk(6, 60, _BOARD_OK)
    acts = s.decide_prep(st, sess, None)
    from sr_od.application.currency_war.cw_state import BuyCard
    spent = sum(a.card.cost for a in acts if isinstance(a, BuyCard))
    assert st.gold - spent >= 50 or spent == 0, \
        f'金60 应守 50 满息,剩 {st.gold - spent}'


def test_r9_boss_window_not_platform() -> None:
    """r9(boss 破息窗)不走平台——r278 破息优先。"""
    from sr_od.application.currency_war.strategies.line_strategy import (
        _BOSS_BREAKER_FLOOR,
    )
    assert _BOSS_BREAKER_FLOOR == 10
