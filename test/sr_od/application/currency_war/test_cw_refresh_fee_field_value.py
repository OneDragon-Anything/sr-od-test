"""刷新刷价 Field 读口回归锁(2026-09-15 04:37 实机停局事故)。

事故形态:RefreshShopOp.execute 刷价读数 ``state.shop_refresh_cost or
基价`` ——商店 env 容器化(W6 波 4 读者切换)后该属性是 GameState 容器的
Field 载体而非裸值,Field 恒真值 → ``or`` 恒取 Field →
``ledger.spend_executed += Field`` TypeError,实机本 session 首次刷新
点击即崩整局。修 = 走 ``.value`` 读口(与 sim/budget 域既有读式同款),
未观察/0 回退基价(ADR-0456 实付恒基价的记账口径不变)。

锁两件事:
1. 刷价 Field 未观察(接管新容器常态,值 None)→ 不炸,花销账记基价
   (事故本形);
2. 刷价 Field 现值在场 → 花销账记现值(读现值意图不因修法丢失)。
"""
from __future__ import annotations

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_economy import REFRESH_COST_BASE
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionRefreshShopParam
from sr_od.application.currency_war.operations.cw_op.cw_refresh_shop_action import (
    CwActionRefreshShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopExecEnv,
    ShopVisitLedger,
)


class _FakeController:
    def click(self, pos) -> None:
        pass


class _FakeCtx:
    def __init__(self) -> None:
        self.controller = _FakeController()
        self.cw_match = None
        self.run_context = None
        self.screen_loader = None


class _FakeOp:
    """execute 所需最小 op 面:首动作段读走容器(零 OCR)、截图桩 None
    (刷后牌面读在 try 内,异常被吞不阻塞)。"""

    def __init__(self) -> None:
        self.ctx = _FakeCtx()

    def screenshot(self):
        return None


def _env(state, ledger: ShopVisitLedger) -> ShopExecEnv:
    return ShopExecEnv(
        op=_FakeOp(), match=None, config=None, click_pts=[],
        level_btn=Point(0, 0), refresh_btn=Point(1603, 479),
        ledger=ledger, state=state)


def test_refresh_fee_unobserved_field_falls_back_to_base(monkeypatch):
    """事故本形:刷价 Field 未观察(None)→ 记基价,不再 TypeError。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)   # 新容器:shop_refresh_cost 未观察
    ledger = ShopVisitLedger()

    _env_ = _env(state, ledger)
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == REFRESH_COST_BASE
    assert ledger.total_refresh == 1
    assert ledger.did_refresh is True


def test_refresh_fee_observed_value_is_used(monkeypatch):
    """刷价 Field 现值在场 → 记现值(读现值意图不因修法丢失)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)   # 点击后固定等待
    session = StrategySession()
    state = game_state_of(session)
    state.observe(state.shop_refresh_cost, 3,
                  sig=ChannelSig(family='obs', actor='cw_observation'))
    ledger = ShopVisitLedger()

    _env_ = _env(state, ledger)
    assert CwActionRefreshShopOp(_env_.op.ctx, CwActionRefreshShopParam(),
                                 env=_env_).run().is_success

    assert ledger.spend_executed == 3
