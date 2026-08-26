# -*- coding: utf-8 -*-
"""W211(ADR-0391):装备策略接入——P14 期望模型的生产化锁。

三面:
1. 图谱纯函数对拍 P14 已发表表(例 1 阿雅/例 2 飞霄;数值改动=图谱变更,
   锁住与证明文档的一致性,防双源漂移);
2. equip_allocation 防误合成配对守卫(口述「穿着触发会被残留件带偏」):
   同角色互为配对的两基础件 → 拒;想要的配对(产物∈key_equips 且 core)
   → 放行;回收合格死库存对在非 core → 放行(回收线有意 2合1);
3. 死库存回收去向(P2/P3):回收合格件优先发非 core 工具人(≤2 件/人),
   不穿 core;发不完留 owned(囤积口述)。

P14 = docs/game/currency_war/research/proofs/p14-equipment-acquisition-ev.md
(定理 1 决策表输入 / 定理 3 回收准入 / 检验点 2 判读锚点)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import (
    equip_allocation,
)
from sr_od.application.currency_war.cw_state import BenchChar
from sr_od.application.currency_war.cw_synthesis import (
    RESERVED_COMPONENTS,
    component_demand,
    hoard_gaps,
    recycle_qualified,
    synthesize_target,
)

# 例 1 阿雅 K(cw_comps 映夜神阿雅 key_equips 摘录;白昼件无配方跳过)
_K_AYA = ['反重力皮靴', '反重力皮靴', '白昼·光速螺旋桨', '火力风暴潮']
# 例 2 追击飞霄 K
_K_FEI = ['火力风暴潮', '火力风暴潮', '永动机', '电磁弹射器']


# ===== 1. 图谱纯函数对拍 P14 已发表表 =====

def test_component_demand_p14_examples() -> None:
    """K → 组件需求向量,逐位对拍 P14 例 1/例 2(含自配×2 与无配方件跳过)。"""
    assert component_demand(_K_AYA) == {'轮滑鞋': 5, '折叠小刀': 1}
    assert component_demand(_K_FEI) == {
        '折叠小刀': 2, '轮滑鞋': 3, '光能电池': 2, '和平手枪': 1}


def test_recycle_qualified_p14_examples() -> None:
    """回收合格集对拍 P14 Q3 表:阿雅 6 件(轮滑鞋除外);飞霄 4 件。"""
    assert recycle_qualified(_K_AYA) == frozenset({
        '以太钻头', '光能电池', '和平手枪', '幸运星', '生命之花', '量产型装甲'})
    assert recycle_qualified(_K_FEI) == frozenset({
        '以太钻头', '幸运星', '生命之花', '量产型装甲'})


def test_recycle_qualified_no_target_empty() -> None:
    """comp=None(无目标)→ 空集:有用性无从判定,一律不当死库存(保守侧)。"""
    assert recycle_qualified(None) == frozenset()
    assert recycle_qualified([]) == frozenset()


def test_hoard_gaps_offset_by_finished_advance() -> None:
    """「缺什么囤什么」差集:成品 1:1 抵扣 K 需求后才展开组件账。

    阿雅 K 已持 1 皮靴 → 剩 皮靴×1(=轮滑鞋2)+风暴潮(=轮滑鞋+小刀)
    → 缺 轮滑鞋3/折叠小刀1;再持轮滑鞋2 → 缺 轮滑鞋1/小刀1。"""
    assert hoard_gaps(_K_AYA, ['反重力皮靴']) == {'轮滑鞋': 3, '折叠小刀': 1}
    assert hoard_gaps(_K_AYA, ['反重力皮靴', '轮滑鞋', '轮滑鞋']) == {
        '轮滑鞋': 1, '折叠小刀': 1}
    assert hoard_gaps(_K_AYA, _K_AYA) == {}, '成品全持 → 零缺口'


# ===== 2. 防误合成配对守卫(equip_allocation)=====

def _mkcomp(key_equips: list[str], cores: list[str]):
    from sr_od.application.currency_war.cw_comps import Comp
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def test_pairing_guard_rejects_unintended_synthesis() -> None:
    """P2:core 已穿 生命之花,新发 光能电池 → 会自动合成「绝对热量」
    (run 26 实锤配方);产物不在该 comp key_equips → 该件不发 core(留 owned)。
    防的是不可逆消耗:穿着触发自动合成无确认,口述「会被残留件带偏」。"""
    assert synthesize_target('光能电池', '生命之花') == '绝对热量', \
        '图谱前提:run 26 实锤配方必须在(否则本锁失锚)'
    comp = _mkcomp(['火力风暴潮'], ['飞霄'])   # 绝对热量 ∉ key_equips
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    alloc = equip_allocation(comp, dep, ['光能电池'], occ, plane=2)
    assert ('飞霄', '光能电池') not in alloc, \
        f'非预期合成对被发到同一 core: {alloc}'


def test_pairing_guard_allows_wanted_synthesis() -> None:
    """同上场景但 绝对热量 ∈ key_equips 且穿者是 core → 放行:
    想要的配对穿着触发合成 = 快路径(合成+穿一次完成)。"""
    comp = _mkcomp(['绝对热量'], ['飞霄'])
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    occ = {('front', 1): ['生命之花']}
    alloc = equip_allocation(comp, dep, ['光能电池'], occ, plane=2)
    assert ('飞霄', '光能电池') in alloc, \
        f'想要的配对应放行(core 快路径): {alloc}'


def test_pairing_guard_no_target_splits_pair() -> None:
    """comp=None:无豁免信息 → 互为配方的基础件对不同人发,不同人同穿。"""
    dep = [BenchChar(slot=1, char_id='三月七', position_pref='front'),
           BenchChar(slot=2, char_id='黑塔', position_pref='front')]
    owned = ['光能电池', '生命之花']      # 互为配方(绝对热量)
    alloc = equip_allocation(None, dep, owned, plane=2)
    holders = [c for c, e in alloc if e in owned]
    assert len(holders) == len(set(holders)), \
        f'配对件必须分人: {alloc}'


def test_pairing_guard_covers_guangneng_base() -> None:
    """守卫覆盖第 8 基础件光能电池(RESERVED_COMPONENTS 恰为全 8 件;
    只查 7 件标准集会漏光能电池系全部配方)。"""
    assert '光能电池' in RESERVED_COMPONENTS
    assert len(RESERVED_COMPONENTS) == 8


# ===== 3. 死库存回收去向(P2/P3 兜底)=====

def test_dead_stock_routed_to_noncore() -> None:
    """P2:回收合格件(对阿雅=以太钻头/幸运星 等)优先发非 core 工具人,
    core 不吃死库存(穿着合成产物落 core=后续转移摩擦)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['以太钻头', '幸运星'], plane=2)
    wearers = {e: c for c, e in alloc}
    assert wearers.get('以太钻头') == '三月七' \
        and wearers.get('幸运星') == '三月七', \
        f'死库存应全去非 core 工具人: {alloc}'
    assert all(c != '阿雅' for c, _ in alloc), f'core 不得吃死库存: {alloc}'


def test_dead_stock_allows_recycle_pair_on_tool_char() -> None:
    """回收线有意 2合1:非 core 工具人身上两件回收合格件互为配方 → 放行
    (口述「先 2 合 1,到一个没用的角色身上」;合成产物必然 ∉ K——若 ∈ K
    则其组件就不是死库存,P14 定理 3 反证)。"""
    rq = recycle_qualified(_K_AYA)
    # 从图谱里找一对真实互为配方的回收合格基础件(锁语义不锁具体对)
    pair = next(((a, b) for a in sorted(rq) for b in sorted(rq)
                 if a != b and synthesize_target(a, b) is not None), None)
    assert pair is not None, '图谱前提:死库存内存在可配对(回收线可触发)'
    a, b = pair
    assert synthesize_target(a, b) not in set(_K_AYA), '定理 3 反证前提'
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, [a, b], plane=2)
    got = [(c, e) for c, e in alloc if e in (a, b)]
    assert {c for c, _ in got} == {'三月七'} and len(got) == 2, \
        f'回收对应允许同穿非 core 工具人: {alloc}'


def test_p1_unchanged_by_policy() -> None:
    """P1 回归:基础件全保留(ADR-0265 不受本批影响),只有非基础件分配。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    dep = [BenchChar(slot=1, char_id='阿雅', position_pref='back'),
           BenchChar(slot=2, char_id='三月七', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['以太钻头', '火力风暴潮'], plane=1)
    worn = {e for _, e in alloc}
    assert worn == {'火力风暴潮'}, f'P1 基础件(含死库存)不入穿戴池: {alloc}'
