# -*- coding: utf-8 -*-
"""连胜奖励表守卫(r305 域)。

2026-09-03 瘦身批删两条:VLM 判读表(手抄表值,被本文件守卫推导覆盖,
纪律 7/9)、BASE_INCOME 近似锁(自供「近似待采集成表」,已知 wart 立锁
违纪律 14,挂账归数据采集批)。
"""
from __future__ import annotations


from sr_od.application.currency_war.kernel.cw_economy import streak_gold


def test_streak_gold_table_constant() -> None:
    """ADR-0262:STREAK_GOLD_TABLE 常量与函数逐点一致守卫(防表与实现漂移)。"""
    from sr_od.application.currency_war.kernel.cw_economy import STREAK_GOLD_TABLE
    for streak in range(0, len(STREAK_GOLD_TABLE) + 3):
        expected = STREAK_GOLD_TABLE[min(streak, len(STREAK_GOLD_TABLE) - 1)]
        assert streak_gold(streak) == expected, f'streak={streak}'
