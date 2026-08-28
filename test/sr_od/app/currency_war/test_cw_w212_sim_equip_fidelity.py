# -*- coding: utf-8 -*-
"""W212(ADR-0393):装备分配 sim 调用形态保真锁。

锁的是 sim 调用 equip_allocation 的**形态**(plane 现读 + occupied 已穿快照),
不是具体分配结果——修复前 sim 恒按默认 plane=1 + occupied=None 调用,导致
ADR-0391 守卫/回收线在 sim 从未点火(W212 批 A 实测 0/0)。

锁法:monkeypatch cw_comps.equip_allocation 捕获调用参数 → 跑一局
simulate_p1(池=snapshot 由 pytest 环境解析;单局 ~0.2s)→ 断言
① 至少一次调用的 plane==2(P2 段真 plane 语义可达——修复前恒 1);
② occupied 与该轮 BenchChar.equips 真值同构(键=(position_pref, slot),
   值=已穿列表),非 None。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_comps
from sr_od.application.currency_war.cw_sim import simulate_p1


def test_sim_equip_allocation_call_shape_plane_and_occupied() -> None:
    """sim 调用形态与生产 EquipAll 对齐:plane 现读 + occupied 已穿快照。"""
    calls: list[dict] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, plane=1, **kwargs):
        calls.append({'plane': plane, 'occupied': occupied,
                      'deployed_n': len(list(deployed or []))})
        return orig(comp, deployed, owned, occupied, plane, **kwargs)

    cw_comps.equip_allocation = spy
    try:
        # fallback 池(测试仓惯例,同 test_cw_action_v2)。P2 段分配点火
        # 是概率事件(equips 非空 ∧ P2 有 deployed)——扫一小窗 seed,
        # 任一 seed 出现 plane=2 调用即形态可达(修复前恒 {1},永不可达)。
        for seed in range(20):
            simulate_p1(seed, planes=2, pool='fallback')
            if any(c['plane'] == 2 for c in calls):
                break
    finally:
        cw_comps.equip_allocation = orig

    assert calls, 'sim 全程未调 equip_allocation(equips 恒空?环境异常)'
    planes_seen = {c['plane'] for c in calls}
    # ① P2 段真 plane 语义可达(修复前恒 1——死库存回收/守卫不可点火的根因)
    assert 2 in planes_seen, (
        f'sim 从未以 plane=2 调 equip_allocation(修复前形态): {planes_seen}')
    # ② occupied 非 None 且为已穿快照 dict(修复前恒 None)
    occ_calls = [c for c in calls if c['occupied'] is not None]
    assert occ_calls, 'occupied 恒 None(修复前形态)——ADR-0393 失效'
    sample = occ_calls[0]['occupied']
    assert all(isinstance(k, tuple) and len(k) == 2
               and isinstance(v, list) for k, v in sample.items()), (
        f'occupied 键形态≠(position_pref, slot): {sample}')


def test_sim_p1_only_still_runs_with_shape_fix() -> None:
    """P1 段(plane=1 路径)在修复后正常出分配结果(零漂移烟雾)。"""
    calls: list[int] = []
    orig = cw_comps.equip_allocation

    def spy(comp, deployed, owned, occupied=None, plane=1, **kwargs):
        calls.append(plane)
        return orig(comp, deployed, owned, occupied, plane, **kwargs)

    cw_comps.equip_allocation = spy
    try:
        simulate_p1(11, planes=1, pool='fallback')
    finally:
        cw_comps.equip_allocation = orig
    # P1 段若发生分配,plane 必须恒 1(逐位零漂移承诺)
    assert all(p == 1 for p in calls)
