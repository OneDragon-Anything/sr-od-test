"""关店机械口 shop payload 清场锁(T-40;proj_buy_payload 跨轮残留收口)。

病理(run_20260918_063249 停局链):上轮买后 payload(空槽+残影)跨轮
残留,下轮开店帧实读新波 5 卡 → observe 失配安灯停局。根因 = 买后
logic 态的唯一清场写端在关店上报(report_action_close_shop_param 的
``leave_screen`` 离屏写),但生产链 CwActionCloseShopParam 被「终结不入序列」约定截在
决策驱动器外(decide_shop_screen 收尾 return,不进 apply),机械关店
只点按钮不喂 kernel。修法 = 关店机械口(cw_op_close_shop.close_shop)
两出口做 kernel 侧清场:点击已发出口 + 幂等已关出口(旧 miss 臂与
变体 observe 早退共享同一构造)。

锁四件事:
1. 点击已发出口:关店点击发出后 payload 置 None(left_screen);
2. 幂等已关出口:店已关 + 残留 payload 同样清(幂等修复);
3. 重开重洗采新:残留 payload 遇新波观察 = 失配路由命中(病理对照,
   capture 替身零停机);清场后同观察零失配、采新波;
4. 当轮买投影回归:买投影语义逐位不变(槽空置换+金扣+写端身份),
   清场只在 close_shop 时点发生,买后 close 前 payload 照常在屏。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import sr_od.application.currency_war.kernel.cw_game_state as game_state_mod
import sr_od.application.currency_war.operations.cw_op.cw_op_close_shop \
    as close_mod
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
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_op.cw_op_close_shop import (
    close_shop,
)

_LOGIC_SIG = ChannelSig(family='logic_action', actor='CwScreenBuyCards',
                        mode='compute', group_id='act:CwScreenBuyCards@1')
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


class _FakeOp:
    """close_shop 宿主替身:ctx 挂真容器 session;「收起」锚按剧本命中/缺席。"""

    def __init__(self, session: StrategySession, click_found: bool):
        self.ctx = SimpleNamespace(
            cw_match=SimpleNamespace(session=session))
        self._click_found = click_found

    def screenshot(self):
        return None

    def round_by_find_and_click_area(self, frame, screen_name, area_name):
        return SimpleNamespace(is_success=self._click_found)

    def round_success(self, msg=''):
        return SimpleNamespace(is_success=True, status='success')

    def round_retry(self, msg='', wait=0):
        return SimpleNamespace(is_success=False, status='retry')


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
    """点击已发出口:买投影后 payload 在屏 → close_shop 点击发出 →
    payload 置 None(evidence=left_screen 锁清场写端身份)。"""
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s: None)
    session, gs = _session_with_shop(['希儿', '花火', '黑塔', '丹恒', '停云'])
    report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿')), _LOGIC_SIG,
        executed=ShopActionExecuted(bought_count=1))
    assert gs.shop.value is not None, '前置:买后 payload 在屏(当轮事实)'
    assert len(shop_payload_content_cards(gs.shop.value)) == 4, \
        '前置:买走 1 张余 4 content(槽空置换语义)'

    close_shop(_FakeOp(session, click_found=True))

    assert gs.shop.value is None, '关店点击后 payload 离屏置 None(跨轮残留根除)'
    assert gs.shop.source == 'observation'
    assert gs.shop.evidence == 'left_screen', '清场写端身份 = leave_screen 口'


def test_close_shop_idempotent_exit_clears_stale_payload(monkeypatch):
    """幂等已关出口:「收起」不在(店已关)+ 残留 payload 同样清——
    旧 miss 臂与变体 observe 早退共享构造,一锁两覆盖。"""
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s: None)
    session, gs = _session_with_shop(['黑塔'])
    assert gs.shop.value is not None

    close_shop(_FakeOp(session, click_found=False))

    assert gs.shop.value is None, '已关出口同样清残留(幂等修复)'


# ===== 锁3 重开重洗采新(含病理对照)=====


def test_reopen_reshuffle_adopts_new_wave_without_mismatch(monkeypatch):
    """重开重洗采新:上半对照 = 残留 logic payload 遇新波观察 → 失配
    路由命中(capture 替身,病理形态入锁);下半 = 清场后同观察零失配、
    采新波。"""
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s: None)
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
    close_shop(_FakeOp(session2, click_found=True))
    gs2.observe(gs2.shop, fresh, evidence='shop_new_wave', sig=_OBS_SIG)
    assert calls == [], '清场后新波观察零失配(修法移除病理形态)'
    assert gs2.shop.value == fresh and gs2.shop.source == 'observation', \
        '开店帧新波采新(payload = 实读,source=observation)'


# ===== 锁4 当轮买投影回归 =====


def test_buy_projection_regression_within_visit(monkeypatch):
    """当轮买投影回归:买投影语义逐位不变(买走槽空置换+gold −单价+
    写端身份),清场只随 close_shop 发生,买后 close 前 payload 在屏。"""
    monkeypatch.setattr(close_mod.time, 'sleep', lambda s: None)
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

    close_shop(_FakeOp(session, click_found=True))
    assert gs.shop.value is None, 'close_shop 时点才清场'
