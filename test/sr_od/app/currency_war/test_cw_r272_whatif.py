# -*- coding: utf-8 -*-
"""r272 what-if 别名突变修复测试(审查②#5 活 bug)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def test_catchup_does_not_mutate_state() -> None:
    """catchup 态决策不得污染入参 state(war+低血触发追赶路径)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 5, 4, 56, 40
    st.board = {'仙舟': 2, '列车同行': 2}
    st.bench = []
    sess = StrategySession()
    sess.v2_state = ('war', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'jizi_train'
    # last_state 别名模拟 shop.py 的前置存储(污染传播路径)
    sess.last_state = st
    gold_before = st.gold
    s.decide_prep(st, sess, None)
    assert st.gold == gold_before, \
        f'catchup 污染入参 gold:{gold_before}→{st.gold}'
    assert sess.last_state.gold == gold_before, \
        f'污染传播到 last_state:{gold_before}→{sess.last_state.gold}'
