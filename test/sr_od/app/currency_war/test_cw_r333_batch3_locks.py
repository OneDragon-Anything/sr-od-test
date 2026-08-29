# -*- coding: utf-8 -*-
"""r332/r333 行为锁(单文件;battle_loop streak+hp 收口)。

(原 test_battle_loop_consumes_director_result 已并入
test_cw_r337_r332_behavior::test_source_has_real_wiring——同断言逐字
重复 + 5 连败行为锁更全;原 test_substate_field_on_observation 已并入
test_cw_r331_fixture 真 fixture 的 substate 可读性断言。重复构成删并
理由(README 纪律 8)。)"""
from __future__ import annotations

import inspect


def test_director_last_state_gated() -> None:
    """r333:director 写 last_state 前过 gated_hp(单写者 hp 同源)。"""
    from sr_od.application.currency_war import prep_director
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'gated_hp as _gh' in src
    assert 'st.hp = _gh(' in src
