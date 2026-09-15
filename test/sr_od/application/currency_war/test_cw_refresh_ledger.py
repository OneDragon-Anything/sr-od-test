"""决策环数据流断链修复 · 缺陷①回归锁(刷新通道整局失能)。

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
纯数面真值表(within/over/non-finite 含 NaN/零负预算四臂)声称由判据主题
文件 test_cw_vgap_frame_horizon.py::TestCriterionAffordability 承载,
本文件原 TestR1CommitmentAccountBoundary 三测为其真子集已删;混合集
过滤「部分不可追 ≠ 合格集空」的精确卡费面声称由同文件
TestMixedPeakCompletionAccount lv6 臂承载(超集),本文件对应单测已删。
⚠️ 上两处承载文件**全史不存在(幽灵指针,2026-09-15 复查确认)**——
被删断言面曾无载体,覆盖缺口已申报;纯数真值表四臂已随批归位
本文件(TestR1CommitmentAccountTruthTable 直测),混合集精确卡费面由
下方 TestR1QualifiedSetSemantics::test_formed_check_precedes_chaseability_
probe 承载先序面。
本文件现辖:``_r1_ledger_terms`` 返回契约(inf 仅由合格集空三来源
承载 + 成型先序探针)与档案帧端到端(污染墓碑 + 刷新发射 + 域外零漂移)。

fixture 说明:锁 B 内联 p1r8 帧状态(来源 = 对局档案
match_g_20260907_021326.json slices decisions.jsonl 首行,禁引用
.debug 路径故原样抄录;gold=53/level=5/deployed 4 人/bench 空)。
"""
from __future__ import annotations

import math

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session as _session,
)

from sr_od.application.currency_war.kernel.cw_vocab import (
    CwSimFrame,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as refresh_criteria,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    _r1_ledger_terms,
)

# ===== 测试基建(与 test_cw_zero_refresh 同款桩模式;单一源 = _cw_helpers)=====

#: P1 配方体系对(本局档案锁帧对);成员全集 = 15 名跨 1-5 费。
_T88_PAIR: tuple[str, ...] = ('仙舟', '持续伤害')


def _session_t88():
    """T88 锁线会话:target = 配方对(非六件套家族的 comp 直选)、
    档案帧位面史、不建 LineState——cw4_session 的三参数分层面。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        pair_target_comp,
    )
    return _session(pair_target_comp(_T88_PAIR),
                    plane_lengths=[9, 5, 7], line_state=False)


def _p1r8_frame(gold: int = 53) -> tuple[CwSimFrame, object]:
    """档案 p1r8 帧内联(gold/level/deployed 抄档案;bench 空;空店面
    隔离买面,使 R1 刷新为该帧唯一可能发射)。"""
    deployed = [
        _bc('椒丘', star=2, slot=1),
        _bc('艾丝妲', star=1, slot=2),
        _bc('藿藿', star=2, slot=1),
        _bc('忘归人', star=1, slot=2),
    ]
    st = CwSimFrame(gold=gold, level=5, plane=1, round_num=8, hp=100)
    st.shop = []
    st.bench = []
    st.deployed = deployed
    return st, _session_t88()


# ===== 锁 A:合格集语义单帧锁(主锁)=====

class TestR1QualifiedSetSemantics:
    """钉 inf 返回契约:inf 只剩「合格集空」三来源(成员集空 / 全部
    2★ 成型 / 该级全不可追),任一非空合格集不得被打 inf(ADR-0571
    污染缺陷的直锁形态)。(「部分不可追剔出合格集」的精确卡费面声称
    由 test_cw_vgap_frame_horizon.py 承载——该文件全史不存在,幽灵
    指针,缺口已申报。)"""

    @pytest.mark.parametrize('members,bench,level', [
        (('景元',), [], 5),                                  # 成员全不可追(lv5 的 5 费)
        (('停云',), [_bc('停云', star=2, slot=1)], 5),       # 全 2★ 成型出域
        ((), [], 5),                                         # 成员集空
    ], ids=['all-unchaseable', 'all-formed', 'empty-membership'])
    def test_qualified_set_empty_sources_are_inf(
            self, members, bench, level):
        """inf 三来源同契约:合格集空 ⇒ (inf, 0)(成员集空 / 全成型 /
        全不可追,三案一锁)。"""
        e_sum, fees = _r1_ledger_terms(members, bench, [], level)
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


# ===== 判据纯数面:r1_commitment_account 真值表直测(收编)=====
# (原声称载体 test_cw_vgap_frame_horizon.py::TestCriterionAffordability
# 全史不存在 = 幽灵指针,被删断言面随本批归位本文件。)

class TestR1CommitmentAccountTruthTable:
    """``r1_commitment_account`` 纯数真值表:within 启动双案 + 拒因五案
    参数化一锁(超账/零负预算 ⇒ account_over_budget;非有限 ⇒
    no_chaseable_member)。判据本体 = criteria/refresh 单点(docstring
    边界段:非有限 ⇒ no_chaseable_member;零负预算恒不启动,息线双侧
    修正由比较式结构承载,不另设门)。"""

    @pytest.mark.parametrize('ledger,budget', [
        (100.0, 100),     # 边界内(等号 = 可负担,启动)
        (99.5, 100),      # 边界内严格小于
    ], ids=['within-equal', 'within-strict'])
    def test_within_budget_starts(self, ledger, budget):
        assert refresh_criteria.r1_commitment_account(ledger, budget) \
            == (True, '')

    @pytest.mark.parametrize('ledger,budget,reason', [
        (100.5, 100, 'account_over_budget'),          # 超账拦阻
        (1.0, 0, 'account_over_budget'),              # 零预算恒不启动
        (1.0, -10, 'account_over_budget'),            # 负预算恒不启动
        (float('inf'), 100, 'no_chaseable_member'),   # 合格集空 inf 承载
        (float('nan'), 100, 'no_chaseable_member'),   # NaN 防御
    ], ids=['over-budget', 'budget-zero', 'budget-negative', 'inf', 'nan'])
    def test_rejection_truth_table(self, ledger, budget, reason):
        """拒因真值表:正账面 > 预算与零负预算走 account_over_budget(金在
        息线 g* 及以下恒不启动,不另设门);非有限总账(合格集空/E=∅ 的
        inf 承载 + NaN 防御)⇒ no_chaseable_member,不与超账混桶(污染
        墓碑判读面)。"""
        assert refresh_criteria.r1_commitment_account(ledger, budget) \
            == (False, reason)


# ===== 锁 B:档案帧端到端帧锁 =====

class TestArchiveP1R8Frame:
    """p1r8 帧(gold=53,lv5,金过息线 50)= 本局「r8 该 D 未 D」的帧级
    事实。修复前:R1 账被污染为 inf → rkey=no_chaseable_member → 零动作;
    污染修复后:真 account_over_budget → 必花域切分线 yield → RefreshShop
    发射;刷新止损批期望账前件恢复后:同帧(r_remaining=14,非末轮)超账
    → 域内拦,零刷新发射。本文件主旨 = 拒因归真墓碑(污染签名不得
    复现)不变;行为断言随账前件恢复演进——旧语义(全域 yielded 放行,
    账买不齐也刷)把零产出烧金段固化成行为(2026-09-15 sim 批量找问题
    报告「问题 1」病灶),已由「末轮豁免 + 账前件拦」取代,docstring
    记一句为什么旧语义过期。"""

    def test_p1r8_frame_pollution_absent_and_overaccount_blocked(self):
        """档案 p1r8 必花域帧双帧同锁(区内 + 区外):①拒因归真墓碑——
        ``shop_r1_no_chaseable_member`` 键不得出现(修复前该键恰出现,
        ADR-0571 污染签名);②区内超账拦阻——零刷新发射 + 域内账拦分键
        ``must_spend_r1_account_fail`` 开火(该帧 r_remaining=14 含
        后续位面,末轮豁免不辖);③域内义务来源披露照写
        v3_release_reason='must_spend'(披露面独立于刷新发射,写点在
        R1 之前;同帧围栏键加密面无独立覆盖锁——现役近邻
        test_cw_no_target_three_arms::test_must_spend_zone_no_refresh_burn
        辖 p2plus 无目标帧族,非本档案帧族,不构成对偶覆盖);④域外零
        漂移对照帧(gold=40 ≤ 息线)——R1 被 account_over_budget 拒
        (真预算账,非污染拒因)且零刷新发射,域外帧刷新纪律与账前件
        恢复无关(域外本就按账判)。末轮豁免支的发射形态由
        TestHorizonClosedYield 承载,不双锁。"""
        # 区内帧(gold=53,过息线)
        st, sess = _p1r8_frame()
        acts = _decide(st, sess)
        cnt = state_of(sess).cw4_counters
        assert 'shop_r1_no_chaseable_member' not in cnt
        assert not [a for a in acts if isinstance(a, RefreshShop)], acts
        assert cnt.get('must_spend_r1_account_fail', 0) >= 1
        assert state_of(sess).v3_release_reason == 'must_spend'
        # 区外对照帧(gold=40,息线下)
        st_out, sess_out = _p1r8_frame(gold=40)
        acts_out = _decide(st_out, sess_out)
        assert not [a for a in acts_out if isinstance(a, RefreshShop)]
        cnt_out = state_of(sess_out).cw4_counters
        assert cnt_out.get('shop_r1_account_over_budget', 0) >= 1
        assert 'shop_r1_no_chaseable_member' not in cnt_out


class TestHorizonClosedYield:
    """末轮豁免锁(全局局终帧;谓词单一源 = crit_refresh.
    r1_horizon_closed):r_remaining=1(含当前节点)帧金随局终沉没,
    刷新机会成本 = 0,正概率出牌机会弱支配停手——必花域超账帧放行
    照旧。这是域内 yielded 放行在账前件恢复后的唯一存活辖域;非末轮
    域内超账拦形态由 TestArchiveP1R8Frame 承载,不双锁。"""

    def test_global_final_frame_overaccount_still_yields(self):
        """P3 r7(全局末轮,plane_lengths=[9,5,7] ⇒ r_remaining=1)
        超账帧:刷新发射 reason='must_spend_r1_yielded' + yielded 分键
        在案——豁免支活性行为锁。空店面隔离买面(R1 刷新为该帧唯一
        可能发射,与 _p1r8_frame 同构)。"""
        deployed = [
            _bc('椒丘', star=2, slot=1),
            _bc('艾丝妲', star=1, slot=2),
            _bc('藿藿', star=2, slot=1),
            _bc('忘归人', star=1, slot=2),
        ]
        st = CwSimFrame(gold=53, level=5, plane=3, round_num=7, hp=100)
        st.shop = []
        st.bench = []
        st.deployed = deployed
        sess = _session_t88()
        acts = _decide(st, sess)
        cnt = state_of(sess).cw4_counters
        assert cnt.get('must_spend_r1_account_yielded', 0) >= 1
        refreshes = [a for a in acts if isinstance(a, RefreshShop)]
        assert refreshes, f'全局末轮帧应豁免放行,实际 {acts}'
        assert all(a.reason == 'must_spend_r1_yielded' for a in refreshes)
