# -*- coding: utf-8 -*-
"""r290 current 左移优先测试(局20 node=reward 污染根修)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director


def test_left_shift_takes_priority() -> None:
    """r290:current 推断链改为左移优先(OCR 仅首帧兜底)。

    局20 实证:OCR 标签位置门拦不住相邻同类标签(r3 结算屏
    「战斗」vs current 读 reward)→ current 直读不可信;
    上帧 upcoming[0](左移)是干净推断。
    """
    src = inspect.getsource(prep_director.PrepDirector._probe_node_type)
    assert '_prev[0] if _prev else None' in src
    # 左移分支在 OCR 分支之前(r290 语义:优先级序)
    assert src.index('_prev[0]') < src.index("s.state == 'current'")


def test_ocr_fallback_only_when_no_shift() -> None:
    """OCR 只在左移无值时兜底(首帧)。"""
    src = inspect.getsource(prep_director.PrepDirector._probe_node_type)
    assert "if _direct is None:" in src
