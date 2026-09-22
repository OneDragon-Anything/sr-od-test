"""关店机械口 shop payload 清场锁(T-40 收编面;proj_buy_payload 跨轮残留收口)。

病理(run_20260918_063249 停局链):上轮买后 payload(空槽+残影)跨轮
残留,下轮开店帧实读新波 5 卡 → observe 失配安灯停局。根因 = 买后
logic 态的唯一清场写端在关店上报(report_action_close_shop_param 的
``leave_screen`` 离屏写)。现役修法 = 关店执行位收编进动作 op
(``CwActionCloseShopOp`` 执行体,关店编排壳退役):帧上找「按钮-收起」
miss = 店已关(幂等,无动作可发)/ 命中 = 点击 + 固定等待,两出口同调
清场上报。

锁四件事:
1. 点击已发出口:关店点击发出后 payload 置 None(left_screen);
2. 幂等已关出口:店已关 + 残留 payload 同样清(幂等修复);
3. 重开重洗采新:残留 payload 遇新波观察 = 失配路由命中(病理对照,
   capture 替身零停机);清场后同观察零失配、采新波;
4. 当轮买投影回归:买投影语义逐位不变(槽空置换+金扣+写端身份),
   清场只在关店动作时点发生,买后 close 前 payload 照常在屏。

驱动方式 = 真类实例 + 节点函数直驱,点击判定桩化(先例 =
test_cw_screen_two_node_family)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war._cw_helpers import Area

import sr_od.application.currency_war.kernel.cw_game_state as game_state_mod
import sr_od.application.currency_war.operations.cw_op.cw_close_shop_action as close_mod
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopActionExecuted,
    ShopPayload,
    ShopSlot,
    game_state_of,
    shop_payload_content_cards,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    CwActionCloseShopParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_close_shop_action import (
    CwActionCloseShopOp,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                        mode='compute', group_id='act:CwScreenShop@1')
_OBS_SIG = ChannelSig(family='obs', actor='cw_observation',
                      screen='货币战争-备战-开商店', mode='read')


def _card(name: str, slot: int = 1) -> ShopCard:
    return ShopCard(x=slot, slot=slot, name=name, faction='?', cost=3,
                    star=1)


def _payload(names: list[str]) -> ShopPayload:
    """5 槽定长 payload:names 依序填 content 槽,余槽 empty。"""
    cards = [ShopSlot(kind='content', card=_card(n, i + 1))
             for i, n in enumerate(names)]
    cards += [ShopSlot(kind='empty') for _ in range(5 - len(cards))]
    return ShopPayload(cards=cards, refresh_probs={})


class _FakeCtx:
    """动作 op 构造所需最小 ctx 面(cw_match = 容器 session 宿主)。"""

    def __init__(self, session: StrategySession) -> None:
        self.cw_match = SimpleNamespace(session=session)
        self.run_context = None


def _close_op(session: StrategySession, click_found: bool,
              monkeypatch: pytest.MonkeyPatch) -> CwActionCloseShopOp:
    """真类实例 + 点击判定桩化:「按钮-收起」按剧本命中/缺席;
    关店动画等待走模块 time 桩。"""
    op = CwActionCloseShopOp(_FakeCtx(session), CwActionCloseShopParam(),
                             env=SimpleNamespace())
    monkeypatch.setattr(op, 'screenshot', lambda: None)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda frame, s, a: Area(click_found))
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s_: None)
    return op


def _session_with_shop(names: list[str], gold: int | None = 30):
    """带在屏 payload 的容器 session(payload/gold 经 logic 直写喂入)。"""
    session = StrategySession()
    gs = game_state_of(session)
    gs.write_logic(gs.shop, _payload(names), produced_by='test',
                   sig=_LOGIC_SIG)
    if gold is not None:
        gs.write_logic(gs.gold, gold, produced_by='test', sig=_LOGIC_SIG)
    return session, gs


# ===== 锁1/2 关店两出口清场 =====


def test_close_shop_click_clears_stale_buy_payload(monkeypatch):
    """点击已发出口:买投影后 payload 在屏 → 关店动作执行体点击发出 →
    payload 置 None(evidence=left_screen 锁清场写端身份)。"""
    session, gs = _session_with_shop(['希儿', '花火', '黑塔', '丹恒', '停云'])
    report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿')), _LOGIC_SIG,
        executed=ShopActionExecuted(bought_count=1))
    assert gs.shop.value is not None, '前置:买后 payload 在屏(当轮事实)'
    assert len(shop_payload_content_cards(gs.shop.value)) == 4, \
        '前置:买走 1 张余 4 content(槽空置换语义)'

    rr = _close_op(session, click_found=True, monkeypatch=monkeypatch).run()

    assert rr.is_success, '终结动作两出口均 round_success(机械交回)'
    assert gs.shop.value is None, '关店点击后 payload 离屏置 None(跨轮残留根除)'
    assert gs.shop.source == 'observation'
    assert gs.shop.evidence == 'left_screen', '清场写端身份 = leave_screen 口'


def test_close_shop_idempotent_exit_clears_stale_payload(monkeypatch):
    """幂等已关出口:「收起」不在(店已关)+ 残留 payload 同样清——
    幂等修复回归(已关残留同样陈旧)。"""
    session, gs = _session_with_shop(['黑塔'])
    assert gs.shop.value is not None

    rr = _close_op(session, click_found=False, monkeypatch=monkeypatch).run()

    assert rr.is_success, '幂等已关 = 无动作可发,回执后终结交回'
    assert gs.shop.value is None, '已关出口同样清残留(幂等修复)'


# ===== 锁3 重开重洗采新(含病理对照)=====


def test_reopen_reshuffle_adopts_new_wave_without_mismatch(monkeypatch):
    """重开重洗采新:上半对照 = 残留 logic payload 遇新波观察 → 失配
    路由命中(capture 替身,病理形态入锁);下半 = 清场后同观察零失配、
    采新波。"""
    calls: list[dict] = []

    def _capture(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(game_state_mod, '_route_logic_mismatch', _capture)
    fresh = _payload(['卡A', '卡B', '卡C', '卡D', '卡E'])

    # 上半(病理对照):上轮残影 payload + 新波观察 → 失配路由命中
    session, gs = _session_with_shop(['黑塔'])
    gs.observe(gs.shop, fresh, evidence='shop_new_wave', sig=_OBS_SIG)
    assert len(calls) == 1 and calls[0]['field_name'] == 'shop', \
        '对照:残留 logic payload 遇新波实读路由失配(安灯停局病理形态)'

    # 下半(修法):同残影起点 → 关店清场 → 新波观察零失配采新
    calls.clear()
    session2, gs2 = _session_with_shop(['黑塔'])
    _close_op(session2, click_found=True, monkeypatch=monkeypatch).run()
    gs2.observe(gs2.shop, fresh, evidence='shop_new_wave', sig=_OBS_SIG)
    assert calls == [], '清场后新波观察零失配(修法移除病理形态)'
    assert gs2.shop.value == fresh and gs2.shop.source == 'observation', \
        '开店帧新波采新(payload = 实读,source=observation)'


# ===== 锁4 当轮买投影回归 =====


def test_buy_projection_regression_within_visit(monkeypatch):
    """当轮买投影回归:买投影语义逐位不变(买走槽空置换+gold −单价+
    写端身份),清场只随关店动作发生,买后 close 前 payload 在屏。"""
    session, gs = _session_with_shop(['希儿', '花火', '黑塔', '丹恒', '停云'])

    report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿')), _LOGIC_SIG,
        executed=ShopActionExecuted(bought_count=1))

    assert gs.gold.value == 27, 'gold: 30 −单价 3 = 27(买投影照常)'
    assert gs.shop.value is not None, \
        '当轮买后 payload 在屏(清场未提前触发,决策循环在屏前置保持)'
    assert len(shop_payload_content_cards(gs.shop.value)) == 4, \
        '买走槽空置换(5 槽定长,余 4 content)'
    assert gs.shop.evidence == 'proj_buy_payload', '买投影写端身份保持'

    _close_op(session, click_found=True, monkeypatch=monkeypatch).run()
    assert gs.shop.value is None, '关店动作时点才清场'
