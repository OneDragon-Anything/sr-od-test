# -*- coding: utf-8 -*-
"""r405(ADR-0265,压测经济批 [29]):装备合成组件保留。

P1(plane==1)阶段,合成保留组件(cw_synthesis.RESERVED_COMPONENTS =
7 件标准基础件 ∪ 光能电池)不入穿戴池——组件留在 owned 待合成;
过渡穿着 = 锁死合成路线 + 浪费转移成本(口述 [29],局70 实机 +
sim 16/60 局同构实证,sim/实机同一 equip_allocation 纯函数)。

豁免边界:组件恰是 comp.key_equips 时放行(COMP_LIBRARY 实查零重叠
——豁免是防御性判据)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_comps import (
    EQUIP_CAPACITY,
    equip_allocation,
)
from sr_od.application.currency_war.cw_state import BenchChar
from sr_od.application.currency_war.cw_synthesis import RESERVED_COMPONENTS
from sr_od.application.currency_war.cw_sim_checks import (
    check_no_component_equipped_p1,
)


def _dep():
    return [BenchChar(slot=1, char_id='飞霄', position_pref='front'),
            BenchChar(slot=2, char_id='三月七', position_pref='front')]


def test_component_not_equipped_p1() -> None:
    """P1:组件不入穿戴池(兜底路径),留在 owned。"""
    owned = ['光能电池', '轮滑鞋', '蓄能帆', '量产型装甲']
    alloc = equip_allocation(None, _dep(), owned, plane=1)
    worn = {e for _, e in alloc}
    assert worn == {'蓄能帆'}, f'P1 组件不该被穿,得 {alloc}'


def test_component_equipped_p2() -> None:
    """P2+:过滤关闭(合成窗口关闭,组件穿着不再锁路线)。"""
    owned = ['光能电池', '轮滑鞋', '蓄能帆']
    alloc = equip_allocation(None, _dep(), owned, plane=2)
    worn = {e for _, e in alloc}
    assert '光能电池' in worn and '轮滑鞋' in worn, \
        f'P2 组件照常分配,得 {alloc}'


def test_key_equip_exempt_boundary() -> None:
    """豁免边界:组件在 comp.key_equips → 放行(防御性判据;
    构造伪 comp 验证,COMP_LIBRARY 实查零重叠)。"""
    from sr_od.application.currency_war.cw_comps import Comp

    comp = Comp(name='伪comp', factions=['追击'], core_chars=['飞霄'],
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=['光能电池'])
    dep = [BenchChar(slot=1, char_id='飞霄', position_pref='front')]
    alloc = equip_allocation(comp, dep, ['光能电池'], plane=1)
    assert ('飞霄', '光能电池') in alloc, \
        f'key_equips 命中的组件应豁免保留过滤,得 {alloc}'


def test_capacity_semantics_unchanged() -> None:
    """容量语义不变:非组件件的分配量与旧语义一致(过滤只改池成分)。"""
    owned = ['蓄能帆', '永动机', '冷笑话引擎']
    alloc_p1 = equip_allocation(None, _dep(), owned, plane=1)
    alloc_p2 = equip_allocation(None, _dep(), owned, plane=2)
    assert alloc_p1 == alloc_p2, '非组件内容两 plane 分配应一致'
    assert len(alloc_p1) <= 2 * EQUIP_CAPACITY


def test_check_no_component_equipped_p1() -> None:
    """检查项双向锁:违规账本报、干净账本不报。"""
    bad_row = {'plane': 1, 'round_num': 5, 'state': {
        'equipped': [{'char': '绯英', 'equip': '光能电池'}]}}
    assert check_no_component_equipped_p1([bad_row]), '组件穿着应违规'
    ok_row = {'plane': 1, 'round_num': 5, 'state': {
        'equipped': [{'char': '绯英', 'equip': '火力风暴潮'}]}}
    assert not check_no_component_equipped_p1([ok_row])
    p2_row = {'plane': 2, 'round_num': 5, 'state': {
        'equipped': [{'char': '绯英', 'equip': '轮滑鞋'}]}}
    assert not check_no_component_equipped_p1([p2_row]), 'P2 不辖'
    assert '光能电池' in RESERVED_COMPONENTS
    assert '以太钻头' in RESERVED_COMPONENTS
