# -*- coding: utf-8 -*-
"""dd-015/dd-016 执行层修复批行为测试(复盘 g_20260902_181254 修复项 A/E)。

- A(装备拖拽失败降级,dd-015):失败登记 ≥2 次拉黑该(件→角色)对、
  拉黑对从分配序列剔除、失败 1 次保留重试——纯函数桩,离线可测;
  session 级记忆字段存在(跨轮存活的载体)。
- E(cap 空槽补部署,dd-016):``residual_fill_plan`` 对留置散牌生成
  补部署计划;同名禁双跳过、cap 动态停、选排 fallback、两排皆满停。
"""

# ⚠️ 待归并标记(2026-09-12 data 域解体批;台账 = .debug/temp/cw_obs_rebuild/DEBT.md):
# 本文件主体 = cw_op_equip_all 的策略执行行为(拉黑登记/补部署计划),
# 非 data 表——待装备策略主题归并,禁按 data 域处置。
from __future__ import annotations

from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
    DRAG_FAIL_BLACKLIST_LIMIT,
    equip_drag_key,
    filter_alloc_blacklisted,
    register_equip_drag_failure,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    residual_fill_plan,
)


# ==================== dd-015:A 失败拉黑 + 跳过继续 ====================


def test_register_blacklists_after_limit():
    """同一(件→角色)对连败达限(2 次)→ 拉黑;未达限不拉黑。"""
    counts: dict = {}
    key = equip_drag_key('列车同行星徽', '三月七')
    assert not register_equip_drag_failure(counts, key)
    assert register_equip_drag_failure(counts, key)   # 第 2 次失败即达线拉黑
    assert register_equip_drag_failure(counts, key)   # 已达线,恒 True(幂等拉黑)
    assert DRAG_FAIL_BLACKLIST_LIMIT == 2
    assert counts[key] == 3


def test_register_keys_are_pair_scoped():
    """拉黑粒度 = 件×角色对:同件换角色 / 同角色换件 互不影响。"""
    counts: dict = {}
    register_equip_drag_failure(counts, equip_drag_key('甲', '三月七'))
    register_equip_drag_failure(counts, equip_drag_key('甲', '三月七'))
    assert register_equip_drag_failure(counts, equip_drag_key('甲', '三月七'))
    assert equip_drag_key('甲', '艾丝妲') not in counts
    assert equip_drag_key('乙', '三月七') not in counts


def test_filter_alloc_drops_blacklisted_keeps_once_failed():
    """分配序列剔除已拉黑对;失败 1 次(未拉黑)的保留(补救链重试一次)。"""
    counts: dict = {}
    register_equip_drag_failure(counts, equip_drag_key('星徽', '三月七'))
    register_equip_drag_failure(counts, equip_drag_key('星徽', '三月七'))   # 已拉黑
    register_equip_drag_failure(counts, equip_drag_key('小刀', '卡芙卡'))   # 仅 1 次,未拉黑
    alloc = [('三月七', '星徽'), ('卡芙卡', '小刀'), ('艾丝妲', '轮滑鞋')]
    out = filter_alloc_blacklisted(alloc, counts)
    assert ('三月七', '星徽') not in out, '已拉黑对应剔除'
    assert ('卡芙卡', '小刀') in out, '失败 1 次保留(≥2 才拉黑)'
    assert ('艾丝妲', '轮滑鞋') in out


# ==================== dd-016:E 残余补部署计划 ====================


def test_fill_plan_deploys_into_vacancy():
    """空槽 + 留置散牌 → 生成补部署计划(P24 支配:空槽不上人修复)。"""
    plan = residual_fill_plan(
        held=[2, 5],
        front_empty=[],            # 前排满
        back_empty=[3],            # 后排 1 空槽(0-based 下标)
        bench_pos={2: 'back', 5: 'back'},
        bench_cid={2: '缇宝', 5: '黑塔'},
        deployed_cids={'艾丝妲', '饮月', '三月七'},
        cap=4, deployed_count=3)
    assert plan == [(2, 'back', 3)], '散牌补进唯一空槽'


def test_fill_plan_skips_same_name_dup():
    """同名禁双(5.1.7):留置件与场上同名 → 跳过(dup 是 3合1 素材,
    游戏拒收,局14 藿藿实证),不产生拖必败计划。"""
    plan = residual_fill_plan(
        held=[2], front_empty=[], back_empty=[3],
        bench_pos={2: 'back'}, bench_cid={2: '艾丝妲'},
        deployed_cids={'艾丝妲'}, cap=4, deployed_count=3)
    assert plan == []


def test_fill_plan_respects_dynamic_cap():
    """cap 动态门:deployed_count 已达 cap → 不再补(cap 现读语义,
    别信固定槽位数);计划中途达 cap → 停。"""
    assert residual_fill_plan(
        held=[2], front_empty=[], back_empty=[3],
        bench_pos={2: 'back'}, bench_cid={2: '缇宝'},
        deployed_cids=set(), cap=4, deployed_count=4) == []
    plan = residual_fill_plan(
        held=[2, 5], front_empty=[], back_empty=[3, 4],
        bench_pos={2: 'back', 5: 'back'}, bench_cid={2: '缇宝', 5: '黑塔'},
        deployed_cids=set(), cap=5, deployed_count=3)
    assert len(plan) == 2   # 3→4→5,恰满即停


def test_fill_plan_row_pref_with_fallback():
    """选排:pref=front 且前排有空 → 直接上前排;首选排满 fallback 另一排;
    计划中途排尽停(第 3 件不再产计划);两排皆满空计划。计划全值精确断言
    (空槽恰消费一次不重复——原 no_double_slot 单测断言面被本断言吸收)。"""
    plan = residual_fill_plan(
        held=[2, 5, 7],
        front_empty=[],            # 前排满 → front 件 fallback 后排
        back_empty=[3, 4],
        bench_pos={2: 'front', 5: 'back', 7: 'back'},
        bench_cid={2: '真理医生', 5: '黑塔', 7: '缇宝'},
        deployed_cids=set(), cap=10, deployed_count=0)
    assert plan == [(2, 'back', 3), (5, 'back', 4)]
    # pref=front 且前排有空 → 直接前排,不 fallback
    assert residual_fill_plan(
        held=[2], front_empty=[1], back_empty=[4],
        bench_pos={2: 'front'}, bench_cid={2: '真理医生'},
        deployed_cids=set(), cap=10, deployed_count=0) == [(2, 'front', 1)]
    # 两排皆满 → 空计划
    assert residual_fill_plan(
        held=[2], front_empty=[], back_empty=[],
        bench_pos={2: 'back'}, bench_cid={2: '缇宝'},
        deployed_cids=set(), cap=10, deployed_count=0) == []
