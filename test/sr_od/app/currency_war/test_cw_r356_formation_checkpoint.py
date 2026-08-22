# -*- coding: utf-8 -*-
"""r356(架构反思 B):P1 成型检查点 + formation_push 冲刺支。

局38-44 七败的结构性判读(策略架构反思.md):决策系统对成型
进度无感知、对成型 deadline 无响应——死循环(配方不满→息平台
不开→金留不住→买散件→更不满),七局七根因是发散信号。
锁:①检查点判据(r3 桥2/r6 配方5/r8 配方7/r9 boss 窗);
②gap>0 时 formation_push 接管(全预算买配方件);
③gap=0 时 boss_breaker 接管(原行为);
④配方断供逃生门(板面无配方阵营时放宽);
⑤围栏:配方未满时集中买只买 RECIPE_FACTIONS∩板面。"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_line_defs import p1_formation_target
from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def test_formation_target_checkpoints() -> None:
    """r356 主锁:阶段判据(r3 桥雏形/r6 配方5/r8 配方7/r9 boss)。"""
    # r3:引擎阵营 ≥2 档的阵营数
    assert p1_formation_target(2, {'仙舟': 2, '狼狩': 2, '公司': 1}) \
        == ('bridge2', 2, 2)      # 达标
    assert p1_formation_target(3, {'仙舟': 2, '公司': 1}) \
        == ('bridge2', 2, 1)      # 缺 1
    # r6:recipe_tier
    assert p1_formation_target(6, {'仙舟': 3, '持续伤害': 2}) \
        == ('recipe5', 5, 5)      # 恰达标
    assert p1_formation_target(5, {'仙舟': 2, '银河学者': 2}) \
        == ('recipe5', 5, 2)      # 缺 3(散面实例)
    # r8:7 档
    assert p1_formation_target(8, {'仙舟': 3, '列车同行': 2}) \
        == ('recipe7', 7, 5)
    # r9:boss 窗
    assert p1_formation_target(9, {}) == ('boss', 0, 0)


def test_formation_push_takes_over_on_gap() -> None:
    """r6 配方 gap(2/5)且店有配方件 → formation_push 接管,
    全预算买配方阵营件(非散件)。"""
    strat = LineStrategy()
    st = GameState(plane=1, round_num=6, gold=30, level=5, hp=70,
                   board={'仙舟': 2, '银河学者': 2}, bench=[],
                   shop=[SimpleNamespace(name='藿藿', faction='仙舟', cost=1),
                         SimpleNamespace(name='翡翠', faction='公司', cost=1)],
                   xp_progress=(48, 48))
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.node_type_current = 'battle'
    acts = strat.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '藿藿' in buys and '翡翠' not in buys, \
        f'配方件买/散件拒(围栏): {buys}'


def test_formation_met_falls_to_boss_breaker() -> None:
    """配方达标(5/5)→ boss_breaker 接管(原决战行为),
    板面阵营件(无论是否配方阵营)可进——围栏解除。
    场景:配方=仙舟3+列车2(满5),板面阵营=仙舟——仙舟件
    既在配方也在板面;用 jizi 线外但板面的设定验证集中买活着。"""
    strat = LineStrategy()
    st = GameState(plane=1, round_num=6, gold=40, level=5, hp=70,
                   board={'仙舟': 3, '列车同行': 2}, bench=[],
                   shop=[SimpleNamespace(name='忘归人', faction='仙舟', cost=3)],
                   xp_progress=(48, 48))
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.node_type_current = 'battle'
    acts = strat.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '忘归人' in buys, \
        f'配方满后集中买放板面阵营(围栏解除): {buys}'
