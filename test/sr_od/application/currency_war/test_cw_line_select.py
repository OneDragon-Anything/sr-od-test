"""终局线选择(候选-锁定制)内核锁——迭代
2026-10-12-prep-shop-workflow-redesign 批 3.7。

出处 = line_and_upgrade §1.2-§1.4(判据唯一源):
- §1.2 线分数 = 字典序(环境分级 → 持有证据级 → 攻略热度,注册序终局)
  + 热度映射常量表(排序立场数据,落策略层);
- §1.3 top3 候选管理(每帧重算,签名幂等);
- §1.4 锁定双触发(硬规则查表:策略型 OR/角色型 AND——判定单一源 =
  知识卡原语;时点兜底 = plane2_started ∧ P2 投资策略选卡完成)+
  同帧多命中裁决(线分数最高 + 热度 tie-break + 注册序终局,禁遍历序)。

锁定写入/连带动作/键面归一(target_comp 终态单写者)的载体面锁在
test_cw_session_scope;本文件锁判据本体。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    line_select,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.session_scope import (
    refresh_line_if_needed,
    write_line_lock,
)

_REG_INDEX = {c.name: i for i, c in enumerate(COMP_LIBRARY)}


def _hold(sess: StrategySession, names: list[str]) -> None:
    """持有面种子(前 4 上场、其余备战;1★)。"""
    cw4_gs(sess, plane=1, round_num=2, node='prep',
           front_row=[Unit(char_id=n, star=1) for n in names[:4]],
           back_row=[], bench=[Unit(char_id=n, star=1)
                               for n in names[4:9]])


# ===== 热度映射常量表 =====


class TestHeatTable:
    def test_table_covers_all_lines_with_positive_counts(self):
        """热度表覆盖 COMP_LIBRARY 全 20 线且值 > 0(缺行 = 热度维
        最低的 fail 方向,生产不应触发;十类帖数全为正)。"""
        assert set(line_select.LINE_HEAT) == {c.name for c in COMP_LIBRARY}
        assert all(v > 0 for v in line_select.LINE_HEAT.values())

    def test_category_ordering_snapshot(self):
        """类级热度序快照(姬子 274 > 圣杯 118 > 银狼 68 > 黄泉 50 >
        万敌 40 = 长尾桶 40 > 希儿/白厄/大黑塔 38 > 绯英 25 > DOT 20);
        同类多线共享类帖数,长尾 8 线共享桶值 ~40。"""
        h = line_select.LINE_HEAT
        assert h['列车同行'] == 274
        assert h['命运圣杯红A'] == h['双王圣杯'] == 118
        assert h['DOT队'] == h['专家桑博DOT'] == 20
        assert h['千冶减益'] == h['巡海击破'] == h['龙丹战技点'] \
            == h['火花星间旅人'] == h['银枝群攻'] == h['昼神阿雅'] \
            == h['追击飞霄'] == h['景元仙舟'] == 40


# ===== 候选快照(top3;字典序) =====


class TestCandidates:
    def test_empty_state_top3_by_heat_then_registration(self):
        """零持有帧:环境/证据级全平 → 热度定序;共享热度(圣杯两线)
        终局裁定 = 注册序首线。"""
        got = line_select.compute_candidates(frozenset(), frozenset())
        assert got[:3] == ('列车同行', '命运圣杯红A', '双王圣杯')
        assert len(got) == 3

    def test_carry_outranks_skeleton_and_heat(self):
        """持有证据级字典序:CARRY 在手压过骨架计数与热度——持有
        低热度线的 CARRY(追击飞霄·飞霄,heat 40)胜过只囤骨架的
        高热度线。"""
        feixiao = next(c for c in COMP_LIBRARY if c.name == '追击飞霄')
        assert line_select.LINE_HEAT[feixiao.name] < line_select.LINE_HEAT['列车同行']
        # 飞霄在手 = 追击飞霄 CARRY 档(大头)→ 证据级首维压热度序
        got = line_select.compute_candidates(
            frozenset({'飞霄'}), frozenset())
        assert got[0] == '追击飞霄'

    def test_env_tier_outranks_hold_evidence(self):
        """环境分级 = 字典序首键:强关联策略命中线(策略型 lock_rules
        命中)即使零持有也压过持有证据最厚的未命中线。"""
        # 黑塔纪元 → 大黑塔银河学者(策略型关联)
        got = line_select.compute_candidates(
            frozenset(), frozenset({'黑塔纪元'}))
        assert got[0] == '大黑塔银河学者'

    def test_deterministic_and_idempotent(self):
        """同一持有面重复计算同值(签名幂等);未锁定帧快照 = 派生值。"""
        held = frozenset({'姬子·启行'})
        a = line_select.compute_candidates(held, frozenset())
        b = line_select.compute_candidates(held, frozenset())
        assert a == b == tuple(sorted(
            a, key=lambda n: (*line_select.line_score_key(
                next(c for c in COMP_LIBRARY if c.name == n),
                held, frozenset()), _REG_INDEX[n])))


# ===== 硬规则锁定(策略型/角色型;同帧多命中裁决) =====


class TestHardRules:
    def test_char_rule_locks_on_full_combo_and_not_partial(self):
        """角色型 = 关键角色组合全员在手(AND):专家桑博DOT 的
        ['桑博','卡芙卡','千冶·刃'] 三件齐 → 命中;缺一件 → 不命中。"""
        full = frozenset({'桑博', '卡芙卡', '千冶·刃'})
        partial = frozenset({'桑博', '卡芙卡'})
        hits_full = line_select.hard_lock_hit_lines(full, frozenset())
        hits_part = line_select.hard_lock_hit_lines(partial, frozenset())
        assert '专家桑博DOT' in hits_full
        assert '专家桑博DOT' not in hits_part

    def test_strategy_rule_locks_on_association(self):
        """策略型 = 强关联策略到手(OR):黑塔纪元 → 大黑塔银河学者。"""
        hits = line_select.hard_lock_hit_lines(frozenset(), frozenset({'黑塔纪元'}))
        assert '大黑塔银河学者' in hits

    def test_same_frame_multi_hit_adjudication(self):
        """同帧多命中裁决(§1.4 明文禁遍历序隐式定锁):两线硬规则
        同帧命中 → 取线分数最高者;分数同 → 热度;再同 → 注册序首线。

        构造:① 角色型命中 专家桑博DOT(热 20,无环境、无持有差)
        + 策略型命中 大黑塔银河学者(热 38)——环境分级首键使大黑塔
        (策略命中 = 最高级)胜出,即使其热度证据面被反超;
        ② 共享热度/同证据级的多命中按注册序(圣杯双线同热,角色型
        组合构造性难同帧,以线分数全序断言形态承载)。"""
        # ① 环境分级压持有证据:专家桑博DOT 持有全组(证据最厚),
        # 大黑塔仅策略命中(零持有)——环境级首键 → 大黑塔胜。
        held = frozenset({'桑博', '卡芙卡', '千冶·刃', '黑塔'})
        invest = frozenset({'黑塔纪元'})
        hits = line_select.hard_lock_hit_lines(held, invest)
        assert {'专家桑博DOT', '大黑塔银河学者'} <= set(hits)
        assert hits[0] == '大黑塔银河学者', (
            '环境分级(策略命中线)必须压过持有证据级——字典序首键')
        # ② 裁决与候选同一全序:命中线首名 = 全序排序首名(禁遍历序)。
        assert hits == tuple(sorted(
            hits, key=lambda n: (*line_select.line_score_key(
                next(c for c in COMP_LIBRARY if c.name == n),
                held, invest), _REG_INDEX[n])))


# ===== 时点兜底与 evaluate_lock 总序 =====


class TestFallbackAndEvaluate:
    def test_no_lock_before_trigger(self):
        """硬规则未命中 ∧ 时点未到(P1/未选卡)→ 不锁(None)。"""
        got = line_select.evaluate_lock(
            ('列车同行', '命运圣杯红A', '双王圣杯'),
            frozenset(), frozenset(),
            plane2_started=False, p2_strategy_pick_done=False)
        assert got is None

    def test_plane2_alone_not_enough(self):
        """plane2_started 但选卡未完成 → 不锁(P2 入口至兜底锁帧的
        短窗 = 未锁双轨期)。"""
        got = line_select.evaluate_lock(
            ('列车同行',), frozenset(), frozenset(),
            plane2_started=True, p2_strategy_pick_done=False)
        assert got is None

    def test_fallback_locks_top_candidate(self):
        """时点兜底触发 → 锁定 top3 中分数最高者(候选元组已按全序
        降序,取首 = 热度序的列车同行)。"""
        got = line_select.evaluate_lock(
            ('列车同行', '命运圣杯红A', '双王圣杯'),
            frozenset(), frozenset(),
            plane2_started=True, p2_strategy_pick_done=True)
        assert got == '列车同行'

    def test_hard_rule_beats_fallback_same_frame(self):
        """同帧硬规则与兜底齐备 → 硬规则线胜(先到先锁的判据序)。"""
        got = line_select.evaluate_lock(
            ('列车同行',), frozenset({'桑博', '卡芙卡', '千冶·刃'}),
            frozenset(),
            plane2_started=True, p2_strategy_pick_done=True)
        assert got == '专家桑博DOT'


# ===== 端到端:refresh 前置段驱动锁定 =====


class TestRefreshDrivesLock:
    def test_hard_rule_lock_on_refresh_frame(self):
        """硬规则命中帧经前置段直接写锁(锁定动作发生的域内立即生效,
        §3):target_comp 写入 + 候选清空 + 派生缓存同步。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        sess = StrategySession()
        _hold(sess, ['桑博', '卡芙卡', '千冶·刃'])
        gs = game_state_of(sess)
        st = state_of(gs)
        gs.node_hist_pos = (1, 2)
        refresh_line_if_needed(gs)
        assert st.target_comp is not None
        assert st.target_comp.name == '专家桑博DOT'
        assert st.line_candidates == ()
        ist = st.v3_intention
        assert ist.locked_comp == '专家桑博DOT'
        assert ist.phase == 'locked'
        # 锁后只读:下一帧(签名变化)重算不复位锁定
        _hold(sess, ['桑博', '卡芙卡', '千冶·刃', '姬子·启行'])
        refresh_line_if_needed(gs)
        assert st.target_comp.name == '专家桑博DOT'

    def test_p2_pick_completion_unlocks_fallback(self):
        """时点兜底端到端:进 P2(窗口谓词置位)首帧快照基线;投资
        策略获得(集合增长)帧 → 兜底锁 top1(零持有 → 热度序首线)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        sess = StrategySession()
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs = game_state_of(sess)
        gs.node_hist_pos = (2, 1)
        # 前置序组合:边界(置 plane2 标志)+ 刷新(快照基线)
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope,
        )
        session_scope.handle_node_boundary(gs)
        refresh_line_if_needed(gs)
        st = state_of(gs)
        assert st.p2_pick_baseline == frozenset()
        assert st.target_comp is None, '选卡未完成 → 不锁'
        # 投资策略获得 → 集合增长 → 完成旗标置位 → 兜底锁
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
        )
        gs.observe(gs.active_strategies, ['白银投资'],
                   evidence='cw-37-test',
                   sig=ChannelSig(family='obs', actor='cw-37-test',
                                  mode='read'))
        refresh_line_if_needed(gs)
        assert st.p2_strategy_pick_done is True
        assert st.target_comp is not None
        assert st.target_comp.name in {c.name for c in COMP_LIBRARY}
        assert st.target_comp.name == '列车同行', (
            '零持有兜底锁 top1 = 热度序首线')

    def test_write_lock_external_api_sets_slot(self):
        """写入 API 直锁(键面归一验收):write_line_lock = target_comp
        终态单写者;锁定后 ist 派生缓存/视图同帧一致。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        sess = StrategySession()
        gs = game_state_of(sess)
        write_line_lock(gs, '黄泉减益')
        st = state_of(gs)
        assert st.target_comp is not None
        assert st.target_comp.name == '黄泉减益'
        assert st.v3_intention.locked_comp == '黄泉减益'
