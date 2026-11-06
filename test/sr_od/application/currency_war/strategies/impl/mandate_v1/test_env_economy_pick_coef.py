"""策略大师金币分支估值口径(通道 4 公式)测试(镜像 src =
strategies/impl/mandate_v1/env_economy.py 的通道 4;按被测面拆文件落位,
先例 = 同目录 test_invest_strategy.py〔已登记超限文件,只读复用不追加〕
④现金分组)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 6:通道 4 公式平移锁——第 k 张金额
coef×k(含本张口径,用户裁定 2026-10-26:首张 coef×1);期望现算自
估算注册表单一源(ENV_ECONOMY_ESTIMATES),禁手抄。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    ENV_ECONOMY_ESTIMATES,
    env_economy_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='EnvPickCoefTest')

_COEF = 2   # 与 kernel 双源同值锁一致(ENV_PICK_GRANTS 闸面另测)


def _fresh_gs() -> GameState:
    """独立容器(桩 session 宿主,弱引用表按宿主隔离,先例 =
    test_invest_strategy._fresh_gs)。"""
    return game_state_of(SimpleNamespace())


def _gs_with_held(held: int) -> GameState:
    """已持有 held 张策略的局态(开局桩形,node 未写 → (1,1) 语义)。"""
    gs = _fresh_gs()
    if held:
        gs.observe(gs.active_strategies, [f'持有卡{i}' for i in range(held)],
                   sig=_SIG_OBS)
    return gs


def test_channel4_first_pick_contributes_coef_times_one() -> None:
    """首张 coef×1 锁(T-46 设计 §4 锁 6):开局桩 held=0 → k ∈ {1,2,3}
    (_STRATEGY_PICK_PLANES 结构表),金额 = coef×k,首张项 = coef×1;
    期望 = Σ coef×k×w_k 现算(k1/k2 在当前位面权 1,k3 = P2 到达权点值),
    resolved=True(CI 端点同向为正)。"""
    p2 = ENV_ECONOMY_ESTIMATES['plane_arrival_p2'].value
    expected = _COEF * (1 * 1.0 + 2 * 1.0 + 3 * p2)
    value, resolved = env_economy_value('策略大师', _gs_with_held(0))
    assert resolved is True, '到达参数已登记,方向闭合'
    assert value == pytest.approx(expected, abs=1e-9), \
        f'金额 = coef×k(首张 coef×1): {value} vs {expected}'


def test_channel4_shift_lock_one_less_held_drops_exactly_one_term() -> None:
    """公式平移锁(T-46 设计 §4 锁 6 的判别面):held=1 → k ∈ {2,3},
    恰移除 k=1 项 = coef×1;若公式仍为旧口径 coef×(k−1),移除项 = 0,
    本断言即红——平移 (k−1)→k 的唯一判别断言。"""
    v0, _ = env_economy_value('策略大师', _gs_with_held(0))
    v1, _ = env_economy_value('策略大师', _gs_with_held(1))
    assert v0 - v1 == pytest.approx(float(_COEF), abs=1e-9), \
        f'移除项 = coef×1(非 0): {v0} - {v1}'
