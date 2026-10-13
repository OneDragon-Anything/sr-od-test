"""策略器 session 作用域键基建锁(节点边界重置/窗口谓词/方向状态骨架/
商店会话标记与机会清单存储)。

出处 = 迭代 changes/2026-10-12-prep-shop-workflow-redesign:
- prep_pipeline §3(节点边界重置清单五项 + 触发检测判重语义)、
  design 契约 C(重置清单唯一所有者);
- line_and_upgrade §3(方向签名前置段/锁定写入连带动作三件/锁定线与
  配方物化分键/候选快照停算)、契约 B(方向状态读写接口);本阶段
  方向解析 = 现行为等价(现行 target_comp 物化链照读),候选-锁定
  判据本体在迭代批 3.7 替换内核;
- shop_session §4.1/§4.2(标记值 = 节点号二元组、值比对双保险、
  机会清单记录字段)、契约 A(标记与清单的存储归本批,解拦复核判定
  函数归 3.6)。

锁语义均不逐字段断言锁核载荷(锁定判据本体测试归 3.7);节点号驱动
= 直赋 ``gs.node_hist_pos``(生效序位的单调水位分量,生产写端 =
advance_node_effective,已有自己的测试辖)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import cw4_comp, cw4_gs

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    LevelUpPreAuth,
    ShopOpportunity,
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
    clear_shop_handled,
    clear_shop_opportunities,
    handle_node_boundary,
    line_members_view,
    mark_shop_handled,
    plane2_started_of,
    record_shop_opportunity,
    refresh_line_if_needed,
    shop_handled_for_current_node,
    shop_opportunities_of,
    write_line_lock,
)


def _sess_with_node(plane: int, round_num: int):
    """裸容器 + 生效节点号直种(node_hist_pos 水位分量驱动)。"""
    sess = StrategySession()
    gs = game_state_of(sess)
    gs.node_hist_pos = (plane, round_num)
    return sess, gs


# ===== 节点边界重置(prep_pipeline §3 清单逐键 + 判重)=====


class TestNodeBoundaryReset:

    def test_boundary_resets_registered_keys_then_dedupes(self):
        """清单四项重置键在节点号变化时按表复位;同节点号重复调用不
        重复执行(哨兵存活 = 判重跳过);节点号再变 → 再次执行。"""
        sess, gs = _sess_with_node(1, 2)
        st = state_of(gs)
        st.shop_handled = (1, 1)
        st.shop_opportunities = (ShopOpportunity(
            card_name='x', blocked_by='bench_full', price=1,
            order_class='seq1'),)
        st.levelup_preauth = LevelUpPreAuth(gold_cost=10, blood_cost=0)
        st.line_eval_signature = ('stale',)
        handle_node_boundary(gs)
        assert st.shop_handled is None          # ①标记清值
        assert st.shop_opportunities == ()      # ②清单清空
        assert st.levelup_preauth is None       # ③预授权键清零
        assert st.line_eval_signature is None   # ④签名置失效
        assert st.node_boundary_last_pos == (1, 2)
        # 判重:同节点号重复调用不重复执行
        st.shop_handled = (1, 2)
        handle_node_boundary(gs)
        assert st.shop_handled == (1, 2)
        # 节点号变化 → 再次执行
        gs.node_hist_pos = (1, 3)
        handle_node_boundary(gs)
        assert st.shop_handled is None
        assert st.node_boundary_last_pos == (1, 3)

    def test_boundary_noop_without_node_pos(self):
        """节点号未观察(None)不执行:未观察不当真(prev 记录不被
        无效帧污染)。"""
        sess = StrategySession()
        gs = game_state_of(sess)
        st = state_of(gs)
        st.shop_handled = (1, 2)
        handle_node_boundary(gs)
        assert st.shop_handled == (1, 2)
        assert st.node_boundary_last_pos is None


class TestBoundaryKeepsDirectionState:

    def test_boundary_keeps_direction_state_and_current_target_comp(self):
        """清单第 5 项负登记:方向状态(锁定线/配方键)与现行
        target_comp 跨节点保留——节点边界不清方向,契约 C;候选快照
        键边界亦不辖(锁定写入时已被清空,手工哨兵 = 模拟外部写入后
        边界不复位);签名置失效(第 4 项)与之同帧对照,锁分界本身。"""
        sess, gs = _sess_with_node(1, 2)
        st = state_of(gs)
        comp = cw4_comp()
        write_line_lock(gs, comp.name)
        st.line_candidates = ('external-write',)
        st.opening_recipe_comp = comp
        st.target_comp = comp   # 现行物化链产物(边界函数不辖此键)
        gs.node_hist_pos = (1, 5)
        handle_node_boundary(gs)
        assert st.line_locked_comp == comp.name   # 锁定跨节点保留
        assert st.line_candidates == ('external-write',)
        assert st.opening_recipe_comp is comp
        assert st.target_comp is comp             # 现行键零破坏
        assert st.line_eval_signature is None     # 签名置失效(对照)


# ===== 窗口谓词标志(line_and_upgrade §1.4 时点兜底载体)=====


class TestPlane2StartedFlag:

    def test_flag_sets_on_first_plane2_node_and_survives_boundary(self):
        """node_hist_pos 序位首入 (2,*) 段置位;P1 内不置位;置位后
        跨节点保留(边界重置不复位——历史事实非节点作用域态)。"""
        sess = StrategySession()
        gs = game_state_of(sess)
        st = state_of(gs)
        gs.node_hist_pos = (1, 9)
        handle_node_boundary(gs)
        assert st.plane2_started is False
        gs.node_hist_pos = (2, 1)
        handle_node_boundary(gs)
        assert st.plane2_started is True
        assert plane2_started_of(gs) is True
        # 跨节点保留:节点推进触发边界重置,标志不复位
        st.shop_handled = (2, 1)
        gs.node_hist_pos = (2, 2)
        handle_node_boundary(gs)
        assert st.shop_handled is None       # 边界重置确实发生了
        assert st.plane2_started is True


# ===== 方向签名前置段骨架(本阶段 = 现行为等价内核)=====


class TestLineRefreshSkeleton:

    def test_signature_skip_and_recompute(self):
        """签名不变跳过重算、签名变化触发重算(幂等性;哨兵法——
        重算的可观测副作用 = 派生快照覆写)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        st = state_of(gs)
        refresh_line_if_needed(gs)
        assert st.line_eval_signature is not None
        # 签名未变:哨兵存活 = 重算被跳过
        st.line_candidates = ('sentinel',)
        refresh_line_if_needed(gs)
        assert st.line_candidates == ('sentinel',)
        # 签名变化(节点号推进)→ 重算发生(哨兵被覆写)
        gs.node_hist_pos = (1, 3)
        refresh_line_if_needed(gs)
        assert st.line_candidates != ('sentinel',)
        assert st.line_candidates == ()   # 未定向 → 空候选

    def test_level_dimension_change_triggers_recompute(self):
        """等级维独立触发重算(签名多维性,review-31 风险②):同持有/
        同节点号、仅等级变化 → 签名变化 → 重算。等级入签名的动机 =
        店内整级购买经验后概率表变,消费旧等级 = 评估陈旧
        (line_and_upgrade §3 步骤 1)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=3)
        st = state_of(gs)
        refresh_line_if_needed(gs)
        st.line_candidates = ('sentinel',)
        # 仅等级变化(持有/节点号/装备/投资集不变)
        cw4_gs(sess, plane=1, round_num=2, node='prep', level=4)
        refresh_line_if_needed(gs)
        assert st.line_candidates != ('sentinel',)

    def test_recompute_reads_current_target_comp_chain(self):
        """本阶段行为等价锁:重算照读现行 target_comp 物化链产物
        (配方键 = 产物本体、候选快照 = 产物名单元素);未锁定视图 =
        空名单 + 未锁定旗标。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        st = state_of(gs)
        comp = cw4_comp()
        st.target_comp = comp   # 现行物化链产物(测试直种 = 照读输入)
        refresh_line_if_needed(gs)
        assert st.opening_recipe_comp is comp
        assert st.line_candidates == (comp.name,)
        view = line_members_view(gs)
        assert view.locked is False
        assert view.comp_name is None
        assert view.members == ()


# ===== 锁定写入骨架(连带动作三件 + 锁后只读)=====


class TestLineLockSkeleton:

    def test_write_lock_side_effects_and_readonly(self):
        """锁定写入联动三件(清预授权键/清商店标记/候选快照清空并停算
        ——review-31 风险③:锁定后读快照恒 = 空集,消费无歧义)+ 锁后
        只读(重复写入不改锁定线;硬规则判定本体测试归 3.7)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        st = state_of(gs)
        comp = cw4_comp()
        st.levelup_preauth = LevelUpPreAuth(gold_cost=10, blood_cost=0)
        st.shop_handled = (1, 2)
        st.line_candidates = ('候选态',)   # 锁定前的非空候选态
        write_line_lock(gs, comp.name)
        assert st.line_locked_comp == comp.name
        assert st.levelup_preauth is None   # ①清升级预授权键
        assert st.shop_handled is None      # ②清商店会话标记
        assert st.line_candidates == ()     # ③候选快照清空
        # 停算:签名变化后重算不再写入快照(恒空)
        gs.node_hist_pos = (1, 3)
        refresh_line_if_needed(gs)
        assert st.line_candidates == ()
        # 锁后只读:重复写入不改锁定线(骨架不解析线名,参数即意图)
        write_line_lock(gs, '其他线名')
        assert st.line_locked_comp == comp.name

    def test_locked_view_returns_line_members(self):
        """锁定后视图 = 锁定线名单(core ∪ shared 集合语义,注册表
        单一源现算对照);未锁定视图空名单由 TestLineRefreshSkeleton 辖。"""
        _, gs = _sess_with_node(1, 2)
        comp = cw4_comp()
        write_line_lock(gs, comp.name)
        view = line_members_view(gs)
        assert view.locked is True
        assert view.comp_name == comp.name
        assert view.members
        assert set(view.members) == (set(comp.core_chars)
                                     | set(getattr(comp, 'shared_chars', None) or ()))


# ===== 商店会话标记与机会清单存储(shop_session §4)=====


class TestShopMarksStorage:

    def test_mark_query_and_value_comparison(self):
        """标记值 = 当前节点号二元组;值比对双保险(值 ≠ 当前节点号
        视为未处理);清除口。"""
        sess, gs = _sess_with_node(1, 5)
        st = state_of(gs)
        mark_shop_handled(gs)
        assert st.shop_handled == (1, 5)
        assert shop_handled_for_current_node(gs) is True
        gs.node_hist_pos = (1, 6)
        assert shop_handled_for_current_node(gs) is False   # 双保险
        clear_shop_handled(gs)
        assert st.shop_handled is None

    def test_mark_noop_without_node_pos(self):
        """节点号未观察时写标记 no-op(未观察不当真)。"""
        sess = StrategySession()
        gs = game_state_of(sess)
        mark_shop_handled(gs)
        assert state_of(gs).shop_handled is None

    def test_opportunity_record_query_clear_and_node_reset(self):
        """清单追加/查询/清空存储口 + 节点边界重置清空(清单表②)。"""
        sess, gs = _sess_with_node(1, 5)
        st = state_of(gs)
        rec = ShopOpportunity(card_name='三月七', blocked_by='gold_short',
                              price=2, order_class='seq1')
        record_shop_opportunity(gs, rec)
        assert shop_opportunities_of(gs) == (rec,)
        clear_shop_opportunities(gs)
        assert shop_opportunities_of(gs) == ()
        # 节点边界重置清空(存储函数之外的重置路径 = 清单表复位)
        record_shop_opportunity(gs, rec)
        gs.node_hist_pos = (1, 6)
        handle_node_boundary(gs)
        assert st.shop_opportunities == ()


# ===== 双域接线(备战/商店两入口各调同一对函数)=====


class TestEntryWiring:

    def test_prep_entry_runs_boundary(self, monkeypatch: pytest.MonkeyPatch):
        """备战入口接线锁:decide_prep_screen 到达任何决策前执行边界
        重置(armed 短路帧同样先过边界——接线位 = 入口最前;armed
        判定核桩化为单键替身,真 armed 判据不在本锁面)。"""
        import sr_od.application.currency_war.kernel.cw_launch_admission as admit_mod
        from sr_od.application.currency_war.kernel.cw_vocab import CwAction

        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    shop_screen='off')
        gs.node_hist_pos = (1, 2)
        monkeypatch.setattr(admit_mod, 'readiness_launch_decision',
                            lambda *a, **k: {'armed': True})
        strat = MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))
        st = state_of(gs)   # 构造 setter 已接线容器 → 同一状态对象
        st.shop_handled = (1, 1)   # 污染(上一节点残留态)
        action = strat.decide_prep_screen()
        assert isinstance(action, CwAction)
        assert st.shop_handled is None    # 备战入口已执行边界重置

    def test_shop_entry_runs_boundary(self):
        """商店入口接线锁:decide_shop_action 单动作核入口先过边界
        (生产单动作循环与 decide_shop_screen 驱动器共用本口)。"""
        from test.sr_od.application.currency_war._cw_helpers import DecideCfg

        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    shop_screen='on')
        gs.node_hist_pos = (1, 2)
        strat = MandateV1Strategy(
            gs, DecideCfg(), registry=DEFAULT_REGISTRY)
        st = state_of(gs)
        st.shop_handled = (1, 1)
        strat.decide_shop_action()
        assert st.shop_handled is None    # 商店入口已执行边界重置

    def test_both_entries_share_one_boundary_state(self):
        """两入口共用同一判重键(契约 C「同一函数」):备战入口已执行
        边界处理后,商店入口同节点号不重复执行(哨兵存活)。"""
        from test.sr_od.application.currency_war._cw_helpers import DecideCfg

        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    shop_screen='on')
        gs.node_hist_pos = (1, 2)
        handle_node_boundary(gs)   # 模拟备战入口已执行
        st = state_of(gs)
        st.shop_handled = (1, 2)   # 判重哨兵(同节点号残留)
        strat = MandateV1Strategy(
            gs, DecideCfg(), registry=DEFAULT_REGISTRY)
        strat.decide_shop_action()
        assert st.shop_handled == (1, 2)   # 同节点号:商店入口判重跳过

