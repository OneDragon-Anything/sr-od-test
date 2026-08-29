# -*- coding: utf-8 -*-
"""r339/r340 遥测+模拟优化锁。"""
from __future__ import annotations

import inspect


def test_outcome_board_fields() -> None:
    """r339:OutcomeRecord 板深快照字段(板深模型校准源)。"""

    from sr_od.application.currency_war.telemetry.schema import OutcomeRecord
    rec = OutcomeRecord()
    assert rec.board_before == {}
    assert rec.bench_count == 0


def test_query_hp_view_exists() -> None:
    """r339:hp 视图(掉血分解,sim hp_events 同构)。"""
    from sr_od.application.currency_war.telemetry import query as _q
    assert hasattr(_q, 'query_hp')
    assert hasattr(_q, 'query_economy')


def test_set_ctx_match_ref_slot() -> None:
    """r339:set_ctx_match 弱引用注册。"""
    from sr_od.application.currency_war.telemetry import state as _s
    assert hasattr(_s, 'set_ctx_match')
    assert hasattr(_s, '_CTX_MATCH_REF')


def test_live_delta_depth_conditioned() -> None:
    """r340:板深条件化池 + live_delta_for 回退链(⓪ 后显式池注入)。

    ⓪(sim 判读同构基建)起 pool_map 显式注入——「离线无 replay
    返回 None」的隐式两态语义已废除(缺源 auto 现 raise,
    DeltaPoolUnavailable),本锁改构造池双向锁:命中桶采样 +
    无更浅桶 → None(调用方走旧模型)。
    (ADR-0279:battle 桶键=rung;depth 路径锁用 boss/encounter
    承载,battle 全 rung 不可达走全池兜底。)
    """
    import random

    from sr_od.application.currency_war.sim import engine_p1 as cw_sim
    from sr_od.application.currency_war.sim import pool as sim_pool
    src = inspect.getsource(sim_pool.live_delta_for)
    assert '浅侧' in src and 'bucket - DEPTH_BUCKET_W' in src   # 邻桶回退只向浅侧(真锁:实现语句在)
    # ADR-0362:合成池带 plane 层
    pool = {'battle': {1: {6: [-3, -5]}}}
    v = sim_pool.live_delta_for('battle', 7, random.Random(1),
                              pool_map=pool)
    assert v in (-3, -5)     # rung 桶不可达 → 全池兜底命中样本
    # boss 桶缺 → None(r343 E 修:只向浅侧;节点缺 → None)
    assert sim_pool.live_delta_for('boss', 6, random.Random(1),
                                 pool_map=pool) is None


def test_sim_events_reach_node_delta() -> None:
    """r340:sim 结算走板深池优先(hp_events 记真值)。"""
    from sr_od.application.currency_war.sim import engine_p1 as cw_sim

    src = inspect.getsource(cw_sim.simulate_p1)
    assert 'live_delta_for' in src

