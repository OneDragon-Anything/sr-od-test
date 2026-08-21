# -*- coding: utf-8 -*-
"""r265 节点类型权威源测试(备战节点行 → session → on_round_end 消费)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_strategy import StrategySession


def test_session_field_default_none() -> None:
    """node_type_current 默认 None(未读到;消费方退普通战斗)。"""
    s = StrategySession()
    assert s.node_type_current is None


def test_field_writable() -> None:
    """prep_director 写 current 槽类型;battle_loop 读同名字段。"""
    s = StrategySession()
    s.node_type_current = '遭遇'
    assert s.node_type_current == '遭遇'
    # 消费端语义(None → 普通战斗)
    assert s.node_type_current or '普通战斗' == '遭遇'
    s2 = StrategySession()
    assert (s2.node_type_current or '普通战斗') == '普通战斗'
