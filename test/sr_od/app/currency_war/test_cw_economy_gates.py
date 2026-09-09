"""CW 经济闸族测试(#5):afford / vgap / must_spend / budget_disclosure
各代表行 + data_registry 金核(金票券 OCR 真值锚)。

覆盖面:
- afford:r1_commitment_account 判据本体四分支(预算内放行/超预算拒/
  非有限=合格集空拒/零预算恒拒)+ r2_budget 硬闸两向(全仓唯一直调);
- vgap:R1 门形态三分支(息线关门/大溢余开门/合格集空关门分键)
  + 混合峰值完成账(部分不可追≠合格集空;g_20260907_021326 实机
  9 评估帧 0 刷店事故定谳,ADR-0571 勘误);
- must_spend:G_must 判据单一源(10×cap_resolved 边界,买断制出辖,
  cap 覆写参数化)+ L3 模式无关行为行(m3_batch:must_spend 授权);
- budget_disclosure:闸拒归因分键可辨(budget_gate_must_spend_defer /
  deadend 观测分键,域内独立于域外);
- 金核:备战店面金卡典籍/银箱互斥判定(slot1/7 命中典籍、slot4/9
  走箱不判典籍;OCR 真值锚)。

来源:must_spend_zone(mv 主干)/ vgap_frame_horizon / budget_gate
(披露分键两行)/ data_registry 金核段(该文件已按 #15 重建,金核代表
迁入本文件;2026-09-09 套件重建批 A,#5)。其余历史锁已退役
(git 可复活)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import (
    in_must_spend_zone,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.obs import cw_identity_obs as cio
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    shop as shop_mod,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)
from test.sr_od.app.currency_war._cw_helpers import (
    battle_state as _state,
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
from test.sr_od.app.currency_war._cw_helpers import (
    ns_session as _ns_session,
)

_COMP = '列车同行'


def _ns_with_state(**state_fields) -> SimpleNamespace:
    """桩 session:策略器字段经 state_of 载体设置(session 职责分离迁移后
    生产唯一读面;对 SimpleNamespace 桩同样生效)。"""
    s = SimpleNamespace()
    st = state_of(s)
    for k, v in state_fields.items():
        setattr(st, k, v)
    return s


def _zone_frame(gold: int, *, cards=None, level: int = 5,
                locked: bool = True) -> tuple[GameState, SimpleNamespace]:
    """必花域帧:锁线列车同行、level=level、gold 必入域(g > 50)。"""
    comp = get_comp(_COMP)
    km = list(line_members(comp))
    chaseable = [m for m in km if m != '瓦尔特']
    deployed = [_bc(m, star=2, slot=i + 1)
                for i, m in enumerate(chaseable)]
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.level_readable = True
    st.plane = 2
    st.node_type = 'battle'
    st.shop = list(cards) if cards is not None else []
    st.bench = []
    st.deployed = deployed
    st.refresh_probs = {5: 0}
    sess = _ns_with_state(
        cw4_counters={},
        target_comp=comp,
        v3_intention=SimpleNamespace(
            locked_comp=(_COMP if locked else '')))
    return st, sess


def _bg_sess():
    """budget_gate 披露分键两行的 session(锁线列车同行)。"""
    return _ns_session(get_comp(_COMP))


# ==================== must_spend:G_must 判据单一源 ====================


class TestZonePredicate:

    def test_zone_predicate_bounds(self):
        """G_must = 10×cap_resolved:g 越线 True/等值 False;买断制
        (cap=0)出辖恒 False。注入通道 = session.active_strategies
        注册表名(ADR-0598 单一源迁移,原 cw4_cap_override 死通道退役)。"""
        sess = _ns_with_state()
        assert in_must_spend_zone(51, sess) is True
        assert in_must_spend_zone(50, sess) is False
        buyout = _ns_with_state()
        buyout.active_strategies = ['买断制']
        assert in_must_spend_zone(999, buyout) is False
        rich = _ns_with_state()
        rich.active_strategies = ['利息上调']
        assert in_must_spend_zone(101, rich) is True
        assert in_must_spend_zone(100, rich) is False


class TestL3MustSpend:

    def test_l3_skeleton_only_mode_applies(self):
        """C1 模式无关锁:skeleton_only(骨架 only)帧 ⇒ L3 照样适用
        (金量级裁定与模式无关,ADR-0528 模式无关声明)。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='skeleton_only'))
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'm3_batch:must_spend'


# ==================== afford:r1 判据本体 + r2 硬闸(自 test_cw_vgap_frame_horizon 并入) ====================


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


class TestR2BudgetGate:
    """r2 预算门纯数锁(P40 R2 原语义,ADR-0516 保留声明;
    test_cw_zero_refresh 同名类迁入后唯一载体的继任,断言零改动)。"""

    def test_gold_minus_reserve_gates_refresh_cost(self):
        """r2 预算门两向:金−预留 ≥ 刷价才批(全仓唯一直调锁)。
        门形态端到端面归本文件 TestR1AffordabilityGate 与
        TestZonePredicate(域内可负担性硬闸仍辖)。"""
        assert not crit_refresh.r2_budget(1, 51, 2)
        assert crit_refresh.r2_budget(60, 51, 2)


class TestR1AffordabilityGate:
    """门形态(行为锁;ADR-0516)。帧态构造:lv6、合格集收缩到单目标
    成员(其余线成员置 2★ 成型出域,P40 A4)、目标 1★×2(j=2,差 1 张
    到 2★ 完成档)——总账量级 ~20 金;视界 r=14
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
        assert not [a for a in acts if isinstance(a, RefreshShop)]
        assert state_of(sess).cw4_counters.get('shop_r1_no_chaseable_member', 0) >= 1


class TestMixedPeakCompletionAccount:
    """完成账整套求和口径锁(用户裁定 2026-09-04;装配承载修正 =
    ADR-0571;旧 inf 污染缺陷病理形态实证 = g_20260907_021326 实机
    9 评估帧 0 刷店)。本文件保留 lv6 过滤代表行;lv7 求和行退役
    git 可复活。"""

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


# ==================== budget_disclosure:闸拒归因分键(自 test_cw_budget_gate 并入) ====================


class TestMustSpendGate:
    """必花域 L3 位:闸在域内生效(P72 承继「要花 ≠ 花在哪」)。"""

    def test_zone_gate_defers_with_key(self):
        """域内帧(g=65, 批 20 金,τ(65)=5 → 花后 45 < 50)⇒ 闸拒改道:
        budget_gate_must_spend_defer 独立分键(与域外分键分开,归因可辨),
        零 LevelUpShop。"""
        st = _state(65, 5, xp=(0, 20))
        sess = _bg_sess()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_defer') == 1
        assert 'levelup_budget_gate_blocked' not in state_of(sess).cw4_counters

    def test_zone_gate_deadend_observed(self):
        """金滞留死角观测:闸拒 ∧ bench 无空席(义务无处安放)⇒
        budget_gate_must_spend_deadend 观测分键在案(纯观察,不降档)。
        帧构造:满编全 2★ 线(无 M2 缺口/M4 腾席干扰)+ bench 9 垫
        (bench_free=0)+ g=57(τ(57)=5,花后 49 < 50,ρ=0 闸拒)。"""
        km = list(line_members(get_comp(_COMP)))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        pad_bench = [_bc(f'垫{i}', star=1, slot=i + 1) for i in range(9)]
        st = _state(57, 4, xp=(0, 6), bench=pad_bench, deployed=deployed)
        sess = _bg_sess()
        act = shop.decide_shop_action(st, sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_defer') == 1
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_deadend') == 1


# ==================== 金核:金票券 OCR 真值锚(自 test_cw_data_registry 金核段迁入) ====================

_TEST_ROOT = Path(__file__).resolve().parents[4]   # 测试仓根(sr-od-test)
FIXTURES = _TEST_ROOT / 'screens' / '货币战争-备战'  # 备战屏 fixture 目录

# 备战栏-1..9 pc_rect(assets/game_data/screen_info/currency_war_battle_prep.yml;
# 与 cw_identity_obs._ctx_slots 同一坐标系的离线硬编码,同 find_supply_boxes 分层约定)
SLOTS = [
    Rect(382, 845, 495, 979), Rect(507, 844, 620, 978), Rect(632, 844, 743, 978),
    Rect(757, 845, 869, 979), Rect(882, 846, 995, 980), Rect(1004, 847, 1118, 978),
    Rect(1132, 846, 1244, 977), Rect(1256, 845, 1368, 979), Rect(1379, 844, 1493, 980),
]
_IDX = list(enumerate(SLOTS, 1))

_FRAME_GOLD = FIXTURES / 'shop_closed_lowhp.webp'      # slot1/7 金卡典籍 + slot4/9 银箱


def _slots(screen: np.ndarray) -> list[tuple[int, Rect]]:
    """1080p 整帧校验 + 带槽号 rect 对(防 fixture 尺寸漂移静默错位)。"""
    assert screen.shape[:2] == (1080, 1920), f'真值帧应为 1080p,实得 {screen.shape}'
    return _IDX


@pytest.fixture(scope='module')
def gold_frame() -> np.ndarray:
    img = cv2_utils.read_image(str(_FRAME_GOLD))
    assert img is not None, f'真值帧缺失:{_FRAME_GOLD}'
    return img


def test_gold_card_slots_hit_tomes(gold_frame) -> None:
    """slot1/slot7 金票券卡必须被 find_tomes 命中(旧模板在 slot7 被 shape 守卫
    判盲 → 箱模板低分接走 → 误判为箱)。"""
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    tome_slots = {idx for idx, _ in tomes}
    assert {1, 7} <= tome_slots, f'金卡典籍槽应命中,实得 {sorted(tome_slots)}'


def test_silver_box_slots_not_tomes(gold_frame) -> None:
    """银箱槽(slot4/9)互斥判定必须走箱:箱命中且不被认成典籍。"""
    boxes = cio.find_supply_boxes(gold_frame, _slots(gold_frame))
    tomes = cio.find_tomes(gold_frame, _slots(gold_frame))
    box_slots = {idx for idx, _ in boxes}
    tome_slots = {idx for idx, _ in tomes}
    assert {4, 9} <= box_slots, f'银箱槽应报箱,实得 {sorted(box_slots)}'
    assert not ({4, 9} & tome_slots), f'银箱槽不得判典籍,实得 {sorted(tome_slots)}'
