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


# ---------------------------------------------------------------- # conftest 复位登记锁
# 以下两条成对(同文件按定义序执行,中间无其他测试):前条故意把槽
# 留脏不清,后条进场即断言槽空——锁 test/conftest.py 的 autouse 复位
# 登记(reset_decision_tag 进测试复位面):登记被移除时后条在全量/整文件
# 跑里红。后条单跑也绿(新进程槽天然空),顺序耦合只在成对跑里表达。


def test_conftest_reset_dirty_leaver() -> None:
    """成对前条:故意把槽留脏(不 take 不 reset),模拟跨测试残留源。"""
    set_decision_tag('stale:residue')


def test_conftest_reset_leaves_no_residue() -> None:
    """成对后条:进场即断言槽空(上条 teardown 由 conftest autouse 复位
    清场)——跨测试零 dtag 残留(landing §3.2 判据④)。"""
    assert take_decision_tag() is None
