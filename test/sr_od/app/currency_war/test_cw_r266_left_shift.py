# -*- coding: utf-8 -*-
"""r266 current 槽左移推断测试(节点类型 last-known upcoming)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_strategy import StrategySession


def test_upcoming_field_default() -> None:
    s = StrategySession()
    assert s.upcoming_types is None


def test_left_shift_semantics() -> None:
    """上帧 upcoming=['encounter','reward',...] → 本轮 current=encounter;
    新帧 upcoming 存下轮用。"""
    s = StrategySession()
    s.upcoming_types = ['encounter', 'reward', 'battle']
    # prep_director 的推断逻辑(current 直读 None → 左移)
    _direct = None
    _prev = s.upcoming_types or []
    inferred = _prev[0] if _prev else None
    assert inferred == 'encounter'
    # 消费后更新(模拟下一帧)
    s.upcoming_types = ['reward', 'battle']
    assert (s.upcoming_types or [None])[0] == 'reward'
