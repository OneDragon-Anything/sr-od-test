# -*- coding: utf-8 -*-
"""r262/r263 升人口门测试(局15 板深根因;r263 修订:lv5 基线)。"""
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
    """P1 lv4 金 30 → 升人口(宽松门 10;旧门 50 恒不触发)。"""
    s, st, sess = _mk(round_num=4, level=4, gold=30)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts), \
        f'lv<5 该升,得 {[type(a).__name__ for a in acts]}'


def test_level5_reached_strict_again() -> None:
    """lv5(过渡成型基线,攻略[13])后恢复满息门(金 40 不升)。"""
    s, st, sess = _mk(round_num=4, level=5, gold=40)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, LevelUp) for a in acts), \
        'lv5+ 守息(过渡成型攒息)'


def test_lv4_late_still_relaxed() -> None:
    """lv4 晚期(罕见滞后)仍宽松升到 5(r263:门只看 lv 不看轮)。"""
    s, st, sess = _mk(round_num=7, level=4, gold=30)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, LevelUp) for a in acts), \
        'lv<5 无论轮次都该升(lv5 基线)'


def test_low_gold_never_level() -> None:
    """金 8(<xp+10)→ 不升(宽松门也保命)。"""
    s, st, sess = _mk(round_num=3, level=4, gold=8)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, LevelUp) for a in acts)
