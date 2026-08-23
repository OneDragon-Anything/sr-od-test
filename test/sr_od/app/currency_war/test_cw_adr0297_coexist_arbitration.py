"""ADR-0297 刷新×追级并存仲裁回归锁:评分侧联动(采纳)+约束侧(备选)。

- 评分侧联动锁:金<refresh_starve_gold 时 refresh_ev 打折(采纳参数
  0.6/40 下恒负分不刷);金≥阈值全额 EV。
- 约束侧锁(注册 A/B 通道,默认关闭):局刷新预算上限触发/追级保留金
  触发(等级封顶后豁免)。
- 两通道同局共存:同一 arbitrate 裁决里刷新与升级都被采纳(并存而非
  二选一),且局刷新计数回写 session。
决策见 docs/develop/currency_war/decisions/0297-refresh-levelup-coexist-arbitration.md。
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    GameState,
    LevelUp,
    RefreshShop,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    _check_constraint,
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _refresh_cand(cost: int = 2) -> Candidate:
    return Candidate(action=RefreshShop(cost=cost), tag='refresh',
                     source='test')


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 45, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 100,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _refresh_cand_from_gen(state: GameState, sess: StrategySession
                           ) -> Candidate:
    """走生成器取真 refresh 候选(与生产同源)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        generate_candidates,
    )
    return [c for c in generate_candidates(state, sess, DEFAULT_REGISTRY)
            if c.tag == 'refresh'][0]


def test_starve_discount_makes_refresh_negative() -> None:
    """评分侧联动:金<40 时 0.6 折扣 → EV=1.5-2 恒负分(让位追级)。"""
    st = _state(gold=39, shop=[_card('占位件', faction='公司', cost=1)])
    sess = StrategySession()
    cand = _refresh_cand_from_gen(st, sess)
    val, bd = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    expect = DEFAULT_REGISTRY.refresh_ev \
        * DEFAULT_REGISTRY.refresh_starve_discount - 2
    assert val == expect and val < 0, (
        f'金<饥饿阈值刷新应恒负分(实际 {val},breakdown {bd})')


def test_starve_threshold_full_ev_above() -> None:
    """金≥40 无折扣:全额 refresh_ev-cost(早刷找件通道保留)。"""
    st = _state(gold=40, shop=[_card('占位件', faction='公司', cost=1)])
    sess = StrategySession()
    cand = _refresh_cand_from_gen(st, sess)
    val, _ = score_candidate(cand, st, sess, DEFAULT_REGISTRY)
    assert val == DEFAULT_REGISTRY.refresh_ev - 2, (
        f'金≥阈值应全额 EV(实际 {val})')


def test_game_cap_rejects_refresh() -> None:
    """约束侧·预算上限:局刷新已用尽 → refresh_budget 拒绝。"""
    reg = replace(DEFAULT_REGISTRY, refresh_game_cap=2,
                  levelup_reserve_gold=0, refresh_starve_discount=1.0)
    sess = StrategySession()
    sess.v2_refresh_used = 2
    st = _state(gold=50)
    reason = _check_constraint('refresh_budget', _refresh_cand(), st.copy(),
                               st, sess, reg, pending_bench=0)
    assert reason is not None and '预算' in reason
    # 未用尽放行
    sess.v2_refresh_used = 1
    assert _check_constraint('refresh_budget', _refresh_cand(), st.copy(),
                             st, sess, reg, pending_bench=0) is None


def test_levelup_reserve_rejects_refresh() -> None:
    """约束侧·追级保留金:等级未满+刷后金<保留金 → 拒;封顶豁免。"""
    reg = replace(DEFAULT_REGISTRY, refresh_game_cap=0,
                  levelup_reserve_gold=30, refresh_starve_discount=1.0)
    sess = StrategySession()
    st = _state(gold=31)     # 刷后 29 < 30
    reason = _check_constraint('refresh_budget', _refresh_cand(), st.copy(),
                               st, sess, reg, pending_bench=0)
    assert reason is not None and '保留金' in reason
    # 等级封顶:追级通道不存在,保留金豁免
    st_max = _state(gold=31, level=DEFAULT_REGISTRY.level_max)
    assert _check_constraint('refresh_budget', _refresh_cand(),
                             st_max.copy(), st_max, sess, reg,
                             pending_bench=0) is None


def test_two_channels_coexist_same_round() -> None:
    """两通道同局共存:同一裁决里升级+刷新都被采纳,计数回写。"""
    st = _state(gold=60, round_num=2)
    sess = StrategySession()
    scored = [
        (Candidate(action=LevelUp(cost=4), tag='levelup', source='test'),
         5.0, {}),
        (_refresh_cand(), 0.5, {}),
    ]
    res = arbitrate(scored, st, sess, DEFAULT_REGISTRY)
    tags = [c.tag for c, _v, _bd in scored]
    assert 'levelup' in tags and 'refresh' in tags
    assert any(isinstance(a, LevelUp) for a in res.actions), '升级通道应采纳'
    assert any(isinstance(a, RefreshShop) for a in res.actions), (
        '刷新通道应同局共存(非二选一)')
    assert getattr(sess, 'v2_refresh_used', 0) == 1, (
        '局刷新计数应回写 session(预算约束数据源)')


def test_coexist_initial_values() -> None:
    """ADR-0297 并存仲裁批初值锁(双窗+终验定;改动须重跑双窗+更新本锁)。"""
    assert DEFAULT_REGISTRY.refresh_starve_discount == 0.6
    assert DEFAULT_REGISTRY.refresh_starve_gold == 40
    assert DEFAULT_REGISTRY.refresh_game_cap == 0      # 约束侧默认关闭
    assert DEFAULT_REGISTRY.levelup_reserve_gold == 0
    assert 'refresh_budget' in DEFAULT_REGISTRY.constraints


def test_strategy_default_carries_coexist_registry() -> None:
    """默认策略注入并存参数(评分侧联动即生产行为)。"""
    s = DecisionV2Strategy()
    assert s.registry.refresh_starve_discount == 0.6
