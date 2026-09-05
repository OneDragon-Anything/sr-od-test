"""买卡点击生效性检出锁(第十八局 p2r7 停场修复,g_20260905_175220):
点击发出而金差≈0(执行未生效)形态的执行侧闭环——买后同 rect 卡面
复采,未离场 = 未生效 ⇒ 账不计入(bought_names/purchases/spend 均不记,
防 pixel-diff 假配对)+ buy_click_ineffective 分键留证。
"""
from types import SimpleNamespace

import numpy as np

from sr_od.application.currency_war.kernel.cw_state import BuyCard, GameState, ShopCard
from sr_od.application.currency_war.operations.cw_op import cw_shop_action_ops
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    BuyCardOp,
    ShopExecEnv,
    buy_click_ineffective,
)

_RECT = (0, 0, 100, 150)


def _frame(v: int) -> np.ndarray:
    return np.full((150, 100, 3), v, dtype=np.uint8)


def _capture(monkeypatch) -> list[dict]:
    rows: list[dict] = []
    from sr_od.application.currency_war.telemetry import defects
    monkeypatch.setattr(defects, 'record_defect',
                        lambda *a, **kw: rows.append({'args': a, **kw}))
    return rows


def _setup(monkeypatch, before: np.ndarray, after: np.ndarray):
    monkeypatch.setattr(cw_shop_action_ops, '_area_rect',
                        lambda ctx, area, screen: SimpleNamespace(
                            x1=_RECT[0], y1=_RECT[1],
                            x2=_RECT[2], y2=_RECT[3]))
    monkeypatch.setattr(cw_shop_action_ops.time, 'sleep', lambda s: None)
    shots = {'frames': [before, after]}

    def _screenshot():
        return shots['frames'].pop(0) if len(shots['frames']) > 1 \
            else shots['frames'][-1]
    op = SimpleNamespace(
        screenshot=_screenshot,
        ctx=SimpleNamespace(controller=SimpleNamespace(click=lambda p: None)))
    card = ShopCard(x=50, name='杰帕德', cost=4, star=1)
    action = BuyCard(card=card, reason='m2_stockpile')
    ledger = SimpleNamespace(
        total_buy=0, spend_executed=0, bought_names=[], buy_purchases=[],
        buy_unidentified=False, total_sell=0, total_level=0, total_refresh=0,
        refresh_skipped=0, refresh_attempted=0, refresh_board_changed=0,
        plan_truncated=False)
    match = SimpleNamespace(session=SimpleNamespace(
        tracked_bench_chars=[], tracked_deployed=[], v3_intention=None))
    env = ShopExecEnv(op=op, match=match, config=None, click_pts=[],
                      level_btn=None, refresh_btn=None, ledger=ledger,
                      state=GameState(bench=[]))
    rows = _capture(monkeypatch)
    BuyCardOp(action).execute(env)
    return ledger, rows, match


class TestBuyClickIneffective:

    def test_identical_card_means_ineffective(self):
        """同 rect 卡面逐像素相同 ⇒ 未生效(卡未离场)。"""
        assert buy_click_ineffective(_frame(50), _frame(50)) is True

    def test_changed_card_means_effective(self):
        """卡面离场(区域内容大变)⇒ 生效判定为 False。"""
        assert buy_click_ineffective(_frame(50), _frame(220)) is False

    def test_missing_crop_fails_open(self):
        """裁片缺失/形状不等 ⇒ False(不可判不污账,保持既有记账)。"""
        assert buy_click_ineffective(None, _frame(50)) is False
        assert buy_click_ineffective(_frame(50), None) is False

    def test_ineffective_buy_skips_ledger_and_records(self, monkeypatch):
        """执行器接线:未生效 ⇒ 账不计入(total_buy/bought_names/spend 均零)
        + buy_click_ineffective 分键在案。"""
        ledger, rows, _match = _setup(monkeypatch, _frame(50), _frame(50))
        assert ledger.total_buy == 0
        assert ledger.spend_executed == 0
        assert ledger.bought_names == []
        assert ledger.buy_purchases == []
        assert len(rows) == 1
        assert rows[0]['args'][1] == 'buy_click_ineffective'

    def test_effective_buy_keeps_ledger(self, monkeypatch):
        """对照:卡面离场 ⇒ 既有记账零回退(total_buy/bought_names 记入)。"""
        ledger, rows, _match = _setup(monkeypatch, _frame(50), _frame(220))
        assert ledger.total_buy == 1
        assert ledger.bought_names == ['杰帕德']
        assert rows == []
