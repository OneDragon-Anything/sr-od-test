"""kernel 决策上下文槽(dtag 关联锚)锁面。

被测 = src/sr_od/application/currency_war/kernel/cw_decision_ctx.py;
设计出处 = changes/2026-10-24-strategy-telemetry/details/capture-store.md §2
(take 读后清语义 / reset 测试复位口)。
"""

from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_decision_ctx import (
    reset_decision_tag,
    set_decision_tag,
    take_decision_tag,
)


def test_take_reads_once_and_clears() -> None:
    """take = 读后清:同一 dtag 只可被读走一次(防重复并入后续无关回执)。"""
    reset_decision_tag()
    set_decision_tag('probe:1')
    assert take_decision_tag() == 'probe:1'
    assert take_decision_tag() is None


def test_reset_clears_slot() -> None:
    """复位口:置位后 reset 零残留(测试与装配复位的正规入口)。"""
    set_decision_tag('probe:2')
    reset_decision_tag()
    assert take_decision_tag() is None
