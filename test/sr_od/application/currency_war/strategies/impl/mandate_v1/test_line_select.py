"""终局线选择(统一阵容评分)内核测试——迭代
2026-11-03-unified-line-scoring 批 1;含选线决策族两翼
(过渡框架判定 + session 作用域载体)。

出处 = strategy-docs/12_line_and_intention.md §1.1-§1.3(判据唯一源)+
design.md §2(数量级表)/§6(锁定语义):
- §1.1 线分数 = 单值和(证据 carry/骨架/插件 + 热度 + 投资通道派生 +
  词缀〔含万敌燃料底线〕+ boss〔批 2 前恒 0〕;数量级常数单一源 =
  kernel/cw_line_scales);
- §1.2 top3 候选管理(每帧重算,签名幂等)+ 证据门(env∨carry∨骨架∨
  插件 > 0,不含热度);
- §1.3 锁定 = P2 时点兜底唯一路径(硬规则/即时锁全退役——P1 即锁
  行为消失为设计语义,sim 场景①)+ 空候选兜底分支;
- design §2 sim 不变量(正项上界 < |−100000|)与数值对照三场景。

分节组织(同文件三节):
- 判据本体(本文件主节):数量级对照 / 候选快照 / P1 无锁 / 时点兜底 /
  万敌燃料底线 / 正项上界自算 / 端到端;
- 配方伪阵容路由(decision_target):统一保护集迭代末阶段收口后,
  过渡框架判据族(pick_framework / transition_score / _framework_counts)
  已随 TRANSITION_PACK 策展符号退役(design §2.4:判据数据源 = 策展
  档位标签,符号删除后为死码),本节保留配方路由与配方形状判定;
- session 作用域载体(节点边界重置 / 窗口谓词 / 方向状态骨架 /
  商店会话标记与机会清单 / 双域接线):锁定写入与判重载体面。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_comp,
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    Comp,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_recipe import (
    decision_target,
    recipe_comp,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    line_select,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
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


# ===== 候选快照(top3;单值和排序) =====


class TestCandidates:
    def test_empty_state_top3_by_heat_then_registration(self):
        """零持有帧:证据/投资分量全 0 → 热度定序(每点 +1);共享热度
        (圣杯两线 118)终局裁定 = 注册序首线。"""
        got = line_select.compute_candidates(
            frozenset(), line_select.OpeningCtx())
        assert got[:3] == ('列车同行', '命运圣杯红A', '双王圣杯')
        assert len(got) == 3

    def test_carry_anchor_outranks_heat(self):
        """锚核心 +8000 压过热度序:持有低热度线的锚(追击飞霄·飞霄,
        heat 40)胜过零证据高热度线(列车同行 274)。"""
        feixiao = next(c for c in COMP_LIBRARY if c.name == '追击飞霄')
        assert line_select.LINE_HEAT[feixiao.name] < line_select.LINE_HEAT['列车同行']
        got = line_select.compute_candidates(
            frozenset({'飞霄'}), line_select.OpeningCtx())
        assert got[0] == '追击飞霄'

    def test_invest_channel_bonus_outranks_heat(self):
        """投资通道派生分量进线分:黑塔纪元(定义卡 +500)→ 大黑塔
        银河学者压过零信号热度首线(列车 274)。"""
        got = line_select.compute_candidates(
            frozenset(),
            line_select.OpeningCtx(held_invest=frozenset({'黑塔纪元'})))
        assert got[0] == '大黑塔银河学者'

    def test_deterministic_and_idempotent(self):
        """同一持有面重复计算同值(签名幂等);未锁定帧快照 = 派生值。"""
        held = frozenset({'姬子·启行'})
        ctx = line_select.OpeningCtx()
        a = line_select.compute_candidates(held, ctx)
        b = line_select.compute_candidates(held, ctx)
        assert a == b == tuple(sorted(
            a, key=lambda n: (-line_select.line_score_key(
                next(c for c in COMP_LIBRARY if c.name == n),
                held, ctx), _REG_INDEX[n])))


# ===== 数量级对照(design §2 三场景:层间/层内数量级锁) =====


class TestMagnitudeScenarios:
    """三对照场景(design §2「sim 数值对照场景」):①单 anchor vs 多非锚
    core ②4 骨架 vs 1 anchor ③热度满 vs 单插件。

    场景①数值语义申报:anchor +8000 vs 非锚 core +4000(减半)——多非锚
    core(花火+符玄+缇宝 = 12000)数值上仍高于单 anchor(8000);相对旧
    等权(24000 vs 8000 = 3:1 支配)修复为 3:2,单 anchor 独压任一非锚
    core、锚+任一 core 与 3 core 相平(12000 = 12000)。「无希儿的量子线
    不是量子线」的攻略语义由证据档位(锚不在手 = 该线证据起于 core 档)
    承载,数值支配关系以本组断言为准(已申报 design §2 场景①的
    「希儿胜」措辞与采纳常数的张力,处置归迭代方)。
    """

    def test_scenario_anchor_vs_multi_core(self):
        """①层内 carry 档:锚 8000 > 单非锚 core 4000;锚+1 core =
        3 非锚 core(相平点,design §2 表注「锚+任一辅助即胜/相平」)。"""
        seele = next(c for c in COMP_LIBRARY if c.name == '希儿量子')
        ctx = line_select.OpeningCtx()
        anchor_only = line_select.line_score_breakdown(
            seele, frozenset({'希儿'}), ctx).carry
        one_core = line_select.line_score_breakdown(
            seele, frozenset({'花火'}), ctx).carry
        anchor_plus_core = line_select.line_score_breakdown(
            seele, frozenset({'希儿', '花火'}), ctx).carry
        three_core = line_select.line_score_breakdown(
            seele, frozenset({'花火', '符玄', '缇宝'}), ctx).carry
        assert anchor_only > one_core
        assert anchor_plus_core == three_core

    def test_scenario_four_skeleton_equals_one_anchor(self):
        """②层间:4 骨架 = 1 anchor 相平(design §2 表相平点按 anchor
        档重校)——分项常数断言(跨线同帧构造等价持有面不可复现,
        常数关系即设计锁)。"""
        from sr_od.application.currency_war.kernel.cw_line_scales import (
            CARRY_ANCHOR,
            SKELETON_BONUS,
        )
        assert 4 * SKELETON_BONUS == CARRY_ANCHOR

    def test_scenario_heat_below_single_plugin(self):
        """③热度 < 1 插件(R4-2:持有实证 > 社区先验,与字典序行为
        一致):满热度 274 点 < 插件 500;行为面 = 零证据满热度线被
        证据门挡,单插件持有线(希儿量子·知更鸟 = shared 插件)入选。"""
        from sr_od.application.currency_war.kernel.cw_line_scales import (
            PLUGIN_BONUS,
        )
        ctx = line_select.OpeningCtx()
        assert max(line_select.LINE_HEAT.values()) < PLUGIN_BONUS
        got = line_select.compute_candidates(
            frozenset({'知更鸟'}), ctx, evidence_gate=True)
        assert '希儿量子' in got, '插件证据点亮(热度不作入选理由)'
        assert '列车同行' not in got, '零证据满热度线被证据门挡'


# ===== 证据门(12 号篇 §1.2 候选入选证据门) =====


class TestEvidenceGate:
    """证据门参数(候选快照消费开启版;缺省关闭 = 全量口径):

    - 线入选 ⟺ 证据门分量为正(投资通道 ∨ carry ∨ 骨架 ∨ 插件——命名
      分量访问 :attr:`LineScore.gate_positive`,**不含热度**);
    - 零证据线不入候选——热度只作有证据线间的排序,不再是入选理由;
    - 开局零持有零投资 = 空候选(合法形态;时点兜底空候选分支承接)。
    """

    def test_zero_evidence_yields_empty_candidates(self):
        """零持有零投资 → 空候选(开局「无阵容入选」;缺省版对照 =
        热度前三常驻,TestCandidates.test_empty_state 辖)。"""
        assert line_select.compute_candidates(
            frozenset(), line_select.OpeningCtx(), evidence_gate=True) == ()

    def test_carry_evidence_lights_line(self):
        """锚在手点亮该线(证据 carry 层):飞霄 = 追击飞霄锚
        (LINE_ANCHOR)——唯一证据线即唯一候选。"""
        got = line_select.compute_candidates(
            frozenset({'飞霄'}), line_select.OpeningCtx(), evidence_gate=True)
        assert got == ('追击飞霄',)

    def test_skeleton_evidence_lights_line(self):
        """骨架件持有(≥1)点亮该线:key_items 成员在手 = 骨架分量非零
        (carry 层零也入选)。"""
        from sr_od.application.currency_war.kernel.cw_comps import (
            carry_set,
        )
        comp = next(c for c in COMP_LIBRARY
                    if c.key_items
                    and any(n not in carry_set(c) for n in c.key_items))
        skel = next(n for n in comp.key_items if n not in carry_set(comp))
        got = line_select.compute_candidates(
            frozenset({skel}), line_select.OpeningCtx(), evidence_gate=True)
        assert comp.name in got, (
            f'骨架件 {skel} 在手须点亮 {comp.name}(骨架分量)')

    def test_invest_channel_evidence_lights_line(self):
        """投资通道命中(定义卡)点亮该线——零持有也入选。"""
        got = line_select.compute_candidates(
            frozenset(),
            line_select.OpeningCtx(held_invest=frozenset({'黑塔纪元'})),
            evidence_gate=True)
        assert '大黑塔银河学者' in got

    def test_negative_affix_component_not_in_gate(self):
        """词缀分量为负不点亮证据门(门分量集显式定义:env∨carry∨骨架∨
        插件——词缀/boss 不在门内):万敌无燃料局词缀分 −100000,
        零持有零投资时仍空候选。"""
        got = line_select.compute_candidates(
            frozenset(),
            line_select.OpeningCtx(
                enemy_affixes=('永久创伤', '净化身心')),
            evidence_gate=True)
        assert got == ()

    def test_heat_ranks_only_within_evidenced_lines(self):
        """热度降为有证据线间的排序:候选 ⊆ 证据点亮线域且按线分全序;
        零证据高热度线(命运圣杯红A 118 > 追击飞霄 40)不入——热度不再
        是入选理由。姬子·启行跨线点亮(反甲白厄/列车同行)为注册表事实,
        点亮域按现算取。"""
        held = frozenset({'姬子·启行', '飞霄'})
        ctx = line_select.OpeningCtx()
        got = line_select.compute_candidates(held, ctx, evidence_gate=True)
        lit = {c.name for c in COMP_LIBRARY
               if line_select.line_score_breakdown(
                   c, held, ctx).gate_positive}
        assert lit and set(got) <= lit, '候选 ⊆ 证据点亮线域'
        assert '命运圣杯红A' not in got, '零证据高热度线不入'
        order = sorted(lit, key=lambda n: (
            -line_select.line_score_key(
                next(c for c in COMP_LIBRARY if c.name == n),
                held, ctx), _REG_INDEX[n]))
        assert list(got) == order[:line_select.CANDIDATE_TOP_N], \
            '候选序 = 全序在点亮域上的受限投影'

    def test_default_off_keeps_full_ranking(self):
        """缺省关闭 = 全量版(虚拟评估/资格器消费口径):零证据帧
        仍返回热度前三。"""
        assert line_select.compute_candidates(
            frozenset(), line_select.OpeningCtx()) \
            == ('列车同行', '命运圣杯红A', '双王圣杯')


# ===== 万敌燃料底线(design §4;词缀分量;sim 场景③) =====


class TestWandiFuelBottom:
    def test_no_fuel_line_bottom_despite_full_evidence(self):
        """万敌无燃料局垫底:开局词缀 ∩ 燃料集 = 空 → −100000,满证据
        (锚+全 core 24040)线分为负、全序垫底(20 线排序末位)且被挤出
        top3——数值排他非布尔特判;有燃料对照(正当防卫 +900)回到
        榜首区。"""
        wandi = next(c for c in COMP_LIBRARY if c.name == '万敌单C')
        full_ev = frozenset(wandi.core_chars) | {'万敌'}
        no_fuel_ctx = line_select.OpeningCtx(
            enemy_affixes=('净化身心', '风之熄火', '沉重脚步', '皮糙肉厚'))
        got = line_select.compute_candidates(full_ev, no_fuel_ctx)
        assert '万敌单C' not in got, '无燃料局被挤出 top3(数值排他)'
        full_rank = sorted(
            COMP_LIBRARY,
            key=lambda c: line_select._line_sort_key(c, full_ev, no_fuel_ctx))
        assert full_rank[-1].name == '万敌单C', '全序垫底(sim 场景③)'
        assert line_select.line_score_key(wandi, full_ev, no_fuel_ctx) < 0
        fuel_ctx = line_select.OpeningCtx(enemy_affixes=('正当防卫',))
        assert line_select.line_score_key(wandi, full_ev, fuel_ctx) \
            > line_select.line_score_key(wandi, full_ev, no_fuel_ctx)


# ===== P1 无锁(硬规则/即时锁全退役;sim 场景①) =====


class TestHardLocksRetired:
    def test_full_char_combo_p1_does_not_lock(self):
        """角色硬锁废:旧角色型全组在手(专家桑博DOT 三件)P1 帧不锁
        ——核心在手 = carry 证据分(数值必然性替代),锁定唯一路径 =
        P2 时点兜底。"""
        sess = StrategySession()
        _hold(sess, ['桑博', '卡芙卡', '千冶·刃'])
        gs = game_state_of(sess)
        gs.node_hist_pos = (1, 2)
        refresh_line_if_needed(gs)
        st = state_of(gs)
        assert st.target_comp is None, 'P1 即锁行为消失(design §6)'

    def test_defining_strategy_p1_does_not_lock(self):
        """策略即时锁废:黑塔纪元(旧策略型硬锁触发)P1 帧不锁——
        定义卡 +500 进线分,锁定走时点兜底;候选排序照常被加分驱动。"""
        sess = StrategySession()
        gs = game_state_of(sess)
        gs.node_hist_pos = (1, 2)
        gs.observe(gs.active_strategies, ['黑塔纪元'], evidence='t',
                   sig=ChannelSig(family='obs', actor='cw-test', mode='read'))
        refresh_line_if_needed(gs)
        st = state_of(gs)
        assert st.target_comp is None
        assert st.line_candidates[0] == '大黑塔银河学者', \
            '定义卡加分照常进候选排序(分数说话)'


# ===== 时点兜底与 evaluate_lock 总序 =====


class TestFallbackAndEvaluate:
    _CTX = line_select.OpeningCtx()

    def test_no_lock_before_trigger(self):
        """时点未到(P1/未选卡)→ 不锁(None)。"""
        got = line_select.evaluate_lock(
            ('列车同行', '命运圣杯红A', '双王圣杯'),
            frozenset(), self._CTX,
            plane2_started=False, p2_strategy_pick_done=False)
        assert got is None

    def test_plane2_alone_not_enough(self):
        """plane2_started 但选卡未完成 → 不锁(P2 入口至兜底锁帧的
        短窗 = 未锁双轨期)。"""
        got = line_select.evaluate_lock(
            ('列车同行',), frozenset(), self._CTX,
            plane2_started=True, p2_strategy_pick_done=False)
        assert got is None

    def test_fallback_locks_top_candidate(self):
        """时点兜底触发 → 锁定 top3 中分数最高者(候选元组已按全序
        降序,取首 = 热度序的列车同行)。"""
        got = line_select.evaluate_lock(
            ('列车同行', '命运圣杯红A', '双王圣杯'),
            frozenset(), self._CTX,
            plane2_started=True, p2_strategy_pick_done=True)
        assert got == '列车同行'

    def test_fallback_full_recompute_head_is_evidence_top(self):
        """空候选分支的真重算:空候选 + 持有面非空 → 锁全量重算首名
        (证据最厚线,非热度首线)。"""
        got = line_select.evaluate_lock(
            (), frozenset({'桑博', '卡芙卡', '千冶·刃'}), self._CTX,
            plane2_started=True, p2_strategy_pick_done=True)
        assert got == '专家桑博DOT'

    def test_fallback_empty_candidates_locks_full_order_head(self):
        """时点兜底空候选分支(12 号篇 §1.3:证据门下空候选可达,
        兜底为真规则):候选空且零持有 → 锁全 20 线全序首名——零证据帧
        全序首名 = 热度首线(全序的退化情形);触发前置不满足时仍不锁。"""
        got = line_select.evaluate_lock(
            (), frozenset(), self._CTX,
            plane2_started=True, p2_strategy_pick_done=True)
        assert got == '列车同行'
        got2 = line_select.evaluate_lock(
            (), frozenset(), self._CTX,
            plane2_started=True, p2_strategy_pick_done=False)
        assert got2 is None


# ===== 正项上界自算(design §2 sim 不变量;批 1 锁常数) =====


def test_positive_terms_upper_bound_below_restart_magnitude():
    """正项上界不变量(design §2/R4-1):任一线「全员持有 + 全投资持有
    (83 环境∪335 策略,放宽上界假设——不变量只要求任何构局追不上
    重开级)+ 开局词缀正项 top4 + 满热度」的正项和 < |−100000|。
    重开级单条即数值排他;上界值随常数表演进自动重算(本断言 = 锁)。"""
    from sr_od.application.currency_war.kernel.cw_affinity_table import (
        affix_row_of,
    )
    from sr_od.application.currency_war.kernel.cw_invest_channels import (
        env_line_bonus,
        strategy_line_bonus,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_ENVS,
        INVESTMENT_STRATEGIES,
    )
    from sr_od.application.currency_war.kernel.cw_line_scales import (
        RESTART_PENALTY,
    )
    worst = ('', 0)
    for comp in COMP_LIBRARY:
        held_all = frozenset(comp.core_chars) \
            | set(comp.shared_chars or ()) | set(comp.key_items or ())
        bd = line_select.line_score_breakdown(
            comp, held_all, line_select.OpeningCtx())
        invest_max = sum(
            max(env_line_bonus(n, comp), 0) for n in INVESTMENT_ENVS) \
            + sum(max(strategy_line_bonus(n, comp), 0)
                  for n in INVESTMENT_STRATEGIES)
        affix_max = sum(sorted(
            (s.score for s in affix_row_of(comp.name).values()
             if s.score > 0), reverse=True)[:4])
        total = bd.carry + bd.skeleton + bd.plugin + bd.heat \
            + invest_max + affix_max
        if total > worst[1]:
            worst = (comp.name, total)
    assert worst[1] < abs(RESTART_PENALTY), (
        f'正项上界越界:{worst}(design §2 不变量 < 100000)')


# ===== 端到端:refresh 前置段驱动锁定 =====


class TestRefreshDrivesLock:
    def test_p1_full_combo_waits_until_p2_fallback(self):
        """端到端(P1 即锁消失 + 时点兜底,sim 场景①):P1 持旧角色硬锁
        全组不锁;进 P2 且首笔策略获得帧 → 兜底锁证据首名(target_comp
        写入 + 候选清空 + 派生缓存同步)。"""
        sess = StrategySession()
        _hold(sess, ['桑博', '卡芙卡', '千冶·刃'])
        gs = game_state_of(sess)
        st = state_of(gs)
        gs.node_hist_pos = (1, 2)
        refresh_line_if_needed(gs)
        assert st.target_comp is None, 'P1 不锁(硬锁退役)'
        # 进 P2 + 首笔策略获得(滑动基线增长)→ 兜底锁
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs.node_hist_pos = (2, 1)
        handle_node_boundary(gs)
        gs.observe(gs.active_strategies, ['白银投资'], evidence='t',
                   sig=ChannelSig(family='obs', actor='cw-37-test',
                                  mode='read'))
        refresh_line_if_needed(gs)
        assert st.target_comp is not None
        assert st.target_comp.name == '专家桑博DOT', \
            '兜底锁 = 证据门版候选首名(全组证据最厚线)'
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


# ===== review-37 修复测试(P1 过期配方读口 / R2 滑动基线)=====


class TestP2WindowRecipeRetirement:
    """进 P2 后开局面配方键退役(review-37 P1):P2 未锁窗
    direction 读口 = None(两键都空契约),过期 P1 配方禁消费。"""

    @staticmethod
    def _strategy(gs):
        from types import SimpleNamespace

        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        return MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))

    def test_p2_entry_clears_recipe_and_direction_reads_none(self):
        """端到端:P1 帧配方物化(过渡候选槽首位物化)→ 进 P2(窗口谓词
        置位)首个贵段清配方锁 + 开局面键/过渡候选槽同点清空 → 未锁窗
        direction_comp_of 返回 None——shop 序 1 未锁分支/k 空窗回退/
        形态⑥观测的消费输入面统一恢复(review-37 P1 三消费端)。

        无羁绊开局新语义(12 号篇 §3):空板面(无羁绊
        开局)→ 过渡候选空 → 物化 **None**(旧制种 p1_pair 即物化的形态
        随 3.1 物化源切槽消亡)→ K 空窗回退承接——「P1 空窗期恒有方向」
        只对有羁绊开局成立,无羁绊开局 = 冷启动臂域(11 号稿 §1)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope,
        )
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=9, node='prep')
        gs.node_hist_pos = (1, 9)
        strat = self._strategy(gs)
        st = state_of(gs)
        from sr_od.application.currency_war.kernel.cw_intention import (
            IntentionState,
        )
        st.v3_intention = IntentionState()
        # 空板面:配方链贵段重算 → 过渡候选空 → 物化 None(§2.6-12)
        strat._refresh_direction(gs, st)
        assert st.transition_candidates == (), '无羁绊开局候选空(§2.3-2)'
        assert st.opening_recipe_comp is None, \
            '空板面候选空 → 物化 None(§2.6-12 新语义)'
        assert session_scope.direction_comp_of(gs) is None, \
            '空板面无方向 → K 空窗回退域(冷启动臂承接,§2.3-8)'
        # 有羁绊开局对照:槽非空 → 物化 = 候选首位伪阵容(便宜段物化链)
        st.transition_candidates = (('仙舟', '持续伤害'),)
        strat._refresh_direction_views(gs, st)
        assert st.opening_recipe_comp is not None, '槽首位物化前置'
        assert session_scope.direction_comp_of(gs) is st.opening_recipe_comp
        # 进 P2:边界置窗口谓词 + 贵段清配方(写端)+ 读口守卫(双保险)
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs.node_hist_pos = (2, 1)
        session_scope.handle_node_boundary(gs)
        strat._refresh_direction(gs, st)
        assert st.v3_intention.p1_pair == (), '配方锁退场'
        assert st.opening_recipe_comp is None, '开局面键同点清空(写端)'
        assert st.transition_candidates == (), '过渡候选槽同点清空'
        assert st.target_comp is None, '未锁窗(P2 首帧未选卡)'
        assert session_scope.direction_comp_of(gs) is None, (
            'P2 未锁窗 direction 读口 = None(两键都空契约)')
        # K 空窗回退 p2plus 带可达性(k=None 判定不再被过期配方遮蔽)
        from sr_od.application.currency_war.kernel.cw_intention import (
            k_empty_window_fallback,
        )
        fallback, band = k_empty_window_fallback(gs, st.v3_intention,
                                                 session=sess)
        assert band == 'p2plus', '未锁 P2 帧回退带 = p2plus(可达)'

    def test_direction_read_guard_against_stale_recipe(self):
        """防御双保险:清空写端未及执行的帧(plane2 首帧先于贵段),
        读口 plane2_started 守卫仍不消费过期 P1 配方。"""
        from sr_od.application.currency_war.kernel.cw_comps import get_comp
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope,
        )
        sess = StrategySession()
        gs = game_state_of(sess)
        st = state_of(gs)
        st.plane2_started = True          # 窗口谓词已置位
        st.opening_recipe_comp = get_comp('列车同行')   # 过期残留(哨兵)
        st.target_comp = None             # 未锁
        assert session_scope.direction_comp_of(gs) is None


class TestP2PickBaselineSliding:
    """P1 滑动基线(review-37 R2):P2 首帧快照会把先于首决策帧完成的
    开局三选一吞进基线(兜底退化为第二笔获得帧);滑动基线以 P1 末次
    刷新快照冻结,首笔 P2 获得照常侦测。"""

    @staticmethod
    def _observe_strategies(gs, names):
        from sr_od.application.currency_war.kernel.cw_game_state import (
            ChannelSig,
        )
        gs.observe(gs.active_strategies, names, evidence='cw-37-rev',
                   sig=ChannelSig(family='obs', actor='cw-37-rev',
                                  mode='read'))

    def test_p1_acquisition_in_baseline_no_false_trigger(self):
        """P1 期间获得的策略(加场卡)入滑动基线:进 P2 首帧不误触发
        兜底(该笔不是 P2 获得)。"""
        from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
            session_scope,
        )
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=5, node='prep')
        gs.node_hist_pos = (1, 5)
        self._observe_strategies(gs, ['白银投资'])
        refresh_line_if_needed(gs)
        st = state_of(gs)
        assert st.p2_pick_baseline == frozenset({'白银投资'})
        # 进 P2:策略集未变(该笔已在基线)→ 无增长 → 不触发
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs.node_hist_pos = (2, 1)
        session_scope.handle_node_boundary(gs)
        refresh_line_if_needed(gs)
        assert st.p2_strategy_pick_done is False, 'P1 获得不计 P2 增长'
        assert st.target_comp is None

    def test_p2_pick_before_first_decision_frame_detected(self):
        """吞签退化形态的消解锁:P2 开局三选一先于首个 P2 决策帧完成
        ——滑动基线(P1 末次刷新快照)使该笔在首个 P2 决策帧即被侦测
        为增长,兜底锁当帧触发(不退化到第二笔获得)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=9, node='prep')
        gs.node_hist_pos = (1, 9)
        refresh_line_if_needed(gs)
        st = state_of(gs)
        assert st.p2_pick_baseline == frozenset()
        # 进 P2:开局选卡(获得先于任何 P2 决策帧)→ 首个 P2 决策帧侦测
        cw4_gs(sess, plane=2, round_num=1, node='prep')
        gs.node_hist_pos = (2, 1)
        handle_node_boundary(gs)
        self._observe_strategies(gs, ['黑塔纪元'])
        refresh_line_if_needed(gs)
        assert st.p2_strategy_pick_done is True, (
            '先于首决策帧的 P2 首笔获得须被滑动基线侦测(吞签形态消解)')
        # 黑塔纪元(定义卡 +500)→ 大黑塔银河学者线分居首 → 兜底锁首名
        assert st.target_comp is not None
        assert st.target_comp.name == '大黑塔银河学者'


# ===== 定义卡缺位线靠证据分入选(sim 场景④)+ 签名词缀分量 =====


class TestDefiningCardAbsence:
    def test_line_enters_via_evidence_without_defining_card(self):
        """定义卡缺位线靠证据分入选(design §6 sim 场景④「定义卡缺位
        线靠证据分入选」):不持黑塔纪元,仅持大黑塔+黑塔(锚 8000 +
        core 4000)→ 证据门候选含大黑塔银河学者且居首——定义卡只是
        加分通道之一,缺位不挡线。"""
        got = line_select.compute_candidates(
            frozenset({'大黑塔', '黑塔'}), line_select.OpeningCtx(),
            evidence_gate=True)
        assert got[0] == '大黑塔银河学者'


class TestSignatureAffixDimension:
    def test_affix_observation_triggers_recompute(self):
        """签名多维性(词缀/boss 分量,design §6):同持有/同节点号,
        词缀观察写入(简报转正帧形态)→ 签名变化 → 重算——防候选消费
        静默旧值。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        gs.node_hist_pos = (1, 2)
        st = state_of(gs)
        refresh_line_if_needed(gs)
        st.line_candidates = ('sentinel',)
        # 仅词缀变化(持有/节点号/投资面不变)
        gs.observe(gs.enemy_affixes, ['正当防卫', '忍无可忍'],
                   evidence='t',
                   sig=ChannelSig(family='obs', actor='cw-test', mode='read'))
        refresh_line_if_needed(gs)
        assert st.line_candidates != ('sentinel',), \
            '词缀入签名:观察写入必须触发重算'
        # boss 分量同判(plane_bosses 写入)
        st.line_candidates = ('sentinel2',)
        gs.observe(gs.plane_bosses, ['灰手生命科技', None, None],
                   evidence='t',
                   sig=ChannelSig(family='obs', actor='cw-test', mode='read'))
        refresh_line_if_needed(gs)
        assert st.line_candidates != ('sentinel2',), \
            'boss 入签名:观察写入必须触发重算'


# ============================================================ 配方伪阵容路由
# (decision_target;过渡框架判据族 pick_framework/transition_score/
#  _framework_counts 已随 TRANSITION_PACK 策展符号退役——判据数据源 =
#  策展档位标签,符号删除后为死码,随符号删除;统一保护集迭代
#  changes/2026-10-15-unified-protection-set design.md §2.4。)


def _fw_sig() -> ChannelSig:
    """渠道①签名(obs 族;观察写入口签名必填)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _fw_gs(*, plane: int = 1) -> GameState:
    """容器:缺省未观察节点(plane_of 缺省 1);plane=2 写节点键。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if plane != 1:
        gs.observe(gs.node, NodeKey(plane=plane, round_num=1, kind='prep'),
                   sig=_fw_sig())
    return gs


def _fw_target_comp() -> Comp:
    """终局哨兵线(合成 Comp,身份断言用;值域无关)。"""
    return Comp(name='测试·终局哨兵', core_chars=['飞霄'],
                form_tiers={'追击': 3})


def _fw_session(framework: str, target_comp: Comp | None) -> StrategySession:
    """策略状态桩:transition_framework/target_comp 黑盒引用
    (decision_target 两读口);锁定线槽非空 = 锁定态,None = 未锁。"""
    st = SimpleNamespace(transition_framework=framework,
                         target_comp=target_comp)
    s = StrategySession()
    s.strategy_state = st
    return s


def test_decision_target_recipe_in_dual_track() -> None:
    """双轨期(未锁定)目标线 = 配方伪 comp(单一入口,消费方零改动):
    committed=False(锁定线槽空)→ transition_framework='仙舟' →
    recipe_comp('仙舟') 同一对象;配方形状即消费契约——仙舟键面含
    持续伤害(deploy 围栏视图键面补全,cw_recipe._RECIPES 注),
    爻光必后台(站位规则住 comp,漏了落 position_pref 兜底),
    form_tiers = 3 仙舟主羁绊档。framework='' 且未锁 → None(散件口径);
    策略状态未装配(裸 session,None-safe)→ None。
    """
    rc = recipe_comp('仙舟')
    got = decision_target(_fw_session('仙舟', None), _fw_gs())
    assert got is rc
    assert got.name == '过渡·仙舟配方'
    assert got.factions == ['仙舟'], \
        'factions = form_tiers 键派生(核心语义;持续伤害是弹性面非核心)'
    assert got.form_tiers == {'仙舟': 3}
    assert got.char_positions == {'爻光': 'back'}
    assert decision_target(_fw_session('', None), _fw_gs()) is None
    assert decision_target(StrategySession(), _fw_gs()) is None


def test_decision_target_committed_returns_terminal_line() -> None:
    """定型权威压过配方路由 → 终局 comp:锁定线槽非空(committed,
    候选-锁定制语义——P1 硬规则锁定与 P2 时点兜底统一承载)→ 返回
    target_comp 本体;P2 未锁短窗(双轨期口径):committed=False,
    配方路由照走。"""
    sentinel = _fw_target_comp()
    assert decision_target(_fw_session('仙舟', sentinel),
                           _fw_gs(plane=1)) is sentinel
    assert decision_target(_fw_session('仙舟', None),
                           _fw_gs(plane=2)).name == '过渡·仙舟配方'


# ============================================================ session 作用域载体
# (节点边界重置 / 窗口谓词 / 方向状态骨架 / 商店会话标记与机会清单 /
#  双域接线;判据本体 = 本文件主节。节点号驱动 = 直赋 ``gs.node_hist_pos``
#  〔生效序位的单调水位分量,生产写端 = advance_node_effective〕。)


def _sess_with_node(plane: int, round_num: int):
    """裸容器 + 生效节点号直种(node_hist_pos 水位分量驱动)。"""
    sess = StrategySession()
    gs = game_state_of(sess)
    gs.node_hist_pos = (plane, round_num)
    return sess, gs


class TestNodeBoundaryReset:

    def test_boundary_resets_registered_keys_then_dedupes(self):
        """清单重置键在节点号变化时按表复位;同节点号重复调用不
        重复执行(哨兵存活 = 判重跳过);节点号再变 → 再次执行。"""
        sess, gs = _sess_with_node(1, 2)
        st = state_of(gs)
        st.shop_handled = (1, 1)
        st.shop_opportunities = (ShopOpportunity(
            card_name='x', blocked_by='bench_full', price=1,
            order_class='seq1'),)
        st.line_eval_signature = ('stale',)
        handle_node_boundary(gs)
        assert st.shop_handled is None          # ①标记清值
        assert st.shop_opportunities == ()      # ②清单清空
        assert st.line_eval_signature is None   # ③签名置失效
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
        """清单第 5 项负登记:方向状态(锁定线槽 target_comp/配方键)
        跨节点保留——节点边界不清方向,契约 C(键面归一:锁定线槽 =
        target_comp);候选快照键边界亦不辖(锁定写入时已被清空,手工
        哨兵 = 模拟外部写入后边界不复位);签名置失效(第 4 项)与之
        同帧对照,校验分界本身。"""
        sess, gs = _sess_with_node(1, 2)
        st = state_of(gs)
        comp = cw4_comp()
        write_line_lock(gs, comp.name)
        st.line_candidates = ('external-write',)
        st.opening_recipe_comp = comp
        gs.node_hist_pos = (1, 5)
        handle_node_boundary(gs)
        assert st.target_comp is comp           # 锁定跨节点保留(锁定线槽)
        assert st.line_candidates == ('external-write',)
        assert st.opening_recipe_comp is comp
        assert st.line_eval_signature is None     # 签名置失效(对照)


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
        # 签名变化(节点号推进)→ 重算发生(哨兵被覆写为证据门版候选——
        # 零持有帧证据门下 = 空候选,12 号篇 §1.2:
        # 热度不再是入选理由)
        gs.node_hist_pos = (1, 3)
        refresh_line_if_needed(gs)
        assert st.line_candidates == (), \
            '零持有帧证据门版候选空(哨兵被覆写 = 重算发生)'
        assert st.target_comp is None         # 无硬规则/未到时点 → 未锁

    def test_level_dimension_change_triggers_recompute(self):
        """等级维独立触发重算(签名多维性):同持有/同节点号、仅等级变化
        → 签名变化 → 重算。等级入签名的动机 = 店内整级购买经验后概率表
        变,消费旧等级 = 评估陈旧(line_and_upgrade §3 步骤 1)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep', level=3)
        st = state_of(gs)
        refresh_line_if_needed(gs)
        st.line_candidates = ('sentinel',)
        # 仅等级变化(持有/节点号/装备/投资集不变)
        cw4_gs(sess, plane=1, round_num=2, node='prep', level=4)
        refresh_line_if_needed(gs)
        assert st.line_candidates != ('sentinel',)

    def test_recompute_respects_lock_slot_and_view(self):
        """键面归一测试:target_comp = 锁定线槽(终态单写者 =
        write_line_lock)——锁定态下重算不覆写配方键/候选停算;未锁定
        视图 = 空名单 + 未锁定旗标(候选快照另由真内核产出,主题测试 =
        本文件判据本体节)。"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        st = state_of(gs)
        comp = cw4_comp()
        write_line_lock(gs, comp.name)
        st.opening_recipe_comp = comp   # 外部哨兵:锁定态重算不辖配方键
        refresh_line_if_needed(gs)
        assert st.opening_recipe_comp is comp   # 重算零写(配方链写端在 flow)
        view = line_members_view(gs)
        assert view.locked is True
        assert view.comp_name == comp.name
        # 未锁定视图(独立局):空名单 + 未锁定旗标
        sess2 = StrategySession()
        gs2 = cw4_gs(sess2, plane=1, round_num=2, node='prep')
        refresh_line_if_needed(gs2)
        view2 = line_members_view(gs2)
        assert view2.locked is False
        assert view2.comp_name is None
        assert view2.members == ()


class TestLineLockSkeleton:

    def test_write_lock_side_effects_and_readonly(self):
        """锁定写入联动两件(清商店标记/候选快照清空并停算)
        + 锁后只读(重复写入不改锁定线)。
        (旧预授权键连带清键随 2026-10-17 迭代 T-4 键退役删除。)"""
        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep')
        st = state_of(gs)
        comp = cw4_comp()
        st.shop_handled = (1, 2)
        st.line_candidates = ('候选态',)   # 锁定前的非空候选态
        write_line_lock(gs, comp.name)
        assert st.target_comp is comp           # 锁定线槽写入(解析产物)
        assert st.shop_handled is None      # ①清商店会话标记
        assert st.line_candidates == ()     # ②候选快照清空
        # 停算:签名变化后重算不再写入快照(恒空)
        gs.node_hist_pos = (1, 3)
        refresh_line_if_needed(gs)
        assert st.line_candidates == ()
        assert st.target_comp is comp       # 锁后只读(重算不复位锁定)
        # 锁后只读:重复写入/未注册名写入均不改锁定线
        write_line_lock(gs, '其他线名')
        assert st.target_comp is comp
        # 派生缓存同步:ist.locked_comp/phase 同帧生效
        ist = getattr(st, 'v3_intention', None)
        assert ist is not None and ist.locked_comp == comp.name
        assert ist.phase == 'locked'

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


class TestEntryWiring:

    def test_prep_entry_runs_boundary(self, monkeypatch: pytest.MonkeyPatch):
        """备战入口接线测试:decide_prep_screen 到达任何决策前执行边界
        重置(armed 短路帧同样先过边界——接线位 = 入口最前;armed
        判定核桩化为单键替身,真 armed 判据不在本测试面)。"""
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
        """商店入口接线测试:decide_shop_action 单动作核入口先过边界
        (生产单动作循环与 decide_shop_screen 驱动器共用本口)。"""
        from test.sr_od.application.currency_war._cw_helpers import DecideCfg

        sess = StrategySession()
        gs = cw4_gs(sess, plane=1, round_num=2, node='prep',
                    shop_screen='on')
        gs.node_hist_pos = (1, 2)
        strat = MandateV1Strategy(
            gs, DecideCfg(), registry=DEFAULT_REGISTRY)
        st = state_of(gs)
        st.node_boundary_last_pos = None   # 边界未处理形态(种子稳态钉位解除)
        st.shop_handled = (1, 1)
        strat.decide_shop_action()
        # 边界已执行:判重键推进到当前节点(重置后若会话零动作收工,
        # 标记由会话收工位重写——此处校验边界执行本身,不断言收工位零标记)。
        assert st.node_boundary_last_pos == (1, 2)
        assert st.shop_handled in (None, (1, 2))

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
