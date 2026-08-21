# -*- coding: utf-8 -*-
"""r350(局38 boss -34 根因):锁线后 _pair_wants 只认线形态羁绊。

局38 实证:jizi 锁线下艾丝妲(flows=DOT∈引擎阵营)被 r245 的
「引擎∪形态」放行集收进 4 张,占 2 部署位——线形态(列车4+护盾3)
不需要 DOT,boss 板面 3 线内+3 线外散件 → -34。
锁:①艾丝妲(DOT flow)在 jizi 锁线下被拒;②护盾系挂件放行
(r245 线内需求语义保留);③未锁线桥方向期引擎门不变。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _sess(line: str | None = None, bridge: str | None = None) -> StrategySession:
    s = StrategySession()
    s.locked_line = line
    s.bridge_id = bridge
    return s


def _card(faction: str, name: str = '') -> object:
    from types import SimpleNamespace
    return SimpleNamespace(name=name or '测试', faction=faction, cost=1)


def test_locked_line_rejects_engine_faction_outside_form() -> None:
    """r350 主锁:jizi 锁线下,DOT flow 挂件(艾丝妲)不再被
    引擎阵营兜底放行(局38 4 张艾丝妲占位根因)。"""
    st = GameState(plane=1, round_num=7, gold=30, level=5,
                   board={'列车同行': 2, '银河学者': 2}, bench=[])
    # 艾丝妲:银河学者+DOT flow;owned 里银河学者在(凑对路径可达门)
    ok = LineStrategy._pair_wants(_card('银河学者', '艾丝妲'), st,
                                  _sess(line='jizi_train'))
    assert not ok, '锁线形态(列车+护盾)外的引擎阵营挂件必须拒(r350)'


def test_locked_line_accepts_form_faction() -> None:
    """r245 语义保留:护盾系挂件(线形态羁绊)锁线下放行。"""
    st = GameState(plane=1, round_num=7, gold=30, level=5,
                   board={'列车同行': 2, '护盾': 1}, bench=[])
    ok = LineStrategy._pair_wants(_card('护盾', '砂金'), st,
                                  _sess(line='jizi_train'))
    assert ok, '线形态羁绊(护盾)挂件必须放行(r245 线内需求保留)'


def test_bridge_direction_keeps_engine_gate() -> None:
    """未锁线桥方向期:引擎阵营门不变(r350 只收锁线分支)。
    艾丝妲(银河学者+DOT flow):阵营门靠 owned(银河学者在板)
    +引擎门靠 flows(DOT∈引擎)——两门都过才放行。"""
    st = GameState(plane=1, round_num=3, gold=20, level=3,
                   board={'银河学者': 1, '仙舟': 1}, bench=[])
    ok = LineStrategy._pair_wants(_card('银河学者', '艾丝妲'), st,
                                  _sess(bridge='xz_dot'))
    assert ok, '桥方向期引擎门(DOT∈引擎)应放行艾丝妲(r242 不变)'
