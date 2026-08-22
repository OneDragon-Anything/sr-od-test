# -*- coding: utf-8 -*-
"""r290 current 左移优先测试(局20 node=reward 污染根修;r363 锚定版)。"""
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
    """OCR 只在 current 无值时兜底(首帧)。

    r363 锚定版:断言随结构演进取新形态——左移锚定轮次(防同轮
    超前)后,current 直读降为「current 无值才写」的兜底;旧断言
    `if _direct is None:` 是 r290 形态,r363 改为 getattr 判 None
    (语义不变:直读仅兜底)。
    """
    src = inspect.getsource(prep_director.PrepDirector._probe_node_type)
    assert "node_type_current', None) is None" in src
    # 兜底分支在左移分支之后(优先级序保持)
    assert src.index("node_type_current', None) is None") \
        > src.index('_prev[0]')
