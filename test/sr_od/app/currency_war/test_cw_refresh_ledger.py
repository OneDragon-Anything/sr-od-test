"""T-88 决策环数据流断链修复 · 缺陷①回归锁(刷新通道整局失能)。

病理(ADR-0571):``_r1_ledger_terms`` 旧实现「任一成员该级不可追 ⇒
共享累加器 ``e_sum = inf`` 且无复位」把非空合格集污染成「无可追」,
R1 刷新门以 ``no_chaseable_member`` 结构性恒关——实机局
g_20260907_021326:P1 全部 9 个刷新评估帧 0 刷店
(``shop_r1_no_chaseable_member=9`` 精确对账)。

修复语义 = 不可追成员剔出本级合格集(continue),``inf`` 仅由「合格
集空」承载(成员集空 / 全部 2★ 成型 / 该级全不可追)——与函数
docstring 返回契约、``r1_commitment_account`` 边界注释、兄弟实现
``r2_card_reserve`` 的 continue 过滤三方对齐。

红证(修复前亲跑,code_commit=1e7d9a33 工作树):真注册表体系对全集
15 名(含 lv3-6 不可追的 5 费景元/黑天鹅)直调 ``_r1_ledger_terms``,
lv3-6 得 ``(inf, 21/42/78/78)``——账为无穷同时卡费为正,即「部分不可
追被错判全空」;p1r8 档案帧全链 ``decide_shop_screen`` 得
``shop_r1_no_chaseable_member=1`` 且零动作。

锁依据 = ``_r1_ledger_terms`` docstring 合格集契约 + ``r1_commitment_
account`` 边界注释(P40 R0-1「合格集空 ⇒ EV 恒负」刷新侧特例)。
改锁先重推语义:本锁钉的是「**部分**不可追 ≠ 合格集空」,与 R0-1
同源;禁为保绿机械跟绿。

覆盖对账(2026-09-08 瘦身批,亲读两处断言面):``r1_commitment_account``
纯数面真值表(within/over/non-finite 含 NaN/零负预算四臂)由判据主题
文件 test_cw_vgap_frame_horizon.py::TestCriterionAffordability 承载,
本文件原 TestR1CommitmentAccountBoundary 三测为其真子集已删;混合集
过滤「部分不可追 ≠ 合格集空」的精确卡费面由同文件
TestMixedPeakCompletionAccount lv6 臂承载(超集),本文件对应单测已删。
本文件现辖:``_r1_ledger_terms`` 返回契约(inf 仅由合格集空三来源
承载 + 成型先序探针)与档案帧端到端(污染墓碑 + 刷新发射 + 域外零漂移)。

fixture 说明:锁 B 内联 p1r8 帧状态(来源 = 对局档案
match_g_20260907_021326.json slices decisions.jsonl 首行,禁引用
.debug 路径故原样抄录;gold=53/level=5/deployed 4 人/bench 空)。
"""
from __future__ import annotations

import math

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    _r1_ledger_terms,
)

# ===== 测试基建(与 test_cw_zero_refresh 同款桩模式)=====

#: P1 配方体系对(本局档案锁帧对);成员全集 = 15 名跨 1-5 费。
_T88_PAIR: tuple[str, ...] = ('仙舟', '持续伤害')


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _session():
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = pair_target_comp(_T88_PAIR)
    s.plane_lengths_seen = [9, 5, 7]
    return s


def _decide(state: GameState, session):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
        MandateV1Strategy,
    )

    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, type('_Cfg', (), {'ev_arm': 'full'})())


def _p1r8_frame(gold: int = 53) -> tuple[GameState, object]:
    """档案 p1r8 帧内联(gold/level/deployed 抄档案;bench 空;空店面
    隔离买面,使 R1 刷新为该帧唯一可能发射)。"""
    deployed = [
        _bc('椒丘', star=2, slot=1),
        _bc('艾丝妲', star=1, slot=2),
        _bc('藿藿', star=2, slot=1),
        _bc('忘归人', star=1, slot=2),
    ]
    st = GameState(gold=gold, level=5, plane=1, round_num=8, hp=100)
    st.shop = []
    st.bench = []
    st.deployed = deployed
    return st, _session()


# ===== 锁 A:合格集语义单帧锁(主锁)=====

class TestR1QualifiedSetSemantics:
    """钉 inf 返回契约:inf 只剩「合格集空」三来源(成员集空 / 全部
    2★ 成型 / 该级全不可追),任一非空合格集不得被打 inf(ADR-0571
    污染缺陷的直锁形态);「部分不可追剔出合格集」的精确卡费行为面
    由 test_cw_vgap_frame_horizon.py::TestMixedPeakCompletionAccount
    承载(覆盖对账超集,本文件不双锁)。"""

    def test_all_unchaseable_is_inf(self):
        """变异探针①:成员全不可追(lv5 的 5 费)⇒ (inf, 0)——合格集
        空三来源之一,契约保持。"""
        e_sum, fees = _r1_ledger_terms(('景元',), [], [], 5)
        assert e_sum == float('inf')
        assert fees == 0

    def test_all_formed_is_inf(self):
        """变异探针②:成员全 2★ 成型 ⇒ (inf, 0)——成型出域后合格集空。"""
        bench = [_bc('停云', star=2, slot=1)]
        e_sum, fees = _r1_ledger_terms(('停云',), bench, [], 5)
        assert e_sum == float('inf')
        assert fees == 0

    def test_empty_membership_is_inf(self):
        """变异探针③:成员集空 ⇒ (inf, 0)。"""
        e_sum, fees = _r1_ledger_terms((), [], [], 5)
        assert e_sum == float('inf')
        assert fees == 0

    def test_formed_check_precedes_chaseability_probe(self):
        """F7 成型先序探针(判别力修复版):「成型出合格集」必须先于
        「可追性判定」——成型 ∧ 该级可追的成员若按可追性放行,会以
        j≥2 混入账面多计 (k−j)×cost 卡费。fixture = 停云 2★ 成型件
        (1 费,lv7 可追)+ 景元 1★(lv7 起 5 费可追):期望卡费 = 景元
        单人 (k−0)×cost(注册表现算,纪律 9);先序翻转则停云再计
        (3−2)×1 即红。旧 fixture(景元 2★ + 停云 @lv5)中成型件在该级
        恰不可追,两种判定顺序同果,对先序零判别力,已重写。"""
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.data.cw_shop_odds import (
            refresh_prob,
        )
        bench = [_bc('停云', star=2, slot=1)]
        # 探针判别力前提:成型件在该级本可追(否则两判定顺序同果)
        assert refresh_prob(7, CHARACTERS['停云'].cost) > 0
        e_sum, fees = _r1_ledger_terms(('停云', '景元'), bench, [], 7)
        assert math.isfinite(e_sum)
        assert fees == 3 * CHARACTERS['景元'].cost


# 判据纯数面(r1_commitment_account 真值表)已并入判据主题文件
# test_cw_vgap_frame_horizon.py::TestCriterionAffordability(四臂超集,
# 覆盖对账后本文件三测子集删除,见文件头「覆盖对账」)。

# ===== 锁 B:档案帧端到端帧锁 =====

class TestArchiveP1R8Frame:
    """p1r8 帧(gold=53,lv5,金过息线 50)= 本局「r8 该 D 未 D」的帧级
    事实。修复前:R1 账被污染为 inf → rkey=no_chaseable_member → 零动作;
    修复后:真 account_over_budget → 必花域切分线 yield → r2_budget 批
    → RefreshShop 发射(reason='must_spend_r1_yielded')。"""

    def test_p1r8_frame_pollution_absent_and_refresh_emitted(self):
        """档案 p1r8 必花域帧双面同帧锁:①拒因归真墓碑——
        ``shop_r1_no_chaseable_member`` 键不得出现(修复前该键恰出现,
        ADR-0571 污染签名),真链走 account_over_budget→yield(yielded
        分键在案);②刷新发射——RefreshShop(reason='must_spend_r1_
        yielded')且义务来源披露 v3_release_reason='must_spend'(该
        写点全仓唯一直锁;同帧围栏键加密面由 test_cw_must_spend_zone
        g20 派生帧承载,不双锁)。"""
        st, sess = _p1r8_frame()
        acts = _decide(st, sess)
        cnt = state_of(sess).cw4_counters
        assert 'shop_r1_no_chaseable_member' not in cnt
        assert cnt.get('must_spend_r1_account_yielded', 0) >= 1
        refreshes = [a for a in acts if isinstance(a, RefreshShop)]
        assert refreshes, f'必花域帧应有刷新发射,实际 {acts}'
        assert all(a.reason == 'must_spend_r1_yielded' for a in refreshes)
        assert state_of(sess).v3_release_reason == 'must_spend'

    def test_outside_zone_frame_stays_closed(self):
        """域外零漂移(息线纪律结构承载):同构帧金 40 ≤ 息线 ⇒ R1 被
        account_over_budget 拒(真预算账,非污染拒因)且零刷新发射——
        本修复只开「必花域内」通道,金 ≤ g* 帧刷新纪律不变。"""
        st, sess = _p1r8_frame(gold=40)
        acts = _decide(st, sess)
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        cnt = state_of(sess).cw4_counters
        assert cnt.get('shop_r1_account_over_budget', 0) >= 1
        assert 'shop_r1_no_chaseable_member' not in cnt
