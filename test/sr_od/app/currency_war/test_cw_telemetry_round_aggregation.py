"""轮聚合判读测试(旧视图族部分已随 W3 退役;本文件保留纯函数与运行时面)。

[退役墓碑,W3]旧视图测试族(test_round_actions_merge_across_carrier_frames /
test_supply_view_buys_not_zero_with_carrier_frames / test_economy_* ×6 /
test_rounds_view_counts_levelupshop)随 query_rounds/query_supply/query_economy
与 _load_decisions_rounds 旧流读面一并退役(r5-migration-plan.md §2 W3 删旧
读面;decisions 流写入端已随删除波 1 停写,视图对新局恒空)。同轮动作合并
语义的现役载体 = journal 行间差分(journal_query 视图族)。git 历史可复活。
"""

from __future__ import annotations


def test_plan_gold_flow_accepts_levelupshop() -> None:
    """逐项金流纯函数同桶:LevelUpShop 计支出(安灯分类器输入单一源;
    W3/T-255 起该纯函数的活消费方 = 运行时安灯 cw_screen_prep/run_state)。"""
    from sr_od.application.currency_war.telemetry.query import plan_gold_flow
    flow = plan_gold_flow([{'__type__': 'LevelUpShop', 'cost': 4}])
    assert flow['planned_spend'] == 4
    assert flow['items'][0]['target'] == 'level_up'


# ===== C5:ok 分支 debug 行附疑截断行名 =====


def test_faction_ok_line_appends_suspect_names() -> None:
    """疑截断行名非空 → 行内附带行名(mismatch=0 稳定态可溯源)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        faction_display_ok_debug_line,
    )
    line = faction_display_ok_debug_line(
        7, 1, ['持续伤害', '仙舟', '狼狩', '银河学者'], 0)
    assert 'trunc_suspect=4' in line
    assert '(持续伤害,仙舟,狼狩,银河学者)' in line


def test_faction_ok_line_empty_suspects_keeps_legacy_shape() -> None:
    """空疑截断列表 → 不附括号段(旧行形,判读 grep 兼容)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        faction_display_ok_debug_line,
    )
    line = faction_display_ok_debug_line(6, 0, [], 0)
    assert 'trunc_suspect=0 computed_missing=0' in line
    assert 'trunc_suspect=0(' not in line
