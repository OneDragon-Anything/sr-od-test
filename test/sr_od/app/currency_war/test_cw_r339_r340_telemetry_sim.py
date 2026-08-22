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
    """r340:板深条件化池 + live_delta_for 回退链(⓪ 后显式池注入)。

    ⓪(sim 判读同构基建)起 pool_map 显式注入——「离线无 replay
    返回 None」的隐式两态语义已废除(缺源 auto 现 raise,
    DeltaPoolUnavailable),本锁改构造池双向锁:命中桶采样 +
    无更浅桶 → None(调用方走旧模型)。
    """
    import random

    from sr_od.application.currency_war import cw_sim
    src = inspect.getsource(cw_sim.live_delta_for)
    assert '浅侧' in src and 'bucket - _DEPTH_BUCKET_W' in src   # 邻桶回退只向浅侧(真锁:实现语句在)
    pool = {'battle': {6: [-3, -5]}}
    v = cw_sim.live_delta_for('battle', 7, random.Random(1),
                              pool_map=pool)
    assert v in (-3, -5)     # 深7 → 桶6 命中
    # 深0 → 桶0 缺,浅侧回退桶-3 也缺 → None(r343 E 修:只向浅侧)
    assert cw_sim.live_delta_for('battle', 0, random.Random(1),
                                 pool_map=pool) is None
    # 节点缺 → None
    assert cw_sim.live_delta_for('boss', 6, random.Random(1),
                                 pool_map=pool) is None


def test_sim_events_reach_node_delta() -> None:
    """r340:sim 结算走板深池优先(hp_events 记真值)。"""
    from sr_od.application.currency_war import cw_sim
    src = inspect.getsource(cw_sim.simulate_p1)
    assert 'live_delta_for' in src
