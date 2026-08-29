# -*- coding: utf-8 -*-
"""W626(W625 设计 R1/R3):定向合成调度 + 守卫语义切换 + sim seam 零漂移锚。

设计单一源:`.debug/temp/currency_war/w625_wear_scheduling/DESIGN.md`
(已裁决放行;根源:8 基础件全配方闭包 × 守卫「禁配对」语义 = 滞留的
结构性必然,W625 消融 guard_off 臂实证守卫解释 ~100% sim 滞留)。

锁面:
1. plan_directed_syntheses 三优先级序(①key 产物→②通用进阶补板面空缺
   →③回收线),①的组件不被②③偷用;
2. 守卫语义切换:_pairing_guard_ok 的 directed_pairs 放行规划内配对,
   缺省 None = 旧两例外语义逐位保留;
3. seam 缺省零漂移:simulate_p1 不传 synth_gate 的 baseline 局与 W625
   冻结消融逐 seed 一致(全量对拍见 w626 零漂移脚本,此处锁缺省参数
   域:非法 gate raise);
4. 回收线生锈加权:recycle_line=False 时死库存不配对(囤积语义保留)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.cw_comps import (
    _pairing_guard_ok,
    equip_allocation,
)
from sr_od.application.currency_war.cw_synthesis import (
    ADVANCE_CATEGORIES,
    board_gap_category,
    directed_pairs_of,
    plan_directed_syntheses,
    recycle_qualified,
)

# 注册表常量(来自 cw_synthesis 派生;只锁语义成员,不锁全量清单——
# 全量清单由注册表版本驱动,换版本重拉自动跟上)
_轮滑鞋 = '轮滑鞋'
_小刀 = '折叠小刀'
_皮靴 = '反重力皮靴'
_装甲 = '量产型装甲'
_钻头 = '以太钻头'
_电池 = '光能电池'


# ===== 1. 三优先级序 =====

def test_priority1_key_products_first() -> None:
    """①key 产物先消费:key 需求的组件不被②通用进阶偷用。"""
    keys = [_皮靴]                       # 需求 轮滑鞋×2
    owned = [_轮滑鞋] * 3 + [_小刀]      # 3 鞋:①吃 2,剩 1 鞋+1 刀
    actions = plan_directed_syntheses(keys, owned, gap_category='输出')
    first = actions[0]
    assert first[0] == _皮靴
    assert set(first[1]) == {_轮滑鞋}
    # ①已消耗后,②只剩 1 鞋凑不出输出侧交叉对 → 不应有偷用皮靴组件的产物
    consumed = [c for _, comps in actions for c in comps]
    assert consumed.count(_轮滑鞋) == 3   # 全部鞋都有去向(①2 + ②若可行)
    assert (_皮靴, 2) not in [(a, comps.count(_轮滑鞋))
                              for a, comps in actions[1:]]


def test_priority2_generic_advance_matches_gap_category() -> None:
    """②非 key 组件定向成缺位类别的通用进阶;类别不符不配。"""
    owned = [_装甲, _装甲]               # 量产型装甲×2 → 很硬的甲(生存类)
    surv = plan_directed_syntheses([], owned, gap_category='生存')
    assert surv and surv[0][0] == '很硬的甲'
    # 输出缺口时:很硬的甲纯生存,不属输出类 → 不配(囤着)
    assert plan_directed_syntheses([], owned, gap_category='输出') == []
    # gap_category=None(未给板面信息)→ ②整体关闭,同囤着
    assert plan_directed_syntheses([], owned) == []


def test_priority3_recycle_line_gated_by_rust_flag() -> None:
    """③回收线配对仅在 recycle_line=True(R3:生锈在场)时触发。"""
    keys = [_皮靴]
    assert _钻头 in recycle_qualified(keys) and _电池 in recycle_qualified(keys)
    owned = [_钻头, _电池]
    # 无生锈代理 → 死库存维持囤积(ADR-0391 语义,不提前合成)
    assert plan_directed_syntheses(keys, owned, recycle_line=False) == []
    # 生锈在场 → 立即配对成进阶(冶金炉等刷的无用进阶)
    acts = plan_directed_syntheses(keys, owned, recycle_line=True)
    assert acts and set(acts[0][1]) == {_钻头, _电池}


def test_advance_categories_registry_derived() -> None:
    """类别标定进注册表派生:很硬的甲=生存-only(伤害减免),皮靴不属进阶。"""
    assert ADVANCE_CATEGORIES['很硬的甲'] == frozenset({'生存'})
    assert '输出' in ADVANCE_CATEGORIES[_皮靴]   # 皮靴=轮滑鞋×2 的自配进阶
    assert _轮滑鞋 not in ADVANCE_CATEGORIES    # 基础件不进类别表


def test_board_gap_category_counts() -> None:
    """缺位类别 = 生存/输出计数取少侧;相等取输出(空板/均衡板)。"""
    assert board_gap_category(['输出', '输出', '治疗']) == '生存'
    assert board_gap_category(['输出', '治疗', '护盾']) == '输出'
    assert board_gap_category(['输出']) == '生存'      # 全输出板缺生存位
    assert board_gap_category([]) == '输出'            # 计数相等 → 输出


# ===== 2. 守卫语义切换 =====

def test_guard_directed_pairs_endorsement() -> None:
    """规划内配对放行(directed_pairs),无主配对仍拦;缺省 None=旧语义。"""
    worn = {'阿雅': [_轮滑鞋]}
    key_set: set[str] = set()
    core_set: set[str] = set()
    rq: set[str] = set()
    # 无主配对:鞋+刀(产物火力风暴潮非 key)→ 拦
    assert not _pairing_guard_ok(worn, '阿雅', _小刀, key_set, core_set, rq)
    # 同配对进了定向规划 → 放行(R1 快路径)
    pairs = {frozenset({_轮滑鞋, _小刀})}
    assert _pairing_guard_ok(worn, '阿雅', _小刀, key_set, core_set, rq, pairs)
    # 缺省 None:两例外旧语义逐位(非 key 非回收 → 拦)
    assert not _pairing_guard_ok(worn, '阿雅', _小刀, key_set, core_set, rq)


def test_equip_allocation_default_zero_drift() -> None:
    """equip_allocation 不传 directed_pairs → 行为与旧签名逐位一致。"""
    deployed = [type('D', (), {'char_id': '阿雅', 'position_pref': 'front',
                               'slot': 0, 'equips': []})()]
    owned = [_小刀, _轮滑鞋, '冶金炉']
    a = equip_allocation(None, deployed, owned)
    b = equip_allocation(None, deployed, owned, directed_pairs=None)
    assert a == b


# ===== 3. seam 缺省零漂移 =====

def test_sim_synth_gate_validation() -> None:
    """非法 synth_gate 显式 raise;合法值域 locked/always/locked_directed。"""
    from sr_od.application.currency_war import cw_sim
    with pytest.raises(ValueError):
        cw_sim.simulate_p1(0, pool='fallback', synthesis_chain=True,
                           synth_gate='bogus')
    # 缺省不点火合成链(synthesis_chain=False)→ gate 值不参与任何分支
    r = cw_sim.simulate_p1(0, pool='fallback')
    assert r.p1_synth_locked_products == []
    assert r.p1_synth_open_products == []
