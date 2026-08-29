# -*- coding: utf-8 -*-
"""r305 采集数据判读:奖励弹窗样本 × VLM(用户指路)。"""
from __future__ import annotations


from sr_od.application.currency_war.kernel.cw_economy import streak_gold


def test_streak_table_vlm_verified() -> None:
    """VLM 双样本判读的连胜表(0-1→1,2-4→2,5→3,6+→4)。"""
    assert streak_gold(0) == 1
    assert streak_gold(1) == 1
    assert streak_gold(2) == 2
    assert streak_gold(4) == 2
    assert streak_gold(5) == 3
    assert streak_gold(6) == 4
    assert streak_gold(9) == 4   # 6+ 表尾截断边界(ADR-0262)
    assert streak_gold(10) == 4


def test_streak_gold_table_constant() -> None:
    """ADR-0262:STREAK_GOLD_TABLE 常量与函数逐点一致守卫(防表与实现漂移)。"""
    from sr_od.application.currency_war.kernel.cw_economy import STREAK_GOLD_TABLE
    for streak in range(0, len(STREAK_GOLD_TABLE) + 3):
        expected = STREAK_GOLD_TABLE[min(streak, len(STREAK_GOLD_TABLE) - 1)]
        assert streak_gold(streak) == expected, f'streak={streak}'


def test_base_income_varies_by_node() -> None:
    """VLM 判读:基础奖励随节点变(r2=4/r3=5)——
    sim BASE_INCOME=5 是近似,采够样本后建表。"""
    from sr_od.application.currency_war.kernel.cw_economy import BASE_INCOME
    assert BASE_INCOME == 5   # 近似值,待采集成表替换
