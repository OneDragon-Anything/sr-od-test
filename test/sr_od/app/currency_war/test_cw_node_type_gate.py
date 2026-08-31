# -*- coding: utf-8 -*-
"""节点类型语义门测试(r80 审计 P0;2-7 误判 boss 实证驱动)。

锁两道门(gate_node_type):
1. boss 轮次门:round < 8 读到「首领」= 即将到来的 boss 节点标签(2-7 实证 x1341)→ None;
   round ≥ 8(真 boss 轮)→ 放行。
2. 标签位置门:标签 x 与当前槽 cx 错位 > 容差 → None(张冠李戴)。
误判代价实证:2-7 被判 boss → _boss_spend 提前花光资源 → HP17 惨胜。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'src'))

from sr_od.application.currency_war.obs.cw_observation import (
    _BOSS_MIN_ROUND,
    _NODE_LABEL_X_TOL,
    gate_node_type,
)


def test_boss_round_gate_rejects_upcoming_boss_label():
    """2-7 实证:round=7 读到「首领」(即将到来的 boss 节点标签)→ None。
    r80 审计 a 收紧:round=8 同样拒(boss=第 9 轮;人身意外险+补给后 ≥10,取 9 下限)。"""
    assert gate_node_type('boss', 7) is None
    assert gate_node_type('boss', 8) is None   # 收紧:与 boss 相邻的前置轮,标签更早出现
    assert gate_node_type('boss', 1) is None
    assert gate_node_type('boss', None) is None   # 轮次读不到 → 不信 boss


def test_boss_round_gate_passes_real_boss_round():
    """真 boss 轮(位面最后节点 = 第 9 轮)→ 放行。"""
    assert gate_node_type('boss', 9) == 'boss'
    assert _BOSS_MIN_ROUND == 9


def test_label_position_gate_rejects_mismatch():
    """标签 x=1341(即将到来的 boss 节点)vs 当前槽 cx≈900 → 错位 > 容差 → None。"""
    assert abs(1341 - 900) > _NODE_LABEL_X_TOL   # 实证数据确超容差
    assert gate_node_type('boss', 9, label_x=1341, current_cx=900) is None


def test_label_position_gate_passes_aligned():
    """标签在当前节点下方(对齐)→ 放行。"""
    assert gate_node_type('supply', 3, label_x=905, current_cx=900) == 'supply'
    assert gate_node_type('boss', 9, label_x=1340, current_cx=1310) == 'boss'


def test_non_boss_types_unaffected_by_round_gate():
    """非 boss 类型(补给/遭遇等)无轮次语义约束 → 只受位置门。"""
    assert gate_node_type('supply', 2) == 'supply'
    assert gate_node_type('encounter', 1) == 'encounter'


def test_none_passthrough():
    """None → None(无标签不造数据)。"""
    assert gate_node_type(None, 9) is None
    assert gate_node_type(None, None) is None
