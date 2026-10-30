"""过渡锁定状态槽 kernel 批单帧测试(写入端 + 清空点接线)。

被测 = ``src/sr_od/application/currency_war/strategies/impl/mandate_v1/
protection.py``(:func:`refresh_transition_locked_systems`)与写点/清空点
接线(bridge 两决策入口前置段 / flow 进 P2 分支)。

出处 = ``docs/develop/sr_od/application/currency_war/changes/2026-10-15-
unified-protection-set/design.md`` §2.1(点亮判定 = 持有域支持度链达标;
保护集判据件已随统一让位优先级迭代 3.4 退役,本文件保留面 = 过渡锁定
状态槽写端,原域分派表作历史锚)/ §2.6(单帧验证设计:点亮锁定判据)
与同目录 ``landing.md`` 3.1 完成判据。

成员代表锚(注册表 cw_chars 事实,机械重推):
- 仙舟系:青雀/停云/藿藿(factions=仙舟);3 人支持度 = 3/3 = 1.0 达标;
- 持续伤害系:桑博(flows=持续伤害);
- 列车同行系:姬子·启行(factions=列车同行);
- 希儿系:希儿(factions=贝洛伯格,flows=量子同频,单卡 0.5 不足)+
  放大器花火/缇宝(flows=量子同频)——希儿+任 1 去重放大器 = 1.0 达标;
- 非四体系:阿格莱雅(昼之半神/能量)。
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    refresh_transition_locked_systems,
)


class TestTransitionLockedSystems:
    """过渡锁定状态槽(design §2.1 点亮判定 + §2.7 锁定持久化)。"""

    def test_prep_entry_locks_xianzhou_trio(self, monkeypatch):
        """判据①:仙舟 3 人在场 → 锁定槽含仙舟;写入端走真实生产路径
        (bridge.decide_prep_screen 前置段挂 refresh,写点 =
        refresh_line_if_needed 同点;armed 判定核桩化为单键替身短路
        后续九段,真 armed 判据不在本测试面)——设计 §2.6 / landing 3.1。"""
        import sr_od.application.currency_war.kernel.cw_launch_admission as admit_mod

        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    bench=[cw4_bc('青雀'), cw4_bc('停云'), cw4_bc('藿藿')],
                    shop_screen='off')
        gs.node_hist_pos = (1, 2)
        monkeypatch.setattr(admit_mod, 'readiness_launch_decision',
                            lambda *a, **k: {'armed': True})
        strat = MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))
        st = state_of(gs)   # 构造 setter 已接线容器 → 同一状态对象
        strat.decide_prep_screen()
        assert '仙舟' in st.transition_locked_systems

    def test_sold_member_does_not_drop_lock(self):
        """判据②:卖退 1 人不掉锁定(幂等只增不减——支持度回落后已
        入槽体系不收缩;design §2.7「掉档 → 保护收缩 → 连锁卖」恶性
        循环防线)/ landing 3.1。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    bench=[cw4_bc('青雀'), cw4_bc('停云'), cw4_bc('藿藿')])
        st = state_of(gs)
        refresh_transition_locked_systems(gs, st)
        assert '仙舟' in st.transition_locked_systems
        # 卖退一人:bench 域重落 = 2 人(支持度 2/3 < 1.0,本帧无新达标)
        cw4_gs(sess, plane=1, round_num=3, node='prep',
               bench=[cw4_bc('青雀'), cw4_bc('停云')])
        refresh_transition_locked_systems(gs, st)
        assert '仙舟' in st.transition_locked_systems

    def test_quantum_without_seele_not_locked(self):
        """判据③:量子 3 件无希儿 → 不锁希儿系(支持度公式首行希儿
        在场门:放大器不能独立当过渡;design §2.1)/ landing 3.1。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    bench=[cw4_bc('花火'), cw4_bc('缇宝'), cw4_bc('银狼')])
        st = state_of(gs)
        refresh_transition_locked_systems(gs, st)
        assert '希儿系' not in st.transition_locked_systems

    def test_bench_only_quantum_locks(self):
        """判据④:量子件全在 bench 未上阵 → 锁(持有域分辨用例,拦
        「误实现成板面域」——板面域判定 seele_system_formed 读场上名单
        与板面羁绊,本帧全 bench 时恒假;design §2.1 双源差异申报选定
        持有域)/ landing 3.1。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    bench=[cw4_bc('希儿'), cw4_bc('花火'), cw4_bc('缇宝')])
        st = state_of(gs)
        refresh_transition_locked_systems(gs, st)
        assert '希儿系' in st.transition_locked_systems

    def test_p2_entry_clears_slot(self):
        """清空点 = 进位面 2(flow._refresh_direction 配方退场同点):
        P1 贵段不清槽(幂等只增),窗口谓词翻真后首个贵段槽清空;
        design §2.1 域切换。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=9, node='prep')
        gs.node_hist_pos = (1, 9)
        strat = MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))
        st = state_of(gs)
        st.transition_locked_systems = frozenset({'仙舟'})
        st.v3_intention = IntentionState(p1_pair=('仙舟', '持续伤害'))
        strat._refresh_direction(gs, st)
        assert st.transition_locked_systems == frozenset({'仙舟'})
        # 进 P2:边界置窗口谓词 + 贵段同点清槽
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs.node_hist_pos = (2, 1)
        session_scope.handle_node_boundary(gs)
        strat._refresh_direction(gs, st)
        assert st.transition_locked_systems == frozenset()


# (TestProtectionMembership 保护集成员函数测试已随 protection_membership
#  退役删除——统一让位优先级迭代 3.4:静态不许卖名单与买面囤货判据
#  整批退役,保护集「自己人」概念消亡;本文件保留面 = 过渡锁定状态槽
#  写端(TestTransitionLockedSystems)与 CROSS_LINE_KEEP_NAMES 数据源
#  (消费 = criteria/priority.py 档 6)。)
