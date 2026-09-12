"""商店现货可得性主题锁(2★ 直出现货比较子 + s_reserve 拒绝对价载体)。

来源:自 test_cw_p77_spot2.py 并入(2026-09-12 归并批,按机制主题文件命名
规范);并入时删原 test_j2_diary_dominates_exclusion_still_holds——恒真
断言(base < base*3,base≥1 恒成立,测试自抄 3× 常数非生产单一源,无
真实错误可杀之),其行为面(M2b 星过滤拒)由本文件 fail-closed/基线注入
两锁承载,零覆盖损失(生产徽章定价单一源 = cw_observation.resolve_cost_
star,倍率表 {1,3,9})。

设计出处 = ``docs/develop/sr_od/application/currency_war/proofs/p77-shop-spot-availability-signal.md``
(已收口命题,本批=装载批)与本批装载设计
``.debug/temp/currency_war/T-122-装载设计.md`` §1/§2;行为落点 =
``shop.py::decide_shop_action`` m2_stockpile 臂(缺口面1)与 M6 面 s_reserve
拒帧位(缺口面3);ADR-0626 为行为变更记录。

锁契约(测试纪律 8):锁结构/回显/单一源数值锚,不锁分布数值;
数值锚全部直调生产单一源复算(P72/P76/P77 同款口径),容差 ±0.1 金/帧。
缺口面2(V_slot)按 P77 §7【拟】#3 维持 fail-closed,本文件不为其立行为锁
(缺省放行语义 = 现状回归网自辖)。
"""
from __future__ import annotations

import math

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import (
    expected_refreshes_for_card,
    reencounter_window_frames,
    refresh_prob,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    CORE_SINGLE_CARD_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    REFRESH_COST_BASE,
    BuyCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_bs,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_comp as _comp_single_source,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_members as _members_of,
)

_LOCK_COMP = '列车同行'


def _comp():
    return _comp_single_source(_LOCK_COMP)


def _members() -> list[str]:
    return _members_of(_comp())


def _non_c1_member() -> str:
    """锁锚成员 = 非 C1 直通注册表成员(C1 恒买不限星会先于臂①吃掉
    2★ 直出帧,P77 备注4——比较子锁须锚定臂①自身的判定,选无 C1 覆盖
    成员;存在性断言防注册表漂移静默空转)。"""
    for m in _members():
        if m not in CORE_SINGLE_CARD_REGISTRY:
            return m
    pytest.fail('套内全员 ∈ C1 注册表:比较子帧被 C1 前置覆盖,换套重锚')


def _sess():
    # 策略器字段(target_comp/cw4_counters)经 state_of 载体生效
    #(test_cw_spend_face._shop_session 同款 SimpleNamespace 桩)。
    from types import SimpleNamespace
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = _comp()
    return s


def _st(gold: int, shop_cards, bench, *, level: int = 7):
    from sr_od.application.currency_war.kernel.cw_vocab import CwWorkFrame
    st = CwWorkFrame(gold=gold, level=level, round_num=2, hp=60)
    st.level_readable = True
    st.plane = 2
    st.shop = list(shop_cards)
    st.bench = list(bench)
    st.deployed = []
    return st


def _decide(st, sess):
    from types import SimpleNamespace
    return shop.decide_shop_action(cw4_bs(st, sess), sess, SimpleNamespace(ev_arm='full'))


def _counters(sess) -> dict:
    return dict(getattr(state_of(sess), 'cw4_counters', {}) or {})


# ===== 缺口面1:比较子数值锚(P77 §2.2 表,直调单一源复算)=====


class TestSpot2PremiumAnchors:

    def test_p77_premium_table_rows(self):
        """P77 §2.2 现货溢价表 4 行(c_eff·E−c_base;E =
        expected_refreshes_for_card(level, cost, 2, owned=1),c_eff=基价
        REFRESH_COST_BASE)。行值 = 证明复算锚,实现端比较子同式消费。"""
        rows = [((7, 3), 30.9), ((6, 2), 30.4), ((8, 4), 57.2),
                ((9, 5), 80.7)]
        for (level, cost), want in rows:
            e = expected_refreshes_for_card(level, cost, target_star=2,
                                            owned=1)
            premium = REFRESH_COST_BASE * e - cost
            assert abs(premium - want) <= 0.1, \
                f'{cost}费@L{level} 溢价 {premium:.2f} ≠ 表值 {want}'



# ===== 缺口面1:比较子行为(j=1 帧 2★ 直出现货)=====


class TestSpot2ComparatorBehavior:

    def test_j1_star2_direct_out_bought_via_comparator(self):
        """P77 缺口面1:j=1 帧店内仅同名 2★ 直出卡(徽章语义 cost=3×base)
        ⇒ 过比较子(溢价>0)买入,reason 维持 'm2_stockpile'(义务通道
        不扩闭集),计数 m2_stockpile_spot2_buy 零静默。"""
        m = _non_c1_member()
        base = CHARACTERS[m].cost
        st = _st(gold=30, shop_cards=[_card(m, base * 3, star=2)],
                 bench=[_bc(m, slot=1)])
        sess = _sess()
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm2_stockpile'
        assert (act.card.star or 1) == 2, '比较子应取 2★ 直出现货'
        assert _counters(sess).get('m2_stockpile_spot2_buy', 0) == 1

    def test_gold_gate_carries_rejection_key(self):
        """过比较子后金不足 ⇒ 既有闸键 stockpile_unaffordable 承载拒因,
        star_mismatch 不再伞形吞闸失败帧(装载设计 §1.4 分键拆分)。"""
        m = _non_c1_member()
        base = CHARACTERS[m].cost
        st = _st(gold=1, shop_cards=[_card(m, base * 3, star=2)],
                 bench=[_bc(m, slot=1)])
        sess = _sess()
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        cs = _counters(sess)
        assert cs.get('stockpile_unaffordable', 0) == 1
        assert 'm2_stockpile_star_mismatch' not in cs

    def test_diy_infeasible_level_stays_fail_closed(self):
        """p(level,c_base)=0 帧(该级刷不出该费):E=0 是函数约定非「DIY
        零成本」——比较子判不可评,维持拒 + star_mismatch 分键
        (装载设计 §1.2 fail-closed 边界;P77 溢价表域外延未证不入)。"""
        m = _non_c1_member()
        base = CHARACTERS[m].cost
        low = next((lv for lv in range(1, 11)
                    if refresh_prob(lv, base) <= 0.0), None)
        assert low is not None, '锁前提:存在该费刷不出的等级'
        st = _st(gold=30, shop_cards=[_card(m, base * 3, star=2)],
                 bench=[_bc(m, slot=1)], level=low)
        sess = _sess()
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert _counters(sess).get('m2_stockpile_star_mismatch', 0) == 1

    def test_arm_baseline_injection_restores_rejection(self):
        """A/B 切换面反事实锁:比较子函数被测试侧 monkeypatch 关闭
        (fixtures.cw_ab 同一注入形)→ 同帧回到星过滤拒 +
        m2_stockpile_star_mismatch(臂 A 基线语义;生产代码零开关)。"""
        m = _non_c1_member()
        base = CHARACTERS[m].cost
        st = _st(gold=30, shop_cards=[_card(m, base * 3, star=2)],
                 bench=[_bc(m, slot=1)])
        sess = _sess()
        import unittest.mock as _mock
        with _mock.patch.object(shop, 'spot2_direct_out_card',
                                return_value=None):
            act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        assert _counters(sess).get('m2_stockpile_star_mismatch', 0) == 1


# ===== 缺口面3:s_reserve 拒绝对价载体 =====


class TestSRserveConsiderationCarrier:

    def test_reencounter_window_anchor_p77_table(self):
        """再遇窗锚(P77 §1.4 表:3费@L7 q=0.1357 → 窗≈7.4 帧;
        2费@L6 ≈7.9)——helper 直算 1/P(≥1 张/帧),超几何单一源。"""
        w37 = reencounter_window_frames(7, 3, held=0)
        assert abs(w37 - 7.37) <= 0.05, f'3费@L7 窗 {w37:.3f} ≠ 7.37'
        w26 = reencounter_window_frames(6, 2, held=0)
        assert abs(w26 - 7.90) <= 0.05, f'2费@L6 窗 {w26:.3f} ≠ 7.90'

    def test_consideration_helper_held_weighting_and_ceil(self):
        """对价累计 helper:held 折算(1★×1/2★×3)抬高剩余窗(持有越多
        牌库越薄,q 越低);输出 = ceil 窗帧整数(计数器 int 载体)。"""
        name = next(n for n in CHARACTERS
                    if CHARACTERS[n].cost == 3 and refresh_prob(7, 3) > 0)
        b = shop._s_reserve_remeet_frames
        f0 = b(7, [], [], _card(name, 3))
        f1 = b(7, [_bc(name, slot=1)], [], _card(name, 3))
        f2 = b(7, [_bc(name, slot=1, star=2)], [], _card(name, 3))
        assert f0 == math.ceil(reencounter_window_frames(7, 3, 0))
        assert f1 >= f0 and f2 >= f1, 'held 折算须单调抬窗'
        assert f2 == math.ceil(reencounter_window_frames(
            7, 3, 3)), '2★ 持有折算 3 基础副本'

    def test_rejection_wiring_lands_in_frame(self):
        """接线锁(合成帧):M6 面 s_reserve 拒帧 ⇒ 对价累计键同步落账
        (m6_s_reserve_reject 事件 + m6_s_reserve_remeet_frames_sum =
        ceil(再遇窗),窗值经 helper 单一源现算、不锁死数)。
        帧形 = 溢余带下界侧(gold ∈ (g*, s_reserve+cost)),空席让
        席位闸放行到金约束位。假局 e2e 扫描不可达申报:假局备战席恒满
        (m6_bench_full 为主导拒),s_reserve 位在席闸之后结构性少达——
        接线由本帧承载,分布面归 A/B 批读数(实测累计恒 0 如实申报)。"""

        from test.sr_od.app.currency_war._cw_helpers import (
            cw4_card as _h_card,
        )
        from test.sr_od.app.currency_war._cw_helpers import (
            cw4_session as _h_session,
        )
        st = _st(gold=52, shop_cards=[_h_card('填充件X', 3)], bench=[],
                 level=6)
        sess = _h_session(_comp())
        act = _decide(st, sess)
        assert not isinstance(act, BuyCard)
        cs = _counters(sess)
        assert cs.get('m6_s_reserve_reject', 0) == 1
        assert cs.get('m6_s_reserve_remeet_frames_sum', 0) == math.ceil(
            reencounter_window_frames(6, 3, 0)), \
            '对价累计 ≠ ceil(再遇窗)(载体量值破缺)'
