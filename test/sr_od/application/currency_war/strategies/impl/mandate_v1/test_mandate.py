"""mandate 骨架帧装配测试(k_members 换源面;阶段 1 = roster-plane1-
union design §2.6 换源不消亡;过渡支口径 = 32 号稿 §2)。

被测 = ``strategies/impl/mandate_v1/mandate.py`` 的 ``snapshot_frame``
与 ``cheapest_member_cost``:k_members 装配读口从
``predicates.line_members(direction_comp_of)`` 换源为统一线内名单
(:func:`sell_line_membership`,双层口径 = 实候选 ∪ 过渡候选 ∪
锁定线并集)——P1 锁定局过渡成员随换源可见;保留面消费(金需求侧
``cheapest_member_cost``)随名册变宽照常供数。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_members,
    cw4_session,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    _pair_members,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    cheapest_member_cost,
    snapshot_frame,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _p1_locked_seed():
    """P1 锁定局种子:锁定线 = 双王圣杯,过渡候选 = 持续伤害×希儿系
    (注册表事实:卡芙卡/希儿 ∈ 过渡对 ∉ 锁定线);plane2 缺省未启动。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc('卡芙卡')], node='prep')
    st = state_of(gs)
    st.target_comp = get_comp('双王圣杯')
    st.transition_candidates = (('持续伤害', '希儿系'),)
    return gs


def test_snapshot_frame_k_members_p1_locked_union() -> None:
    """snapshot_frame k_members 换源(design §2.6;过渡支口径 =
    §2.4-5):P1 锁定局 frame.k_members = 锁定线 ∪ 过渡候选成员并集
    (修复前 direction 读口锁定帧只见锁定线,过渡成员不可见);排序序
    承载。"""
    gs = _p1_locked_seed()
    frame = snapshot_frame(gs)
    expected = set(cw4_members(get_comp('双王圣杯'))) \
        | _pair_members(('持续伤害', '希儿系'))
    assert set(frame.k_members) == expected
    assert frame.k_members == tuple(sorted(expected))
    assert '卡芙卡' in frame.k_members, '纯过渡成员随换源可见'


def test_snapshot_frame_k_members_p2_recipe_exits() -> None:
    """进位面 2:过渡支退出——frame.k_members 退回锁定线单源(槽位
    残留不消费,判窗在槽直读之前)。"""
    gs = _p1_locked_seed()
    state_of(gs).plane2_started = True
    frame = snapshot_frame(gs)
    assert set(frame.k_members) == set(cw4_members(get_comp('双王圣杯')))
    assert '卡芙卡' not in frame.k_members


def test_cheapest_member_cost_reads_widened_roster() -> None:
    """金需求侧保留面消费回归(design §2.6 D4-6:成员口径变宽):
    cheapest_member_cost 按 frame.k_members 全名册注册表现查取最低
    费——P1 锁定局名册含过渡成员后,最低费随名册变宽(不高于锁定线
    单源口径;硬约束①金需求侧不断粮)。"""
    gs = _p1_locked_seed()
    frame = snapshot_frame(gs)
    costs = [CHARACTERS[m].cost for m in frame.k_members
             if CHARACTERS.get(m) is not None and CHARACTERS[m].cost]
    assert costs, '前置:名册内注册成员非空'
    assert cheapest_member_cost(frame) == min(costs)
    # 名册变宽方向:并集口径 ≤ 锁定线单源口径(过渡侧 1 费椒丘在册)。
    lock_costs = [CHARACTERS[m].cost for m in
                  cw4_members(get_comp('双王圣杯'))
                  if CHARACTERS.get(m) is not None and CHARACTERS[m].cost]
    assert cheapest_member_cost(frame) <= min(lock_costs)
