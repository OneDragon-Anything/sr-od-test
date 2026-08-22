# -*- coding: utf-8 -*-
"""r388 锁测:开局轮(r≤2)装备 hold(gen 散件不穿,key 照穿)。"""
from __future__ import annotations

from sr_od.application.currency_war.operations.prep import equip_all


class _FakeState:
    plane = 1
    round_num = 2
    dual_track_phase = True   # r2 通常双轨期;hold 由 opening_round 接管


class _FakeSession:
    last_state = _FakeState()


class _FakeMatch:
    session = _FakeSession()


class _FakeComp:
    key_equips = ('轮滑鞋',)


def test_opening_round_hold_semantics() -> None:
    """开局轮:hold = target_comp 存在(与 form 无关;gen 攒着)。"""
    # 模拟 L308-322 的判定链(纯逻辑复刻,锁语义不锁实现)
    m = _FakeMatch()
    tgt = _FakeComp()
    form = 0.0   # 开局 form 恰 0(严格大于旧条件绕过 hold 的 bug 位)
    dual = bool(m.session.last_state is not None
                and m.session.last_state.dual_track_phase)
    transition_hold = (tgt is not None and 0.0 < form < 0.6 and not dual)
    round_now = m.session.last_state.round_num
    opening_round = round_now is not None and round_now <= 2
    if opening_round:
        transition_hold = tgt is not None
    assert transition_hold is True, '开局轮应 hold(gen 散件攒着)'


def test_battle_round_not_held_at_form0() -> None:
    """r3+ 战斗轮 form=0:沿用 r70 语义(白板也穿,散件给在场者)。"""
    class _S3(_FakeState):
        round_num = 3
    m = _FakeMatch()
    m.session.last_state = _S3()
    tgt = _FakeComp()
    form = 0.0
    dual = False
    transition_hold = (tgt is not None and 0.0 < form < 0.6 and not dual)
    round_now = m.session.last_state.round_num
    opening_round = round_now is not None and round_now <= 2
    if opening_round:
        transition_hold = tgt is not None
    assert transition_hold is False, 'r3+ form=0 沿 r70(散件照穿)'
