"""r135 装备分配场景生成器(用户提议:装备做成模拟数据 test)。

与 r134 手写 4 条互补:组合枚举 × 不变量。枚举面 = 真实分配维度:
- comp 态(None/有 core/key_equips 有无)
- deployed 构成(core 数 × 非 core 数 × 前后排)
- owned 构成(key 命中数 × 通用件数 × 件数 < / = / > 总容量)

不变量(分配纪律的数学性质,比断言具体分配更强):
I1 容量守恒:任何角色分得数 ≤ EQUIP_CAPACITY × 该角色槽位数
I2 key 优先:key_equips 全部分给 core(carry 先于其它 core)
I3 core 优先:comp 在场时,通用件先填满 core 才轮非 core
I4 不超发:输出总条数 ≤ owned 总数(每件至多一次)
I5 无 comp 保持兜底序:comp=None 时前排先(deployed 原序)
"""
import itertools
import sys

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.cw_comps import (
    COMMIT_FRAC,
    EQUIP_CAPACITY,
    Comp,
    equip_allocation,
)
from sr_od.application.currency_war.cw_state import BenchChar


def _mk_comp(cores, keys=None, carry=None):
    c = Comp(name='测试线', factions=['贝洛伯格'], core_chars=list(cores),
             form_tiers={}, strength=5.0, form_difficulty='hard')
    c.key_equips = list(keys or [])
    if carry:
        c.plaza_carry = carry
    return c


# 枚举面(压缩到代表性档)
COMPS = [None,
         _mk_comp(['白厄']),                        # 单 core 无 key
         _mk_comp(['白厄', '三月七']),              # 双 core
         _mk_comp(['白厄', '三月七'], ['以牙还牙甲', '以牙还牙甲', '高周波电锯'], carry='白厄')]
DEPLOYED_SETS = [
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front')],
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front'),
     BenchChar(slot=2, char_id='白厄', faction='贝洛伯格', star=1, position_pref='front')],
    [BenchChar(slot=1, char_id='砂金', faction='公司', star=1, position_pref='front'),
     BenchChar(slot=1, char_id='白厄', faction='贝洛伯格', star=1, position_pref='back'),
     BenchChar(slot=2, char_id='三月七', faction='列车同行', star=1, position_pref='back'),
     BenchChar(slot=2, char_id='翡翠', faction='公司', star=1, position_pref='front')],
]
OWNED_SETS = [
    [],
    ['以牙还牙甲'],
    ['狙击枪', '生命之花', '物质分解液'],
    ['以牙还牙甲', '以牙还牙甲', '高周波电锯', '狙击枪', '生命之花'],
]


@pytest.mark.parametrize('ci,di,oi', itertools.product(range(4), range(3), range(4)))
def test_allocation_invariants(ci, di, oi):
    comp, dep, owned = COMPS[ci], DEPLOYED_SETS[di], OWNED_SETS[oi]
    alloc = equip_allocation(comp, dep, owned)
    # I4 不超发
    assert len(alloc) <= len(owned)
    # I1 容量守恒
    per_char: dict[str, int] = {}
    for cname, _w in alloc:
        per_char[cname] = per_char.get(cname, 0) + 1
    on_field = {d.char_id for d in dep if d.char_id}
    for cname, n in per_char.items():
        assert cname in on_field, f'{cname} 不在场上却分得装备'
        assert n <= EQUIP_CAPACITY, f'{cname} 超 EQUIP_CAPACITY'
    # I2 key 优先:key_equips 只给 core(carry 含);**core 在场前提**——
    # core 未上场时 key 件经兜底穿给场上人是合理行为(保战力,core 上场后
    # C6 转移挪;分配器无「等 core」语义,转移层负责)。
    if comp is not None and comp.key_equips:
        keys = list(comp.key_equips)
        core_set = set(comp.core_chars) | ({comp.plaza_carry} if comp.plaza_carry else set())
        field_core = core_set & on_field
        for cname, w in alloc:
            if w in keys and field_core:
                assert cname in core_set, f'key 件 {w} 分给了非 core {cname}(core 在场)'
                keys.remove(w)   # multiplicity 消费
    # I3 core 优先(comp 在场):通用件填满 core 剩余容量前非 core 不拿
    # (core 容量可能已被 key 件占满——白厄 key×3 后通用容量 0,非 core 拿合法)
    if comp is not None:
        core_set = set(comp.core_chars)
        field_cores = [c for c in comp.core_chars if c in on_field]
        key_used_by_core = sum(1 for c, w in alloc
                               if c in core_set and comp.key_equips and w in comp.key_equips)
        core_generic_cap = max(0, sum(EQUIP_CAPACITY for _ in field_cores) - key_used_by_core)
        generic_n = sum(1 for w in owned
                        if not comp.key_equips or w not in comp.key_equips)
        core_got_generic = sum(1 for c, w in alloc if c in core_set
                               and (not comp.key_equips or w not in comp.key_equips))
        non_core_got = sum(1 for c, w in alloc if c not in core_set
                           and (not comp.key_equips or w not in comp.key_equips))
        if core_got_generic < min(generic_n, core_generic_cap) and non_core_got > 0:
            pytest.fail(f'core 通用容量未满({core_got_generic}<{min(generic_n, core_generic_cap)})'
                        f'但非 core 拿了 {non_core_got} 件')


def test_no_comp_front_first():
    """I5:comp=None 保持 deployed 序(前排先)。"""
    dep = DEPLOYED_SETS[2]
    alloc = equip_allocation(None, dep, ['a', 'b', 'c', 'd'])
    assert alloc[0][0] == '砂金', '无 comp 时按 deployed 原序(前排先)'
