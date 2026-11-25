"""遥测 run_id 跨秒时钟(测试 harness)。

run_id = 秒级时间戳(``telemetry/state.start_run``),两次铸造落在同一秒即同号。
生产里相邻两次相关铸造(上局收尾 → 下局开局 / loop 构造预铸 → 漏斗正铸)隔着
一次 app 运行或框架等待下限,必跨秒;测试把时序压到毫秒级后同秒碰撞会让
「新段 ≠ 旧段」判据退化为同值字符串假绿。本口把 telemetry state 模块的
``datetime`` 换成每次调用前进 2 秒的替身,显式造出跨秒前提——只影响 run_id
铸造与 ``_CURRENT_RUN_ID`` 同语句的时间源,状态流水行的 ``ts`` 用的是 kernel
侧自己的 ``datetime``,不受影响。

用法::

    advancing_run_clock(monkeypatch)   # 夹具或用例体开头调一次
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def advancing_run_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 ``telemetry.state.datetime`` 换成每次调用前进 2 秒的替身(monkeypatch 自动还原)。"""
    from sr_od.application.currency_war.telemetry import state as cw_state

    class _AdvancingDatetime:
        """``datetime.now`` 替身:每次调用前进 2 秒(真实时序压缩)。

        秒数进位到分:时钟单调递增、任意次调用不重号也不越界(纯秒字段
        +2 会在第 30 次调用越出 0–59 抛 ValueError,批量场景不可用)。
        """

        _elapsed: int = 0

        @staticmethod
        def now():
            _AdvancingDatetime._elapsed += 2
            from datetime import datetime as _real
            return _real(2026, 11, 25, 12, _AdvancingDatetime._elapsed // 60,
                         _AdvancingDatetime._elapsed % 60)

    _AdvancingDatetime._elapsed = 0
    monkeypatch.setattr(cw_state, 'datetime', _AdvancingDatetime)
