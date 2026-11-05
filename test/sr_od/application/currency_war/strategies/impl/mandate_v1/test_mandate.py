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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    cheapest_member_cost,
    snapshot_frame,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def _p2_unlocked_seed(plane2: bool = True):
    """位面 2 未终局锁定种子:过渡候选 = DOT2+列车2(注册表事实:卡芙卡
    ∈ DOT2 块域,无锁定线);终局锁定态缺省未置。"""
    session = cw4_session()
    gs = cw4_gs(session, plane=2 if plane2 else 1, level=7,
                bench=[cw4_bc('卡芙卡')], node='prep')
    st = state_of(gs)
    if plane2:
        st.plane2_started = True
    st.transition_candidates = ('DOT2+列车2',)
    return gs


def test_snapshot_frame_k_members_p2_unlocked_union() -> None:
    """snapshot_frame k_members 换源(换轴后口径):位面 2 未终局锁定帧
    frame.k_members = 过渡层贡献名单(原「P1 锁定局并集」形态随终局
    锁定即退役收敛——锁定帧名单 = 锁定线单源);排序序承载。"""
    gs = _p2_unlocked_seed()
    frame = snapshot_frame(gs)
    expected = {'卡芙卡', '桑博', '椒丘', '海瑟音', '艾丝妲', '黑天鹅',
                '姬子·启行', '三月七'}
    assert set(frame.k_members) == expected
    assert frame.k_members == tuple(sorted(expected))
    assert '卡芙卡' in frame.k_members, '过渡成员随换源可见(位面 2 照收)'


def test_snapshot_frame_k_members_final_lock_line_only() -> None:
    """终局锁定:frame.k_members 退回锁定线单源(过渡层在锁定写入点
    退役清空,槽位残留不消费)。"""
    session = cw4_session()
    gs = cw4_gs(session, level=7, bench=[cw4_bc('卡芙卡')], node='prep')
    st = state_of(gs)
    st.target_comp = get_comp('双王圣杯')
    st.transition_candidates = ('DOT2+列车2',)
    frame = snapshot_frame(gs)
    assert set(frame.k_members) == set(cw4_members(get_comp('双王圣杯')))
    assert '卡芙卡' not in frame.k_members


def test_cheapest_member_cost_reads_widened_roster() -> None:
    """金需求侧保留面消费回归(design §2.6 D4-6:成员口径变宽):
    cheapest_member_cost 按 frame.k_members 全名册注册表现查取最低
    费——位面 2 未终局锁定帧名册含过渡层贡献名单后,最低费随名册变宽
    (不高于空名册侧;硬约束①金需求侧不断粮)。"""
    gs = _p2_unlocked_seed()
    frame = snapshot_frame(gs)
    costs = [CHARACTERS[m].cost for m in frame.k_members
             if CHARACTERS.get(m) is not None and CHARACTERS[m].cost]
    assert costs, '前置:名册内注册成员非空'
    assert cheapest_member_cost(frame) == min(costs)
