"""r135 装备分配场景生成器(用户提议:装备做成模拟数据 test)。

与 r134 手写 4 条互补:组合枚举 × 不变量。枚举面 = 真实分配维度:
- comp 态(None/有 core/key_equips 有无)
- deployed 构成(core 数 × 非 core 数 × 前后排)
- owned 构成(key 命中数 × 通用件数 × 件数 < / = / > 总容量)

不变量(分配纪律的数学性质,比断言具体分配更强):
I1 容量守恒:任何角色分得数 ≤ EQUIP_CAPACITY × 该角色槽位数
I2 key 优先:key_equips 全部分给 core(carry 先于其它 core)
I3 core 优先:comp 在场时,通用件先填满 core 才轮非 core
   (r134 具名样本背书——用户质询「为什么给砂金」:反甲白厄线 3 件通用
   应由 core 白厄吃满容量 3,非 core 砂金/赛飞儿 0 件,核心换血摩擦最小)
I4 不超发:输出总条数 ≤ owned 总数(每件至多一次)
I5 无 comp 轮转保序:comp=None 按 deployed 原序轮转(r232 改轮转,
   前排先入序;全序断言判别「deployed 原序」与「按行排序」两种实现)
"""
import itertools
import sys

import pytest

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_comps import (
    EQUIP_CAPACITY,
    Comp,
    equip_allocation,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar


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


@pytest.mark.parametrize('ci,di,oi', list(itertools.product(range(4), range(3), range(4))))
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
    # core 未上场时 key 件经兜底穿给场上人是合理行为(保战力)。core 上场后
    # 的转移不由分配器/本 op 直拖完成(装备不能角色间直拖;转移=卖角色或
    # 扳手拆,归决策器,见 equipment_mechanics「装备转移机制」节)。
    if comp is not None and comp.key_equips:
        keys = list(comp.key_equips)
        core_set = set(comp.core_chars) | ({comp.plaza_carry} if comp.plaza_carry else set())
        field_core = core_set & on_field
        for cname, w in alloc:
            if w in keys and field_core:
                assert cname in core_set, f'key 件 {w} 分给了非 core {cname}(core 在场)'
                keys.remove(w)   # multiplicity 消费
    # I3 core 优先(comp 在场):通用件填满 core 剩余容量前非 core 不拿
    # (core 容量可能已被 key 件占满——白厄 key×3 后通用容量 0,非 core 拿合法)。
    # 死库存豁免(ADR-0391,全 plane 生效——ADR-0265 增补后 P1 亦然):
    # 回收合格基础件先于 core 兜底抽取、改道非 core 工具人是有意的收益
    # 路由,不计入 I3 的「非 core 抢通用」违规面。本不变量原在 P1 保留
    # 过滤下写成(基础件永不入池,豁免面不可达),随过滤删除补豁免。
    if comp is not None:
        core_set = set(comp.core_chars)
        field_cores = [c for c in comp.core_chars if c in on_field]
        from sr_od.application.currency_war.data.cw_synthesis import (
            recycle_qualified,
        )
        dead = set(recycle_qualified(list(comp.key_equips or [])))
        key_used_by_core = sum(1 for c, w in alloc
                               if c in core_set and comp.key_equips and w in comp.key_equips)
        core_generic_cap = max(0, sum(EQUIP_CAPACITY for _ in field_cores) - key_used_by_core)
        generic_n = sum(1 for w in owned
                        if (not comp.key_equips or w not in comp.key_equips)
                        and w not in dead)
        core_got_generic = sum(1 for c, w in alloc if c in core_set
                               and (not comp.key_equips or w not in comp.key_equips)
                               and w not in dead)
        non_core_got = sum(1 for c, w in alloc if c not in core_set
                           and (not comp.key_equips or w not in comp.key_equips)
                           and w not in dead)
        if core_got_generic < min(generic_n, core_generic_cap) and non_core_got > 0:
            pytest.fail(f'core 通用容量未满({core_got_generic}<{min(generic_n, core_generic_cap)})'
                        f'但非 core 拿了 {non_core_got} 件')


def test_no_comp_rotation_keeps_deployed_order():
    """I5:comp=None 轮转按 deployed 原序(前排先入序;r232 轮转不改序)。

    4 人 front/back 交错帧:deployed 原序 ≠ 前排排序(翡翠 front 但序 4)
    ——只断首元素的旧形态对「按行排序」实现不红,全序断言才有判别力。
    2 人轮转 + 容量扣减面由 test_cw_target_matching
    ::test_equip_allocation_capacity_and_fallback 承载,两帧互补。"""
    dep = DEPLOYED_SETS[2]
    alloc = equip_allocation(None, dep, ['a', 'b', 'c', 'd'])
    assert alloc == [(d.char_id, e) for d, e in zip(dep, 'abcd')], alloc


# ----- dd-015 后补:阵营星徽排除同阵营角色(复盘 g_20260902_181254 定谳) -----

def _mk_dep(char_id, row='back', slot=1):
    return BenchChar(slot=slot, char_id=char_id, faction='', star=1, position_pref=row)


def test_emblem_not_allocated_to_same_faction():
    """列车同行星徽不发同阵营三月七(复盘 g_20260902_181254 定谳)。

    core 艾丝妲 occupied 穿满 3 件容量归零,星徽落到非 core 兜底位——
    无守卫时三月七(注册表自报列车同行)必得件,守卫在位则星徽无人可穿
    留 owned(原帧 core 容量未满、星徽必被非同阵营 core 先拿,守卫删除
    后该断言仍绿 = 零判别力,故改穿满帧)。"""
    deploy = [_mk_dep('艾丝妲', slot=1), _mk_dep('三月七', slot=2)]
    out = equip_allocation(
        _mk_comp(['艾丝妲']), deploy, ['列车同行星徽'],
        {('back', 1): ['x', 'y', 'z'], ('back', 2): []})
    assert all(not (c == '三月七' and e == '列车同行星徽') for c, e in out), out
    assert all(e != '列车同行星徽' for _, e in out), '守卫在位:同阵营无人可穿,星徽留 owned'


def test_emblem_allowed_to_other_faction():
    """非同阵营角色正常获得星徽(add-if-absent 授予新羁绊=星徽用途)。"""
    deploy = [_mk_dep('艾丝妲', slot=1), _mk_dep('三月七', slot=2)]
    out = equip_allocation(
        _mk_comp(['艾丝妲']), deploy, ['列车同行星徽'],
        {('back', 1): [], ('back', 2): []})
    assert any(e == '列车同行星徽' for _, e in out), out


def test_emblem_same_faction_left_in_pool():
    """全员同阵营(列车同行)时星徽留 owned(不产出任何同阵营组合)。"""
    deploy = [_mk_dep('三月七', slot=1), _mk_dep('丹恒·饮月', slot=2)]
    out = equip_allocation(None, deploy, ['列车同行星徽', '列车同行星徽'],
                           {('back', 1): [], ('back', 2): []})
    assert all(e != '列车同行星徽' for _, e in out), out