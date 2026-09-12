"""CW 经济闸族测试(#5):afford / vgap / must_spend / budget_disclosure
各代表行 + data_registry 金核(金票券 OCR 真值锚)。

收缩注记(CUT9 二次收缩:原 15 测试→8 测试;同分支变体/双保险重复砍,
git 可复活):
- afford 判据本体留超预算拒(fail-closed 方向);开门方向由 vgap
  大溢余开门端到端代表;非有限/零预算两变体砍;
- vgap 门形态三分支留息线关门 + 大溢余开门两代表,合格集空关门
  (shop_r1_no_chaseable_member 分键)归 #8 刷新面 fail-closed 锁,
  本文件三处重复代表砍;
- must_spend 留 G_must 判据单一源代表(L3 skeleton_only 模式无关
  变体砍);disclosure 留 defer 分键代表(deadend 观测分键砍);
- 金核 OCR 两代表全留(金卡典籍命中 + 银箱互斥,两真实分支各 1 行);
- 混合峰值完成账 lv6 行砍(求和口径由 afford 判据 + r2 硬闸承载,
  事故病理形态已随 ADR-0571 修复入生产)。

覆盖面:
- afford:r1_commitment_account 超预算拒(fail-closed)+ r2_budget
  硬闸两向(金−预留 ≥ 刷价,全仓唯一直调);
- vgap:R1 门形态息线关门/大溢余开门两代表(行为级);
- must_spend:G_must 判据单一源(10×cap_resolved 边界,买断制出辖);
- budget_disclosure:闸拒归因分键可辨(budget_gate_must_spend_defer);
- 金核:备战店面金卡典籍/银箱互斥判定(slot1/7 命中典籍、slot4/9
  走箱不判典籍;OCR 真值锚)。

来源:must_spend_zone(mv 主干)/ vgap_frame_horizon / budget_gate
(披露分键)/ data_registry 金核段(2026-09-09 套件重建批 A,#5;
CUT9 二次收缩见收缩注记)。其余历史锁已退役(git 可复活)。
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
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwWorkFrame,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.obs import cw_identity_obs as cio
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    battle_state as _state,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
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


# ==================== afford:r1 判据本体 + r2 硬闸(自 test_cw_vgap_frame_horizon 并入) ====================


class TestCriterionAffordability:
    """判据本体(纯数面;ADR-0516 形式二)。"""

    def test_over_budget_closed(self):
        ok, key = crit_refresh.r1_commitment_account(11.0, 10)
        assert not ok and key == 'account_over_budget'


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
    def _frame(gold: int) -> tuple[CwWorkFrame, object]:
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
        st = CwWorkFrame(gold=gold, level=6, round_num=8)
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


# ==================== budget_disclosure:闸拒归因分键(自 test_cw_budget_gate 并入) ====================


class TestMustSpendGate:
    """必花域 L3 位:闸在域内生效(P72 承继「要花 ≠ 花在哪」)。"""

    def test_zone_gate_defers_with_key(self):
        """域内帧(g=65, 批 20 金,τ(65)=5 → 花后 45 < 50)⇒ 闸拒改道:
        budget_gate_must_spend_defer 独立分键(与域外分键分开,归因可辨),
        零 LevelUpShop。"""
        st = _state(65, 5, xp=(0, 20))
        sess = _bg_sess()
        act = shop.decide_shop_action(cw4_bs(st, sess), sess,
                                      SimpleNamespace(ev_arm='full'))
        assert not isinstance(act, LevelUpShop)
        assert state_of(sess).cw4_counters.get('budget_gate_must_spend_defer') == 1
        assert 'levelup_budget_gate_blocked' not in state_of(sess).cw4_counters


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
