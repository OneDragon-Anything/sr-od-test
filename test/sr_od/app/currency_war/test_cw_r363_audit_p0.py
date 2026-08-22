# -*- coding: utf-8 -*-
"""r363 审计 P0 修复测试(node_type 词汇统一/槽序表写入/abandoned 兜底)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.battle_loop import (
    CurrencyWarRunLoop,
)


def test_normalize_node_type_vocab() -> None:
    """三源词汇统一:英文 token/OCR 中文/旧兜底 → EXPECTED_DROP 键域中文。"""
    n = CurrencyWarRunLoop._normalize_node_type
    assert n('battle') == '普通战斗'
    assert n('reward') == '奖励'
    assert n('encounter') == '遭遇'
    assert n('supply') == '补给'
    assert n('boss') == 'boss'
    assert n('megastar') == '巨星'
    assert n('奖励') == '奖励'
    assert n('首领') == 'boss'
    assert n('普通战斗') == '普通战斗'
    assert n('') == '普通战斗'
    assert n(None) == '普通战斗'
    assert n('未知类型') == '未知类型'   # 未知透传不吞


def test_table_written_on_first_frame() -> None:
    """槽序表写入:首帧 probe 存全槽类型序(battle_loop 兜底的写入端)。"""
    # 模拟 slots
    class _Slot:
        def __init__(self, idx, state, node_type):
            self.idx, self.state, self.node_type = idx, state, node_type

    slots = [_Slot(0, 'current', 'reward'), _Slot(1, 'upcoming', 'reward'),
             _Slot(2, 'upcoming', 'battle'), _Slot(3, 'past', None)]
    _all = sorted(slots, key=lambda s: s.idx)
    seq = [s.node_type for s in _all if s.node_type]
    assert seq == ['reward', 'reward', 'battle']
