# -*- coding: utf-8 -*-
"""装备分配组件穿着语义(ADR-0265 增补:穿戴可逆,简易件默认穿)。

历史语义(P1 组件不入穿戴池)已过期:用户裁决「卖角色全额返还装备」
确立穿戴是可逆操作——过渡穿着既不锁死合成路线(组件可取回)也不构成
资源损耗,原保留过滤的存在理由消失,随 ADR-0265 增补删除(旧锁钉的是
已被取代的语义,按锁的存在性纪律重推改写,非机械跟绿)。

当前语义:
- P1 与 P2+ 同池分配,简易件默认穿(编排者裁决;期望收益由磨损标定仪
  测量,ADR-0391 设计件);
- ADR-0391 防误合成配对守卫全 plane 生效(真实不可逆依据:非预期合成
  不可逆消耗两件组件)——同角色两件互为配方的基础件,无豁免信息
  (comp=None)时拆开发/拦下;
- 原 check_no_component_equipped_p1 检查项随过滤一并退役
  (锁的是被取代的裁决)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_comps import (
    EQUIP_CAPACITY,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.data.cw_synthesis import RESERVED_COMPONENTS


def _dep():
    return [BenchChar(slot=1, char_id='飞霄', position_pref='front'),
            BenchChar(slot=2, char_id='三月七', position_pref='front')]


def test_components_wearable_p1_default() -> None:
    """P1:组件默认可穿(简易件默认穿);comp=None 危险配对拆开发。"""
    owned = ['光能电池', '轮滑鞋', '蓄能帆']
    alloc = equip_allocation(None, _dep(), owned)
    worn = {e for _, e in alloc}
    assert worn == set(owned), f'组件应默认参与分配,得 {alloc}'
    # 配对守卫:光能电池/轮滑鞋互为配方 → 无豁免信息时不落同一人
    wearer = {}
    for c, e in alloc:
        wearer[e] = c
    assert wearer['光能电池'] != wearer['轮滑鞋'], \
        f'危险配对应拆开发,得 {alloc}'


def test_pair_guard_blocks_second_basic_single_wearer() -> None:
    """配对守卫(P1):唯一穿者已有一件基础件时,互为配方的第二件拦下
    留 owned(非预期合成不可逆,ADR-0391)。"""
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    alloc = equip_allocation(None, dep, ['轮滑鞋', '光能电池'])
    worn = [e for _, e in alloc]
    assert worn == ['轮滑鞋'], f'第二件互配方基础件应被拦,得 {alloc}'


def test_key_equip_component_reaches_carry() -> None:
    """组件在 comp.key_equips → carry 正常拿到(角色特定意图路径,
    与旧豁免判据不同源:现在是同池分配,不再是保留过滤的放行分支)。"""
    from sr_od.application.currency_war.kernel.cw_comps import Comp

    comp = Comp(name='伪comp', factions=['追击'], core_chars=['飞霄'],
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=['光能电池'])
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['光能电池'])
    assert ('飞霄', '光能电池') in alloc, f'key_equips 组件应发 carry,得 {alloc}'


def test_capacity_semantics_unchanged() -> None:
    """容量语义不变:非基础件的分配量与旧语义一致(放宽只改池成分)。"""
    owned = ['蓄能帆', '永动机', '冷笑话引擎', '火力风暴潮']
    alloc = equip_allocation(None, _dep(), owned)
    assert len(alloc) <= 2 * EQUIP_CAPACITY
    assert {e for _, e in alloc} == set(owned), \
        f'非基础件应全部分配,得 {alloc}'


def test_reserved_components_registry_unchanged() -> None:
    """组件集单一源不变(8 件;图谱消费方 cw_synthesis 仍依赖)。"""
    assert len(set(RESERVED_COMPONENTS)) == 8
    assert '光能电池' in RESERVED_COMPONENTS
    assert '以太钻头' in RESERVED_COMPONENTS
