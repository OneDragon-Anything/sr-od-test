"""接线锁:开局简报(HandleBriefing)遥测落账不得静默断链。

背景(W518 微批):HandleBriefing 读敌人词缀/首领候选集/敌人难度三样,
此前只进日志不进遥测——run_20260828_191254 的 exogenous.jsonl 0 条
briefing,「简报画面当时显示了什么」在证据链上是空白。修法 = 在读数后
补一行 cw_telemetry.record_exogenous(kind='briefing'),口径对齐
battle_loop 位面简报分支先例(r378b,同 kind、同 detail 风格,轮次 0)。

本锁钉住:HandleBriefing.handle 源码内存在 record_exogenous 落账调用
且 kind='briefing'——防后续重构把落账行删掉/改 kind 导致证据链再断。
只锁接线存在性,不锁 detail 内容分布(与测试纪律「锁不锁分布数值」同判据)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.operations.handlers import handle_briefing
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def test_handle_briefing_telemetry_wiring_in_source() -> None:
    """接线锁:简报 op 真调 record_exogenous(kind='briefing')(落盘点唯一源)。"""
    src = inspect.getsource(handle_briefing.HandleBriefing.handle)
    assert 'record_exogenous(' in src, 'HandleBriefing 未接 briefing 遥测落账(W518 断链)'
    assert "'briefing'" in src, "落账 kind 不是 'briefing'(须与 battle_loop 位面简报先例同口径)"
