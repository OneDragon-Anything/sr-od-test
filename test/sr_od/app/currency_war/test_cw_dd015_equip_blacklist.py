# -*- coding: utf-8 -*-
"""dd-015/dd-016 执行层修复批行为测试(复盘 g_20260902_181254 修复项 A/E)。

- A(装备拖拽失败降级,dd-015):失败登记 ≥2 次拉黑该(件→角色)对、
  拉黑对从分配序列剔除、失败 1 次保留重试——纯函数桩,离线可测;
  session 级记忆字段存在(跨轮存活的载体)。
- E(cap 空槽补部署,dd-016):``residual_fill_plan`` 对留置散牌生成
  补部署计划;同名禁双跳过、cap 动态停、选排 fallback、两排皆满停。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_strategy_session import StrategySession
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


def test_fail_continue_behavior_simulated():
    """「失败继续」行为桩:复刻 M7 主循环的失败分叉语义——

    单件失败 → 登记并继续下一件(不中止整批);该件重试再败 → 拉黑,
    后续轮次 alloc 不再含它,其余件照常消费。修复前语义(break 中止)
    之下,第二件永远轮不到——本锁钉住修复后的推进面。
    """
    counts: dict = {}
    alloc_pool = [('三月七', '星徽'), ('卡芙卡', '小刀'), ('艾丝妲', '轮滑鞋')]
    worn: list[str] = []
    # 轮 1:星徽拖败(第 1 次,登记,继续)
    alloc = filter_alloc_blacklisted(list(alloc_pool), counts)
    assert alloc[0] == ('三月七', '星徽')
    assert not register_equip_drag_failure(counts, equip_drag_key('星徽', '三月七'))
    # 轮 2:星徽重试再败(第 2 次)→ 拉黑;队首让位,小刀穿上
    alloc = filter_alloc_blacklisted(list(alloc_pool), counts)
    assert alloc[0] == ('三月七', '星徽'), '失败 1 次仍保留重试'
    assert register_equip_drag_failure(counts, equip_drag_key('星徽', '三月七'))
    alloc = filter_alloc_blacklisted(list(alloc_pool), counts)
    assert alloc[0] == ('卡芙卡', '小刀'), '拉黑后失败继续(修复前此处 break 整批中止)'
    worn.append('小刀')
    # 轮 3+:星徽不再出现(拉黑跨轮存活——counts 即 session 载体)
    alloc = filter_alloc_blacklisted(list(alloc_pool), counts)
    assert all(name != '星徽' for _, name in alloc)


def test_session_carries_fail_counts_field():
    """session 级记忆载体存在且默认空(跨轮存活的登记处;局级新建销毁)。"""
    s = StrategySession()
    assert s.equip_drag_fail_counts == {}


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
    """选排:pref=front 优先前排;首选排满 fallback 另一排;两排皆满停。"""
    plan = residual_fill_plan(
        held=[2, 5, 7],
        front_empty=[],            # 前排满 → front 件 fallback 后排
        back_empty=[3, 4],
        bench_pos={2: 'front', 5: 'back', 7: 'back'},
        bench_cid={2: '真理医生', 5: '黑塔', 7: '缇宝'},
        deployed_cids=set(), cap=10, deployed_count=0)
    assert (2, 'back', 3) in plan, 'front 件前排满 → fallback 后排'
    assert (5, 'back', 4) in plan
    assert (7, 'back', 4) not in plan or plan[-1][2] != plan[-2][2], '空槽不重复分配'
    # 两排皆满 → 空计划
    assert residual_fill_plan(
        held=[2], front_empty=[], back_empty=[],
        bench_pos={2: 'back'}, bench_cid={2: '缇宝'},
        deployed_cids=set(), cap=10, deployed_count=0) == []


def test_fill_plan_no_double_slot_assignment():
    """同排多件依次消费不同空槽(计划内互不撞槽)。"""
    plan = residual_fill_plan(
        held=[2, 5, 7], front_empty=[], back_empty=[3, 4],
        bench_pos={2: 'back', 5: 'back', 7: 'back'},
        bench_cid={2: '缇宝', 5: '黑塔', 7: '银枝'},
        deployed_cids=set(), cap=10, deployed_count=0)
    slots = [s for _, _, s in plan]
    assert len(slots) == len(set(slots)) == 2
