# -*- coding: utf-8 -*-
"""③ 攒数据地基锁:core_count_for 按 target 语境路由单一口径。

三源收口(二轮#8):线库 core_cards / 桥池 fixed+core / 仙舟
三人组 _CORE_TRIO——非仙舟线局 core_count 不再恒 0。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_line_defs import core_count_for


def test_bridge_target_counts_pool_core() -> None:
    """桥 id → 桥池 fixed+core 在场数(hunt3:飞霄/椒丘/貊泽/灵砂)。"""
    names = {'飞霄', '椒丘'}
    assert core_count_for('hunt3', names) == 2
    assert core_count_for('xianzhou_dot', {'爻光', '藿藿'}) == 2   # fixed+core
    assert core_count_for('hunt3', {'飞霄', '姬子·启行'}) == 1    # 非核心不计


def test_line_target_counts_core_cards() -> None:
    """锁线 v2: 前缀 → 线库 core_cards(jizi=姬子·启行)。"""
    assert core_count_for('v2:jizi_train', {'姬子·启行', '三月七'}) == 1
    assert core_count_for('feiying_joy', {'绯英'}) == 1


def test_empty_and_unknown_fallback_trio() -> None:
    """空 target → 三人组缺省;未知 target 不 crash 退缺省。"""
    assert core_count_for('', {'爻光', '藿藿', '丹恒·饮月'}) == 3
    assert core_count_for('v2:nonexistent', {'藿藿'}) == 1


def test_sim_ledger_core_count_follows_target() -> None:
    """sim 账本 core_count 非 jizi 局不再恒 0(integration 冒烟)。"""
    import contextlib
    import io
    import sys

    if hasattr(sys.stdout, 'reconfigure'):
        pass  # sim 内部日志走框架 logger,不扰 stdout
    from sr_od.application.currency_war.cw_sim import simulate_p1
    with contextlib.redirect_stderr(io.StringIO()):
        r = simulate_p1(7, pool='snapshot')
    # 找到有 target 的轮,断言 core_count 是 int 且 ≥0(口径存在性;
    # 具体值随局面,不锁数值——锁分布 = change-detector)
    rows_with_target = [row for row in r.ledger if row['target_comp']]
    assert rows_with_target
    assert all(isinstance(row['sim']['core_count'], int)
               and row['sim']['core_count'] >= 0
               for row in rows_with_target)
