# -*- coding: utf-8 -*-
"""ADR-0297 刷新×追级并存仲裁锁(W126/ADR-0349 语义迁移版)。

原锁族(评分侧饥饿折扣/约束侧预算上限/追级保留金)已随步③ 切调度
整体退场——refresh 附庸闸删除,并存由 V_D 批口径(概率窗二分:goal
说 level_up 时 D 让位)与升级 EV 总账自然裁决。本文件保留:
- 两通道同局共存(同一裁决里升级+刷新都被采纳——D 是一等通道);
- 退场静态断言(旧字段不再存在,防复辟)。
决策见 docs/develop/currency_war/decisions/0297-refresh-levelup-coexist-arbitration.md
与 0349(W126 步③)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    LevelUp,
    RefreshShop,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
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


def test_two_channels_coexist_same_round() -> None:
    """两通道同局共存:同一裁决里升级+刷新都被采纳(注入分,锁仲裁
    层不互斥——D 是一等花钱通道,与升级非二选一)。"""
    st = _state(gold=60, round_num=2)
    sess = StrategySession()
    scored = [
        (Candidate(action=LevelUp(cost=4), tag='levelup', source='test'),
         5.0, {}),
        (_refresh_cand(), 0.5, {}),
    ]
    res = arbitrate(scored, st, sess, DEFAULT_REGISTRY)
    assert any(isinstance(a, LevelUp) for a in res.actions), '升级通道应采纳'
    assert any(isinstance(a, RefreshShop) for a in res.actions), (
        '刷新通道应同局共存(非二选一)')


def test_vassal_gates_retired() -> None:
    """W126/ADR-0349 退场静态断言:refresh 附庸闸字段与约束不再存在
    (防复辟——评分/约束里再出现常量 EV 刷新门即红)。"""
    for field in ('refresh_ev', 'refresh_max_round', 'refresh_min_gold',
                  'refresh_starve_discount', 'refresh_starve_gold',
                  'refresh_game_cap', 'levelup_reserve_gold',
                  'form_refresh_ev', 'form_refresh_max_round',
                  'form_refresh_min_gold', 'form_refresh_engines_target'):
        assert not hasattr(DEFAULT_REGISTRY, field), field
    assert 'refresh_budget' not in DEFAULT_REGISTRY.constraints
    # D 让位语义由 V_D 承载:goal 说 level_up(窗外)→ vd_refresh_score
    # 返回 None(评分侧回负分),见 test_cw_w126_switch_dispatch
