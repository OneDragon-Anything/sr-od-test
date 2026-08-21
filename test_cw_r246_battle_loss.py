# -*- coding: utf-8 -*-
"""r246 普通战斗败检测测试(P2 三连败 economy 不切的回归锁)。"""
from sr_od.application.currency_war.cw_performance import RoundOutcome
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(hp: int = 80):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, 7, 30, hp
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    return s, st, sess


def test_normal_battle_loss_feeds_miss():
    """普通战斗败(HP 降 ≥10)喂 E1_miss——两连败切 war
    (r246:P2 三连败 v2_mode 恒 economy 的回归锁)。
    注:首轮带 hp_after 才能和 prev 比差分。"""
    s, st, sess = _mk(hp=44)
    st.hp = 44
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                                comp_tag='', hp_after=44))
    st.hp = 24
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=2, plane=2, node_type='普通战斗',
                                comp_tag='', hp_after=24))
    # 两连败(44→24 一档 miss + 24→5 一档 miss)需第三轮凑满 M=2?
    # 不——第二轮 44→24 已是第 1 个 miss,补第三轮 24→5 第 2 个
    st.hp = 5
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=3, plane=2, node_type='普通战斗',
                                comp_tag='', hp_after=5))
    assert sess.v2_state[0] == 'war'


def test_normal_battle_win_stays_economy():
    """普通战斗胜(HP 不降)不喂 miss——economy 保持。"""
    s, st, sess = _mk(hp=60)
    st.hp = 60
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                                comp_tag=''))
    st.hp = 60
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=2, plane=2, node_type='普通战斗',
                                comp_tag='', hp_after=60))
    assert sess.v2_state[0] == 'economy'


def test_small_drop_not_miss():
    """小掉血(<10,如 boss 机制的 5-8 点)不算败——防噪声。"""
    s, st, sess = _mk(hp=50)
    st.hp = 50
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=1, plane=2, node_type='普通战斗',
                                comp_tag=''))
    st.hp = 45
    s.on_round_end(st, sess, None,
                   RoundOutcome(round_num=2, plane=2, node_type='普通战斗',
                                comp_tag='', hp_after=45))
    assert sess.v2_state[0] == 'economy'
