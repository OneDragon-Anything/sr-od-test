"""买牌点击槽位解析锁(实机缺陷修复:牌行打洞后紧凑下标 ≠ 物理槽位)。

历史缺陷形态(实机局实证):游戏买入后不压缩剩余卡位(1 号槽空、余卡在
2-5 号槽),payload 是紧凑列表(空槽跳过)而点击按下标取固定槽坐标 →
全体点击右偏落空槽框,恒「Buy 未生效(卡面未变)」。修复语义 = 点击
坐标按牌自带物理槽号(slot,读链 read_shop_cards 写入)取 screen_info
「商店牌-N」中心;槽号缺省(0)退回紧凑下标映射(旧行为,sim/离线
构造与修复前旧档兼容)。
"""
from types import SimpleNamespace

import numpy as np

from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CwSimFrame,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op import cw_shop_action_ops
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    BuyCardOp,
    ShopExecEnv,
)
from test.sr_od.app.currency_war._cw_helpers import (
    cw4_box,
)

_RECT = (0, 0, 100, 150)


def _frame(v: int) -> np.ndarray:
    return np.full((150, 100, 3), v, dtype=np.uint8)


def _clicked_pts(monkeypatch, card: ShopCard, frame_cards: list) -> tuple:
    """执行一次 BuyCardOp,返回 (实际点击坐标列表, 槽位坐标表, 账本, 返回值)。

    买前/买后裁片帧不同(50 vs 220)→ buy_click_ineffective 判「已生效」,
    走完整记账路径;槽位坐标表 = 5 个可区分 Point 桩(x=100..500)。
    """
    monkeypatch.setattr(cw_shop_action_ops, '_area_rect',
                        lambda ctx, area, screen: SimpleNamespace(
                            x1=_RECT[0], y1=_RECT[1],
                            x2=_RECT[2], y2=_RECT[3]))
    monkeypatch.setattr(cw_shop_action_ops.time, 'sleep', lambda s: None)
    clicks: list = []
    shots = [_frame(50), _frame(220)]

    def _screenshot():
        return shots.pop(0) if shots else _frame(220)
    op = SimpleNamespace(
        screenshot=_screenshot,
        ctx=SimpleNamespace(controller=SimpleNamespace(
            click=lambda p: clicks.append(p))))
    action = BuyCard(card=card, reason='test')
    ledger = SimpleNamespace(
        total_buy=0, spend_executed=0, bought_names=[], buy_purchases=[],
        buy_unidentified=False)
    match = SimpleNamespace(session=SimpleNamespace(
        tracked_bench_chars=[], tracked_deployed=[], v3_intention=None))
    pts = [SimpleNamespace(x=100 * (i + 1), y=165) for i in range(5)]
    env = ShopExecEnv(op=op, match=match, config=None, click_pts=pts,
                      level_btn=None, refresh_btn=None, ledger=ledger,
                      state=cw4_box(CwSimFrame(bench=[],
                                                         shop=frame_cards)))
    ok = BuyCardOp(action).execute(env)
    return clicks, pts, ledger, ok


def _hole_row_cards(target: ShopCard) -> list:
    """打洞牌行桩:目标卡紧凑下标 0,但物理槽号在目标卡自身(slot 字段)。"""
    return [target]


class TestBuySlotClickResolution:

    def test_hole_row_clicks_card_own_slot(self, monkeypatch) -> None:
        """判别性场景:1 号槽空、目标卡物理在 3 号槽(payload 紧凑下标 0)
        → 点击 3 号槽坐标,不落 1 号空槽框(缺陷形态 = 恒落 pts[0])。"""
        card = ShopCard(x=0, name='翡翠', cost=1, star=1, slot=3)
        clicks, pts, ledger, ok = _clicked_pts(
            monkeypatch, card, _hole_row_cards(card))
        assert len(clicks) == 1 and clicks[0] is pts[2], \
            '点击坐标 = 牌自带槽号 3 的 screen_info 槽位中心'
        assert ok is True and ledger.total_buy == 1, \
            '生效路径完整(卡面已变 → 记账不跳过)'

    def test_slot_out_of_range_falls_back_compact(self, monkeypatch) -> None:
        """槽号越界(>click_pts 长度,脏档)→ 退紧凑下标(这里 = 0)。"""
        card = ShopCard(x=0, name='翡翠', cost=1, star=1, slot=6)
        clicks, pts, _, _ = _clicked_pts(
            monkeypatch, card, _hole_row_cards(card))
        assert len(clicks) == 1 and clicks[0] is pts[0], \
            '越界槽号 = 旧行为(紧凑下标 0 → 1 号槽)'

    def test_missing_slot_uses_compact_index(self, monkeypatch) -> None:
        """槽号缺省(0 = sim/离线构造)→ 按紧凑下标取坐标:目标在
        payload 下标 1 → 落 2 号槽(不是缺省兜底 pts[0])。"""
        target = ShopCard(x=0, name='杰帕德', cost=4, star=1, slot=0)
        filler = ShopCard(x=0, name='翡翠', cost=1, star=1, slot=0)
        clicks, pts, _, _ = _clicked_pts(
            monkeypatch, target, [filler, target])
        assert len(clicks) == 1 and clicks[0] is pts[1], \
            '缺槽号 = 紧凑下标映射(下标 1 → 2 号槽;payload 未流动则红)'
