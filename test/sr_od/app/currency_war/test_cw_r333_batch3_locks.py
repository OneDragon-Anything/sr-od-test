# -*- coding: utf-8 -*-
"""r332/r333 行为锁(单文件;battle_loop streak+hp 收口)。"""
from __future__ import annotations

import inspect


def test_battle_loop_consumes_director_result() -> None:
    """r332:execute() 返回值被消费(连续失败→round_fail)。"""
    from sr_od.application.currency_war.operations import battle_loop
    src = inspect.getsource(battle_loop.CurrencyWarRunLoop)
    assert '_director_fail_streak' in src
    assert 'PrepDirector 连续失败' in src   # 告警语


def test_director_last_state_gated() -> None:
    """r333:director 写 last_state 前过 gated_hp(单写者 hp 同源)。"""
    from sr_od.application.currency_war import prep_director
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'gated_hp as _gh' in src
    assert 'st.hp = _gh(' in src


def test_substate_field_on_observation() -> None:
    """r333:PrepObservation.substate 字段(observe_full 消费端)。"""
    from sr_od.application.currency_war.prep_director import PrepObservation
    obs = PrepObservation()
    assert obs.substate == {}
    obs.substate = {'node_seq': True, 'shop_cards': False}
    assert obs.substate['shop_cards'] is False
