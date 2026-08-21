# -*- coding: utf-8 -*-
"""r262 早期升人口宽松门测试(局15 板深根因)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    GameState,
    LevelUp,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(round_num, level, gold, plane=1):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = \
        plane, round_num, level, gold, 80
    st.bench = []
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s, st, sess


def test_early_low_level_relaxed_gate() -> None:
    """P1 r4 lv4 金 30 → 升人口(宽松门 10;旧门 50 恒不触发)。"""
    s, st, sess = _mk(round_num=4, level=4, gold=30)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts), \
        f'早期低等该升,得 {[type(a).__name__ for a in acts]}'


def test_level6_reached_strict_again() -> None:
    """lv6 后恢复满息门(金 40 不升,守息)。"""
    s, st, sess = _mk(round_num=5, level=6, gold=40)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, LevelUp) for a in acts), \
        'lv6+ 该守息(满息门)'


def test_round7_strict_even_low_level() -> None:
    """r7+ 窗口外恢复满息门(后期利息优先)。"""
    s, st, sess = _mk(round_num=7, level=4, gold=40)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, LevelUp) for a in acts), \
        'r7+ 守息(窗口外)'


def test_low_gold_never_level() -> None:
    """金 8(<xp+10)→ 不升(宽松门也保命)。"""
    s, st, sess = _mk(round_num=3, level=4, gold=8)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, LevelUp) for a in acts)
