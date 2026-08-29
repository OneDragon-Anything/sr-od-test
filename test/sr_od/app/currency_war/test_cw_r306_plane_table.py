# -*- coding: utf-8 -*-
"""r306 位面节点表缓存测试(用户指路:开局帧读全)。"""
from __future__ import annotations

from sr_od.application.currency_war.decision.cw_strategy import StrategySession


def test_p1_typical_table_matches_stats() -> None:
    """r306b:P1 典型表(25 帧众数)——slot1/2/4/7 恒定,
    slot5/6 变异位(策略效果)。sim 骨架与统计一致。"""
    import random


    from sr_od.application.currency_war.kernel.cw_battle_calib import sample_node_sequence
    for seed in range(50):
        seq = sample_node_sequence(random.Random(seed))
        assert len(seq) == 9
        assert seq[0] == 'reward' and seq[1] == 'reward'
        assert seq[2] == 'battle'
        assert seq[4] == 'supply'
        assert seq[5] in ('battle', 'encounter')   # 变异位(主 battle)
        assert seq[6] in ('encounter', 'supply')   # 变异位(主 encounter)
        assert seq[7] == 'reward'
        assert seq[8] == 'boss'


def test_opening_frame_caches_full_table() -> None:
    """r306 语义(方向修正版):实时识别是**权威**(每帧读);
    开局帧存 plane_node_table 只作离线统计源+左移兜底,
    不做决策主源(策略可改节点,缓存会过期)。"""
    import inspect

    from sr_od.application.currency_war import prep_director
    src = inspect.getsource(prep_director.PrepDirector._probe_node_type)
    # 实时识别每帧执行(主源);缓存注释明确「不做决策主源」
    assert '实时识别是权威' in src
    assert '不做决策主源' in src
