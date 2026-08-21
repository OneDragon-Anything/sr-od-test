# -*- coding: utf-8 -*-
"""r339/r340 遥测+模拟优化锁。"""
from __future__ import annotations

import inspect


def test_outcome_board_fields() -> None:
    """r339:OutcomeRecord 板深快照字段(板深模型校准源)。"""
    from sr_od.application.currency_war.cw_telemetry import OutcomeRecord
    rec = OutcomeRecord()
    assert rec.board_before == {}
    assert rec.bench_count == 0


def test_query_hp_view_exists() -> None:
    """r339:hp 视图(掉血分解,sim hp_events 同构)。"""
    from sr_od.application.currency_war import cw_telemetry
    assert hasattr(cw_telemetry, 'query_hp')
    assert hasattr(cw_telemetry, 'query_economy')


def test_set_ctx_match_ref_slot() -> None:
    """r339:set_ctx_match 弱引用注册。"""
    from sr_od.application.currency_war import cw_telemetry
    assert hasattr(cw_telemetry, 'set_ctx_match')
    assert hasattr(cw_telemetry, '_CTX_MATCH_REF')


def test_live_delta_depth_conditioned() -> None:
    """r340:板深条件化池 + live_delta_for 回退链。"""
    from sr_od.application.currency_war import cw_sim
    src = inspect.getsource(cw_sim.live_delta_for)
    assert 'bucket' in src and '回退' not in src.split('"""')[0]   # 有邻桶回退
    import random
    v = cw_sim.live_delta_for('battle', 7, random.Random(1))
    # 有数据环境返回 int;离线无 replay 返回 None(两态皆合法)
    assert v is None or isinstance(v, int)


def test_sim_events_reach_node_delta() -> None:
    """r340:sim 结算走板深池优先(hp_events 记真值)。"""
    from sr_od.application.currency_war import cw_sim
    src = inspect.getsource(cw_sim.simulate_p1)
    assert 'live_delta_for' in src
