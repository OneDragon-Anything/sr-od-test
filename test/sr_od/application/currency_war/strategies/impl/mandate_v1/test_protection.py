"""过渡锁定态合并与终局锁定清空出口测试(comp-structure-unification 3.3)。

被测 = 过渡锁定态合并裁定落点:旧 ``transition_locked_systems`` 槽与
``protection.refresh_transition_locked_systems`` 写端已删除(合并裁定,
不并存两套锁定态),职责由 ``v3_intention.transition_locked`` 承接
(写端 = kernel 过渡候选机器 ``update_transition_candidates``,锁定
判据测试面在 test_cw_transition_library.py)。本文件锁「终局锁定
写入点 = 过渡层退役清空出口」契约(候选槽 + 过渡锁定态同点清空;
位面切换不触发退役——生命周期挂钩终局锁定事件)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import cw4_bc, cw4_gs

from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)


def test_final_lock_retires_transition_layer() -> None:
    """终局锁定写入 = 过渡层退役清空出口:候选槽与 transition_locked
    同点清空,锁后不复活(贵段停驱)。"""
    sess = StrategySession()
    gs = cw4_gs(sess, plane=2, round_num=3, node='prep',
                bench=[cw4_bc('希儿'), cw4_bc('花火')],
                shop_screen='off')
    st = state_of(gs)
    st.transition_candidates = ('希儿引擎',)
    st.v3_intention = IntentionState()
    st.v3_intention.transition_locked = '希儿引擎'
    session_scope.write_line_lock(gs, '希儿量子')
    assert st.transition_candidates == (), '终局锁定写入点清空候选槽'
    assert st.v3_intention.transition_locked == '', \
        '终局锁定写入点清空过渡锁定态(交棒:过渡层退役)'
    assert st.target_comp is not None


def test_plane_switch_keeps_transition_layer() -> None:
    """位面切换不触发退役:进位面 2 后贵段照常驱动(未终局锁定帧
    过渡层活跃——换轴行为申报 6),锁定态/候选槽不因位面边界清空。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )

    sess = StrategySession()
    gs = cw4_gs(sess, plane=1, round_num=9, node='prep', shop_screen='off')
    gs.node_hist_pos = (1, 9)
    strat = MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))
    st = state_of(gs)
    st.transition_candidates = ('廉价DOT',)
    st.v3_intention = IntentionState()
    st.v3_intention.transition_locked = '廉价DOT'
    strat._refresh_direction(gs, st)
    # 进位面 2(未终局锁定):清空不发生
    cw4_gs(sess, plane=2, round_num=1, node='prep', shop_screen='off')
    gs.node_hist_pos = (2, 1)
    session_scope.handle_node_boundary(gs)
    strat._refresh_direction(gs, st)
    assert st.v3_intention.transition_locked == '廉价DOT', \
        '位面切换不触发过渡层退役(生命周期挂钩终局锁定事件)'
    assert st.target_comp is None


# (TestTransitionLockedSystems 旧测试面〔transition_locked_systems 槽
#  写端/幂等只增/进位面清空〕已随合并裁定删除:锁定判据 = 候选内成型,
#  测试面迁 test_cw_transition_library.py;TestProtectionMembership
#  保护集成员函数测试已随 protection_membership 退役删除——统一让位
#  优先级迭代 3.4。本文件保留面 = 合并清空出口契约与
#  CROSS_LINE_KEEP_NAMES 数据源(消费 = criteria/priority.py 档 8
#  万金油层,测试面在 test_priority)。)
