"""备战屏观察上报测试(``kernel/cw_screen_report/prep.py`` 的合成确认浮层域)。

锁的设计约定(合成确认浮层读数经 ``report_screen_prep_obs`` 上传 game state):

- 干净帧上报不抛,字段值为 ``'none'``(状态容器的观察写入拒绝 ``None``,所以
  「本帧确认无浮层」必须用 ``'none'`` 才写得进去);已是 ``'none'`` 再报不重复写
  ——每次写入都落一条带全量快照的流水行,干净帧每次备战访问都写会让流水白白变胖;
- 在场帧上报后字段值 = 读数结构(dict);
- 本帧未读(歧义 / 有候选但配不成对 / 商店开着的帧,调用方留 ``None``)不写,
  字段留着上一帧的值。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_screen_report.prep import (
    CwScreenPrepObs,
    report_screen_prep_obs,
)

_PRESENT_READING: dict = {
    'ok_xy': (1821, 402), 'cancel_xy': (1707, 402), 'panel_rect': [1597, 299, 1872, 436],
    'inputs': [{'name': '轮滑鞋', 'conf': 0.9, 'cx': 1632, 'cy': 328},
               {'name': '折叠小刀', 'conf': 0.87, 'cx': 1731, 'cy': 328}],
    'product': {'name': '火力风暴潮', 'conf': 0.64, 'cx': 1838, 'cy': 325},
}


def _count_writes(monkeypatch: pytest.MonkeyPatch, gs) -> list[object]:
    """包一层 ``gs.observe`` 记下每次写入的值(上报函数有没有发起写入,只能从这里看)。"""
    writes: list[object] = []
    real_observe = gs.observe

    def observe(target, value, **kwargs) -> None:
        writes.append(value)
        real_observe(target, value, **kwargs)

    monkeypatch.setattr(gs, 'observe', observe)
    return writes


def test_clean_frame_reports_none_without_raising(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """干净帧:上报不抛,字段值为 'none';已是 'none' 再报不重复写。"""
    gs = game_state_of(SimpleNamespace())
    assert gs.synthesis_overlay.value is None   # 开局 = 未观察
    writes = _count_writes(monkeypatch, gs)

    report_screen_prep_obs(gs, CwScreenPrepObs(synthesis_overlay='none'))
    assert gs.synthesis_overlay.value == 'none' and writes == ['none']

    report_screen_prep_obs(gs, CwScreenPrepObs(synthesis_overlay='none'))
    assert gs.synthesis_overlay.value == 'none' and writes == ['none']


def test_present_frame_reports_reading_and_unread_frame_keeps_it() -> None:
    """在场帧:字段值 = 读数结构。随后一帧未读(None)不写,字段留着读数结构。"""
    gs = game_state_of(SimpleNamespace())

    report_screen_prep_obs(gs, CwScreenPrepObs(synthesis_overlay=_PRESENT_READING))
    assert gs.synthesis_overlay.value == _PRESENT_READING

    report_screen_prep_obs(gs, CwScreenPrepObs(synthesis_overlay=None))
    assert gs.synthesis_overlay.value == _PRESENT_READING
