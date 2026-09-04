# -*- coding: utf-8 -*-
"""test_cw_r339_r340_telemetry_sim 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



import inspect as _r339_r340_telemetry_sim_inspect


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

    from sr_od.application.currency_war.sim import pool as sim_pool
    # 邻桶回退的形状断言('浅侧'/'bucket - DEPTH_BUCKET_W' 语句字面)已按
    # 源码锁瘦身删除;回退行为由下方行为断言守住(ADR-0362:合成池带 plane 层)。
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

    src = _r339_r340_telemetry_sim_inspect.getsource(cw_sim.simulate_p1)
    assert 'live_delta_for' in src
