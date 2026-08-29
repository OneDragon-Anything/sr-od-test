# -*- coding: utf-8 -*-
"""W212(ADR-0393):装备分配 sim 调用形态保真锁。

锁的是 sim 调用 equip_allocation 的**形态**(occupied 已穿快照),
不是具体分配结果——修复前 sim 恒 occupied=None 调用,导致 ADR-0391
守卫/回收线在 sim 从未点火(W212 批 A 实测 0/0)。

原「plane 现读」断言已随 ADR-0265 增补(穿戴可逆,P1 组件保留过滤
删除)过期:equip_allocation 不再有 plane 分支,参数随之删除——
该断言锁的是已不存在的分支语义,非当前设计意图(锁的存在性纪律:
改锁=重推语义,非机械跟绿)。

锁法:monkeypatch cw_comps.equip_allocation 捕获调用参数 → 跑一局
simulate_p1(池=fallback 测试惯例;单局 ~0.2s)→ 断言 occupied
与该轮 BenchChar.equips 真值同构(键=(position_pref, slot),
值=已穿列表),非 None。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_comps
from sr_od.application.currency_war.cw_sim import simulate_p1


def test_sim_equip_allocation_call_shape_occupied_snapshot() -> None:
    """sim 调用形态与生产 EquipAll 对齐:occupied = 已穿快照 dict。"""
    calls: list[dict] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, directed_pairs=None):
        calls.append({'occupied': occupied,
                      'deployed_n': len(list(deployed or []))})
        return orig(comp, deployed, owned, occupied)

    cw_comps.equip_allocation = spy
    try:
        # fallback 池(测试仓惯例)。P2 段分配点火是概率事件(equips
        # 非空 ∧ 有 deployed)——扫一小窗 seed,任一 seed 出现带 occupied
        # 的调用即形态可达(修复前恒 None,永不可达)。
        for seed in range(20):
            simulate_p1(seed, planes=2, pool='fallback')
            if any(c['occupied'] is not None for c in calls):
                break
    finally:
        cw_comps.equip_allocation = orig

    assert calls, 'sim 全程未调 equip_allocation(equips 恒空?环境异常)'
    occ_calls = [c for c in calls if c['occupied'] is not None]
    assert occ_calls, 'occupied 恒 None(修复前形态)——ADR-0391 守卫失效'
    sample = occ_calls[0]['occupied']
    assert all(isinstance(k, tuple) and len(k) == 2
               and isinstance(v, list) for k, v in sample.items()), (
        f'occupied 键形态≠(position_pref, slot): {sample}')


def test_sim_p1_still_runs_and_allocates() -> None:
    """P1 段正常出分配调用(零漂移烟雾;分配发生即可,不锁分配内容)。"""
    calls: list[int] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, directed_pairs=None):
        calls.append(1)
        return orig(comp, deployed, owned, occupied)

    cw_comps.equip_allocation = spy
    try:
        for seed in range(10):
            simulate_p1(seed, planes=1, pool='fallback')
            if calls:
                break
    finally:
        cw_comps.equip_allocation = orig
    assert calls, 'P1 段全程未调 equip_allocation(分配链断裂?)'
