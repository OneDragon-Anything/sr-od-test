# -*- coding: utf-8 -*-
"""r248 重启锁线恢复测试(方向恢复双通道)。"""
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(plane: int = 2, round_num: int = 6):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num = plane, round_num
    st.level, st.gold, st.hp = 8, 156, 40
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def test_board_recovers_jizi_lock():
    """修 A:重启后 CARRY 没了但列车2 在板 → 恢复 jizi 锁
    (实锤场景:列车2 被判无方向拆散落 DOT)。"""
    s, st, sess = _mk()
    st.board = {'列车同行': 2, '护盾': 2, '仙舟': 2}
    st.bench = []    # 无 CARRY 在手
    st.shop = []
    s.update_target(st, sess, None)
    assert sess.locked_line == 'jizi_train'   # 恢复,不落 DOT


def test_no_direction_still_falls_back():
    """真无方向(无引擎羁绊≥2)仍落 DOT 兜底(可达性保留)。"""
    s, st, sess = _mk()
    st.board = {'银河学者': 1, '群攻': 1}    # 全散
    st.bench = []
    st.shop = []
    s.update_target(st, sess, None)
    assert sess.locked_line == 'dot_fallback'


def test_board_direction_blocks_fallback():
    """修 B:板面有引擎方向(仙舟2)但无线匹配 P2 键 →
    不落兜底,保持攒金等信号(不拆板)。"""
    s, st, sess = _mk()
    # 仙舟2 在板但 jizi 的 P2 键(列车4+护盾3)不含仙舟——
    # 恢复通道不中,但引擎方向守卫拦截兜底
    st.board = {'仙舟': 2, '银河学者': 1}
    st.bench = []
    st.shop = []
    s.update_target(st, sess, None)
    assert sess.locked_line is None    # 不落 DOT
    assert sess.bridge_id is None      # 也不硬造桥


def test_p1_early_no_fallback_anyway():
    """P1 无兜底(兜底只在 P2+;P1 走桥/等信号)。"""
    s, st, sess = _mk(plane=1, round_num=5)
    st.board = {}
    st.bench = []
    st.shop = []
    s.update_target(st, sess, None)
    assert sess.locked_line is None
