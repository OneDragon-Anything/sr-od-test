"""结算真值收口(settle_truth)锁:金币战后真值无条件入账替代方案。

背景(2026-09-18 回滚批):节点收入由游戏侧在结算屏展示前入账,bot 无
逻辑写端,账本与结算真值的差 = 预期边界收入而非推算 bug——经 observe
失配链则每场战斗必停局(全夜停局病态),吸收窗方案已回滚(吞真投影
bug 无第二道防线)。现行 = 结算点无条件收口 + 差值台账行留证。

锁依据 = GameState.settle_truth docstring(结论→出处→边界):
- 逻辑态账本 + 真值差 → boundary_income_credited 行 + 观察赢;
- 等值观察零新信息不产行;
- 观察态账本(无逻辑失配可比)→ 静默采新,不产行。
"""
from __future__ import annotations

import sr_od.application.currency_war.kernel.cw_game_state as gsm
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    register_sig_actors,
)

register_sig_actors('TestSigWriter')


def _sig():
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _spy_defects(monkeypatch) -> list[str]:
    """桩掉缺陷台账发射口,记录 kind 供断言(同 tracked_slot_star 模式)。"""
    kinds: list[str] = []

    def _rec(*args, **kwargs):
        kinds.append(kwargs.get('kind', ''))

    monkeypatch.setattr(gsm, '_emit_defect', _rec)
    return kinds


def test_diff_credits_with_ledger_row(monkeypatch) -> None:
    """逻辑态账本 7 + 结算真值 11 → 差 +4 落 boundary_income_credited 行,
    真值观察赢入账(不进三分流、不安灯)。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 7, sig=_sig())
    gs.write_logic(gs.gold, 9, produced_by='TestProj',
                   sig=ChannelSig(family='logic_action', actor='TestSigWriter',
                                  mode='compute'))
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11 and gs.gold.source == 'observation', \
        '结算真值无条件入账(观察赢)'
    assert kinds == ['boundary_income_credited'], \
        '差值落台账行留证(豁免 ≠ 消失同纪律)'


def test_equal_value_no_row(monkeypatch) -> None:
    """等值收口(账本与真值一致)→ 零新信息,不落台账行,来源照常翻
    观察态。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 11, sig=_sig())
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11
    assert kinds == [], '等值观察零新信息不产行'


def test_observation_source_adopts_silently(monkeypatch) -> None:
    """账本在观察态(无逻辑失配可比)→ 静默采新,不落差值行。"""
    kinds = _spy_defects(monkeypatch)
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.gold, 7, sig=_sig())
    gs.settle_truth(gs.gold, 11, sig=_sig())
    assert gs.gold.value == 11 and gs.gold.source == 'observation'
    assert kinds == [], '观察→观察采新无失配语义'
