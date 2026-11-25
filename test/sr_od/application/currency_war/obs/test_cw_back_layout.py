"""后排布局读链两处离线帧早退测试(``_observe_back_layout_to_container`` /
``_cv_confirm_readings``)。

锁的设计约定(契约正文 = 两函数 docstring):

- ``_observe_back_layout_to_container``:离线帧(``frame_is_live()`` 为假,即
  ``SrBackendContext.analyze`` 读图路径传进来的历史图)+ 有 session → ``gs.observe``
  零调用(一张旧图的档位不属于正在跑的那一局);实时帧照常写;
- ``_cv_confirm_readings``:离线帧零睡眠、返回 ``[首读, None, None]``(与「重读不可得」
  同形);实时帧照常隔 1s 重读两次。

零副作用约定:状态容器写经 ``game_state_of`` 打桩记录,不建真实 GameState。
"""
from __future__ import annotations

import types

import pytest

import sr_od.application.currency_war.obs.cw_back_layout as mod
from sr_od.context.frame_source import offline_frame


@pytest.fixture
def container_env(monkeypatch: pytest.MonkeyPatch) -> tuple:
    """状态容器夹具:``game_state_of`` 打桩返回记录型 gs;返回 (ctx, observe 调用列表)。"""
    import sr_od.application.currency_war.kernel.cw_game_state as gs_mod

    observes: list = []
    gs = types.SimpleNamespace(
        back_layout=object(),
        observe=lambda *a, **kw: observes.append((a, kw)),
    )
    monkeypatch.setattr(gs_mod, 'game_state_of', lambda session: gs)
    ctx = types.SimpleNamespace(cw_match=types.SimpleNamespace(session=object()))
    return ctx, observes


def test_observe_back_layout_offline_skips_container_write(container_env) -> None:
    """离线帧 + 有 session:gs.observe 零调用;实时帧照常写。"""
    ctx, observes = container_env
    with offline_frame():
        mod._observe_back_layout_to_container(ctx, 7, 7)
    assert observes == []
    mod._observe_back_layout_to_container(ctx, 7, 7)
    assert len(observes) == 1
    args, kwargs = observes[0]
    assert args[1] == 7 and kwargs['sig'].actor == 'cw_back_layout'


def test_cv_confirm_readings_offline_no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """离线帧:零睡眠,返回 [首读, None, None];实时帧照常隔 1s 重读两次。"""
    import time as time_mod

    sleeps: list = []
    monkeypatch.setattr(time_mod, 'sleep', lambda s: sleeps.append(s))
    monkeypatch.setattr(mod, 'cv_back_slots', lambda scr: 7)
    ctx = types.SimpleNamespace(screenshot=lambda: object())

    with offline_frame():
        assert mod._cv_confirm_readings(ctx, object(), 7, 6) == [7, None, None]
    assert sleeps == []

    assert mod._cv_confirm_readings(ctx, object(), 7, 6) == [7, 7, 7]
    assert sleeps == [1.0, 1.0]
