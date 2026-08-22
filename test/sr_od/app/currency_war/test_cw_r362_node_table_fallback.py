# -*- coding: utf-8 -*-
"""r362 首节点类型冷启动兜底测试(局47:1-1/1-2 reward 记成普通战斗)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.battle_loop import (
    CurrencyWarRunLoop,
)

_TABLE = ['reward', 'reward', 'battle', 'battle',
          'supply', 'battle', 'encounter', 'reward', 'boss']


class _Sess:
    plane_node_table = list(_TABLE)
    node_type_current = None


def test_table_fallback_first_nodes() -> None:
    """r1/r2(current 未读到)按开局槽序表兜底 = reward。"""
    s = _Sess()
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 1) == 'reward'
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 2) == 'reward'


def test_table_fallback_mid_and_boss() -> None:
    """r5 supply / r9 boss(表槽序=位面节点序)。"""
    s = _Sess()
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 5) == 'supply'
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 9) == 'boss'


def test_table_fallback_miss_cases() -> None:
    """越界/表空 → None(调用方退普通战斗,不伪装)。"""
    s = _Sess()
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 10) is None
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 0) is None
    s.plane_node_table = None
    assert CurrencyWarRunLoop._node_type_from_table(s, 1, 1) is None
