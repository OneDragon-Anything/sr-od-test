"""概率校准的刷新预算(overlay B 契约锁组;ADR-0475)。

设计出处=ADR-0475(提案面原文见 .debug/temp/currency_war/
w645_proposal_v2/SPECS.md 提案 B-v2 节;落码判定=同目录 w720_overlay_reeval/
REPORT.md「提案 B:照旧实施」)。契约面:

- 帽腿:`min(6, ⌊(g−R*)/刷价⌋, ⌈−ln(1−q)·E_find⌉)`——q 为 registry
  真分位字段,E_find=cw_shop_odds.expected_refreshes_for_card(有限池精确期望);
- 归零腿:塌缩带(refresh_prob(当前级,目标费)/refresh_prob(峰值级,目标费)
  < registry.omega_collapse_ratio)→ 0,求值次序=先归零后帽;
- 空帧豁免:非锁定核帧(意向兜底链)归零判据恒 False(D1「空帧不缩供给」);
- 概率单一址:两腿概率源=既有牌池概率符号(cw_shop_odds),与分配器
  Π_refresh 估计器同源互指,禁第二概率口径。
"""
from __future__ import annotations

import dataclasses
import inspect
import math

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_ROLL_CAP,
    refresh_ev_budget,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_intention import intention_core

_REG = DEFAULT_REGISTRY


def _state(*, gold: int = 200, level: int = 5, hp: int = 80) -> GameState:
    """溢余帧工厂(塌缩/帽判据在非应急带常态溢余帧上判)。"""
    return GameState(
        plane=1, round_num=5, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2, deployed=[],
        bench=[None] * BENCH_CAPACITY, shop=[], node_type='battle',
        board={})


def _locked_session(cost_want: int) -> StrategySession:
    """锁定核 session 工厂:意向锁到「意向核心费用档 == cost_want」的
    第一条 comp 线(判据面只依赖核心费档,不依赖具体线)。"""
    for comp in COMP_LIBRARY:
        core = intention_core(comp)
        ch = CHARACTERS.get(core)
        if ch is not None and ch.cost == cost_want:
            sess = StrategySession()
            sess.v3_intention = IntentionState(
                phase='locked', locked_comp=comp.name)
            return sess
    raise AssertionError(f'无费用档 {cost_want} 的意向核心 comp(注册表漂移?)')


# --- 归零腿:塌缩带契约 -------------------------------------------------------


def test_collapse_band_zeroes_budget_on_locked_core() -> None:
    """塌缩带归零锁(ADR-0475):锁定 4 费核 ∧ 当前级 5(比值
    refresh_prob(5,4)/refresh_prob(峰值级,4)≈0.05 < ω=0.1)→ 预算 0
    (合法 0 帧第三类;金量式恒给 6,归零只能来自概率分量)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    assert refresh_ev_budget(st, sess) == 0


def test_collapse_judgment_strict_below_threshold() -> None:
    """ω 严格小于判据:比值恰等于阈值不归零(边界取「不归零」侧——
    归零是禁刷,宁松勿误杀;注入 ω=0.05 与比值 0.05 帧 → 不归零)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    reg = dataclasses.replace(_REG, omega_collapse_ratio=0.05)
    assert refresh_ev_budget(st, sess, reg) > 0


def test_eval_order_collapse_precedes_cap() -> None:
    """求值次序锁:塌缩带归零与帽取交前先判归零——金量式与帽都远大于 0
    的帧(g=200)预算为 0,只能由归零腿产生(次序颠倒不改变结果,锁钉
    「归零帧不受帽腿豁免」的契约形状)。"""
    st = _state(gold=200, level=5)
    sess = _locked_session(4)
    assert refresh_ev_budget(st, sess) == 0
    # 注入小 q(帽腿收紧)不改变归零结果
    reg = dataclasses.replace(_REG, refresh_find_quantile=0.9)
    assert refresh_ev_budget(st, sess, reg) == 0


# --- 空帧豁免:D1 契约 --------------------------------------------------------


def test_fallback_chain_frame_exempt_from_collapse() -> None:
    """空帧豁免锁(ADR-0475):同一塌缩形态帧(4 费档比值 0.05)在
    未锁定意向帧(兜底链,兜底 2 费非真目标)不归零——对假目标算塌缩比
    会误杀真目标(别的费档)搜索量(D1「空帧不缩供给」契约优先)。"""
    st = _state(gold=200, level=5)
    sess = StrategySession()          # 无锁定意向 → 兜底链空帧
    assert refresh_ev_budget(st, sess) > 0


# --- 帽腿:分位公式手算对拍 ----------------------------------------------------


def test_find_cap_quantile_formula_hand_recalc() -> None:
    """帽公式锁(ADR-0475):预算 = min(6, ⌊溢余/刷价⌋,
    ⌈−ln(1−q)·E_find⌉) 逐项手算对拍——E_find 直接调 cw_shop_odds
    (对拍侧与实现侧同源,公式锁钉的是闭合形状不是数值巧合)。注入
    q=0.05 使帽腿 <6 实际参与 min(默认 q=0.8 的帽在 E_find 放大量级下
    结构性不绑定,SPECS B-v2 §3 已声明)。"""
    from sr_od.application.currency_war.data.cw_shop_odds import (
        expected_refreshes_for_card,
    )
    st = _state(gold=200, level=6)
    sess = StrategySession()          # 兜底链 2 费:非塌缩带
    q = 0.05
    reg = dataclasses.replace(_REG, refresh_find_quantile=q)
    e_find = expected_refreshes_for_card(6, 2, target_star=2, owned=0)
    expect = min(REFRESH_ROLL_CAP, (200 - 50) // 2,
                 math.ceil(-math.log(1.0 - q) * e_find))
    assert expect < REFRESH_ROLL_CAP   # 前置:帽腿确实参与(非恒真锁)
    assert refresh_ev_budget(st, sess, reg) == expect


def test_budget_domain_stays_within_roll_cap() -> None:
    """预算边界锁(ADR-0475):任意 (level, q, ω) 注入组合下预算 ∈
    [0, REFRESH_ROLL_CAP](帽/归零只收紧不放大;6 刷帽单一源不变)。"""
    import itertools
    sess = StrategySession()
    for level, q, omega in itertools.product((4, 6, 8), (0.5, 0.8, 0.9),
                                             (0.05, 0.1, 0.3)):
        reg = dataclasses.replace(_REG, refresh_find_quantile=q,
                                  omega_collapse_ratio=omega)
        st = _state(gold=200, level=level)
        b = refresh_ev_budget(st, sess, reg)
        assert 0 <= b <= REFRESH_ROLL_CAP


# --- 概率单一址:与分配器同源互指 ----------------------------------------------


def test_single_probability_source_no_second_odds_address() -> None:
    """概率单一址锁(ADR-0475;W720 互指条款):两腿都消费
    cw_shop_odds 的既有概率符号,禁第二概率口径——行为证明:把
    expected_refreshes_for_card 换哨兵值,帽腿随之变;把 refresh_prob
    换 0,归零腿随之触发。实现侧若自建概率表,本锁两段都会翻。"""
    import sr_od.application.currency_war.data.cw_shop_odds as odds
    st = _state(gold=200, level=6)
    sess = StrategySession()

    orig_e = odds.expected_refreshes_for_card
    odds.expected_refreshes_for_card = (
        lambda level, cost, target_star, owned=0, non_target_taken=0: 0.5)
    try:
        b = refresh_ev_budget(st, sess, _REG)
        assert b == min(REFRESH_ROLL_CAP, 75, math.ceil(-math.log(0.2) * 0.5))
    finally:
        odds.expected_refreshes_for_card = orig_e

    st5 = _state(gold=200, level=5)
    sess5 = _locked_session(4)
    orig_p = odds.refresh_prob
    odds.refresh_prob = lambda level, cost: 0.0
    try:
        assert refresh_ev_budget(st5, sess5, _REG) == 0
    finally:
        odds.refresh_prob = orig_p


def test_allocator_refresh_estimator_same_odds_source() -> None:
    """分配器互指锁(ADR-0475;W720 统一纪律②):B 的归零腿概率源与
    分配器 Π_refresh 估计器(``allocator._refresh_dpeff_estimate``)同址
    ——两侧都从 cw_shop_odds 取 refresh_prob(结构锁:源码含同一 import
    单一址;行为级同源证明见上锁)。"""
    from sr_od.application.currency_war.decision.decision_v2 import allocator
    src = inspect.getsource(allocator._refresh_dpeff_estimate)
    assert 'cw_shop_odds import refresh_prob' in src
    from sr_od.application.currency_war.kernel import cw_economy
    src_e = inspect.getsource(cw_economy)
    assert 'cw_shop_odds import refresh_prob' in src_e
