"""R1 刷新门·形式二可负担性测试(ADR-0516;V̄ 链退役重锚)。

锁(出处=ADR-0516 裁决与形式二规格;旧 V̄_net/V_GAP 槽位比较项测试
随链退役,本文件重锚为新判据行为锁):
- 判据本体(criteria/refresh.r1_commitment_account 纯数面):
  总账 ≤ 可用预算放行;非有限(无可追成员)拒 'no_chaseable_member';
  预算 ≤ 0 恒拒 'account_over_budget'(息线双侧修正:刷新只花息线
  g* 之上的溢余);
- 门形态(行为面):金在息线及以下关门;大溢余 + 可追缺件开门发射
  RefreshShop;深缺口小溢余关门 + ``shop_r1_account_over_budget`` 分键;
  合格集空(成员全 2★)关门 + ``shop_r1_no_chaseable_member`` 分键。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop as shop_mod,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_decide as _decide,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_session as _session,
)

# ===== 测试基建(承旧 vgap 文件同款桩;六件套单一源 = _cw_helpers)=====


class TestCriterionAffordability:
    """判据本体(纯数面;ADR-0516 形式二)。"""

    def test_within_budget_opens(self):
        assert crit_refresh.r1_commitment_account(10.0, 11) == (True, '')

    def test_over_budget_closed(self):
        ok, key = crit_refresh.r1_commitment_account(11.0, 10)
        assert not ok and key == 'account_over_budget'

    def test_non_finite_is_no_chaseable_member(self):
        """合格集空(E=∅/该级不出此费)⇒ inf/NaN 拒 no_chaseable_member
        (P40 R0-1 刷新侧特例)。"""
        for bad in (float('inf'), float('nan')):
            assert crit_refresh.r1_commitment_account(bad, 100) \
                == (False, 'no_chaseable_member')

    def test_zero_budget_always_closed(self):
        """预算 ≤ 0(金在息线 g* 及以下)恒拒——息线双侧修正由比较式
        结构承载,不另设门(修正③:停级买牌也压金破息)。"""
        for ledger in (0.5, 1.0, 100.0):
            assert crit_refresh.r1_commitment_account(ledger, 0) \
                == (False, 'account_over_budget')
            assert crit_refresh.r1_commitment_account(ledger, -5)[0] is False


class TestR1AffordabilityGate:
    """门形态(行为锁;ADR-0516)。帧态构造:lv6、合格集收缩到单目标
    成员(其余线成员置 2★ 成型出域,P40 A4)、目标 1★×2(j=2,差 1 张
    到 2★ 完成档,E 取 expected_refreshes_for_card 峰值级小值)——
    总账量级 ~20 金,跨预算 70/11/0 三档判开门/关门;视界 r=14
    (plane_lengths=[9,5,7] 同旧桩口径)。
    """

    @staticmethod
    def _frame(gold: int) -> tuple[GameState, object]:
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.data.cw_shop_odds import (
            expected_refreshes_for_card,
        )

        comp = _comp()
        members = _members(comp)
        # 追件目标 = 该级可追(E>0 且有限)成员中期望刷次最小者(小总账帧)
        target = min(
            (m for m in members
             if CHARACTERS[m].cost
             and 0.0 < expected_refreshes_for_card(
                 6, CHARACTERS[m].cost, 2, 2) < float('inf')),
            key=lambda m: expected_refreshes_for_card(
                6, CHARACTERS[m].cost, 2, 2))
        others = [m for m in members if m != target]
        bench = [_bc(target), _bc(target, slot=2)] \
            + [_bc(m, star=2, slot=i + 3) for i, m in enumerate(others)]
        st = GameState(gold=gold, level=6, round_num=8)
        st.plane = 1
        st.shop = [ShopCard(x=100, name='垫', cost=3, star=1)]
        st.bench = bench
        st.deployed = []
        return st, _session(comp, plane_lengths=[9, 5, 7])

    def test_at_interest_line_closed(self):
        """金=息线 g*(50)⇒ 预算 0 ⇒ 关门(修正③:两侧都过 g* 账)。"""
        st, sess = self._frame(50)
        acts = _decide(st, sess)
        # 域外帧(gold=50 非必花域):零变化,息线门照旧关门
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        assert state_of(sess).cw4_counters.get('shop_r1_account_over_budget', 0) >= 1

    def test_large_surplus_opens(self):
        """大溢余(gold=120,预算 70)+ 可追缺件:总账(刷费+卡费+息损)
        ≤ 预算 ⇒ 开门发射 RefreshShop。"""
        st, sess = self._frame(120)
        acts = _decide(st, sess)
        assert any(isinstance(a, RefreshShop) for a in acts)

    def test_small_surplus_deep_gap_closed(self):
        """小溢余(gold=61)为必花域帧(20 号稿):g*/L 核算账降期望核算
        (account_over_budget 分键不落),刷新由可负担性硬闸
        (r2_budget)承载 ⇒ 刷新发射。"""
        st, sess = self._frame(61)
        acts = _decide(st, sess)
        assert state_of(sess).cw4_counters.get('shop_r1_account_over_budget', 0) == 0
        assert any(isinstance(a, RefreshShop) for a in acts)

    def test_qualified_set_empty_closed(self):
        """合格集空(成员全部 2★ 成型)⇒ 关门 +
        ``shop_r1_no_chaseable_member`` 分键(P40 R0-1)。"""
        comp = _comp()
        members = _members(comp)
        bench = [_bc(m, star=2, slot=i + 1)
                 for i, m in enumerate(members[:5])]
        st = GameState(gold=120, level=7, round_num=8)
        st.plane = 1
        st.shop = [ShopCard(x=100, name='垫', cost=3, star=1)]
        st.bench = bench
        st.deployed = []
        sess = _session(comp, plane_lengths=[9, 5, 7])
        acts = _decide(st, sess)
        # 域外帧(gold=50 非必花域):零变化,息线门照旧关门
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        assert state_of(sess).cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1


class TestMixedPeakCompletionAccount:
    """完成账整套求和口径锁(用户裁定 2026-09-04「对整个目标阵容……
    是不是合适的」;装配承载修正 = ADR-0571)。

    合格集含 2费(花火)+5费(流萤):lv6 段 5费不出(REFRESH_PROB
    lv6 无 5费档)⇒ 流萤剔出本级合格集、账 = 花火单成员贡献(有限);
    lv7 段 5费可追(0.01)⇒ 两成员同入合格集、账为整套求和(与「逐
    成员取 min」账的差异锚 = 双成员卡费逐位)。旧锁钉「任一成员不可追
    ⇒ E=∞ ⇒ R1 拒 no_chaseable_member」——那是 inf 污染缺陷的病理
    形态(部分不可追被错判全空,刷新臂 3-6 级结构性恒关,
    g_20260907_021326 实证 9 评估帧 0 刷店),ADR-0571 勘误;完成账的
    「整套补齐」读法本身保留,修正的只是装配承载。口径 =
    ``_r1_ledger_terms`` 装配侧直接复现(j=0、c_taken=0),不经过整帧
    决策。
    """

    @staticmethod
    def _terms(level: int) -> tuple[float, int]:
        return shop_mod._r1_ledger_terms(('花火', '流萤'), [], [], level)

    def test_lv6_mixed_set_filters_unchaseable(self):
        """lv6:5费(流萤)不可追 ⇒ 剔出本级合格集(禁打 inf):账 =
        花火单成员贡献,有限且卡费为正——「部分不可追 ≠ 合格集空」;
        小预算帧 R1 拒因归真(account_over_budget,预算比较承载
        fail-closed),非「合格集空」伪拒因。"""
        e_sum, fees = self._terms(6)
        assert 0.0 < e_sum < float('inf')
        assert fees == (3 - 0) * 2   # 仅花火入集合:(k−j)×cost,k=3,j=0
        ok, key = crit_refresh.r1_commitment_account(e_sum + fees, 10)
        assert not ok and key == 'account_over_budget'

    def test_lv7_account_finite(self):
        """lv7:5费可追 ⇒ 双成员同入合格集,整套求和账有限且为正;
        Σ卡费 = 花火 3×2 + 流萤 3×5(两成员都贡献 = 非 min 账的
        结构锚,k=3/j=0 为 fixture 结构常数,cost 为注册表真值)。"""
        e_sum, fees = self._terms(7)
        assert 0.0 < e_sum < float('inf')
        assert fees == 3 * 2 + 3 * 5
