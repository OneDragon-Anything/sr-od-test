"""OpenLightConeReplaceOp(打开替换光锥列表)节点流程测试。

测试层级声明:节点流程为打桩流程测试(画面判定 / 查找区域 / 点击打桩);
交互链本体(TAB 点替换 → 进列表)由生产实机摸底覆盖,不在此重复。

锁的内容(出处 src/sr_od/operations/open_light_cone_replace.py):
- 入口画面级判定:TAB 起点点「替换」按钮;已在列表幂等不再点按钮;
  异常画面显式失败(前置导航缺失);
- 点按钮后的画面转移由下轮画面判定确认(区域 until 有同位形近误判面);
- 打开后滚回列表顶(每轮一次拖拽,轮间画面判定兜底),OPENED 结束。
"""

from __future__ import annotations

import numpy as np
import pytest

from sr_od.operations import open_light_cone_replace as open_module
from sr_od.operations.open_light_cone_replace import OpenLightConeReplaceOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _NoWindowOpenLightConeReplace(OpenLightConeReplaceOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        OpenLightConeReplaceOp.__init__(self, ctx)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_open_from_tab_and_already_open(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TAB 起点:点「替换」按钮 → 画面判定确认进列表 → 滚顶 → OPENED;
    已在列表起点:幂等不再点按钮,直接滚顶 → OPENED;异常画面 → 显式失败。"""
    from one_dragon.base.screen.screen_utils import FindAreaResultEnum

    op = _NoWindowOpenLightConeReplace(test_context)

    scene = {'screen': 'tab'}  # 当前画面场景:tab(TAB 页) / replace(替换界面)

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '光锥-替换' if scene['screen'] == 'replace' else '角色-光锥'

    drags: list = []
    clicks: list = []

    def _fake_click(pos, **kwargs):
        clicks.append(pos)
        y = pos.y if hasattr(pos, 'y') else pos.center.y
        if y > 900:  # 底部「替换」按钮
            scene['screen'] = 'replace'

    monkeypatch.setattr(OpenLightConeReplaceOp, 'check_and_update_current_screen',
                        _fake_check_screen)
    monkeypatch.setattr(open_module.screen_utils, 'find_area',
                        lambda *args, **kwargs: FindAreaResultEnum.TRUE)
    monkeypatch.setattr(test_context.controller, 'click', _fake_click)
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda *args, **kwargs: drags.append(1))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    # TAB 起点:全链 execute → OPENED(点按钮 1 次 + 滚顶 4 次拖拽)
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(op.ctx, op)
    assert result.success and result.status == 'OPENED'
    assert len(clicks) == 1, 'TAB 起点应点击一次替换按钮'
    assert len(drags) == 4, f'打开后应滚顶 4 次拖拽,实际 {len(drags)}'

    # 已在列表起点:幂等不再点按钮,滚顶后 OPENED
    scene['screen'] = 'replace'
    op_already = _NoWindowOpenLightConeReplace(test_context)
    drags.clear()
    clicks.clear()
    enter_running_state(op_already.ctx)
    try:
        with fast_sleep(op_already):
            result = op_already.execute()
    finally:
        reset_running_state(op_already.ctx, op_already)
    assert result.success and result.status == 'OPENED'
    assert len(clicks) == 0, '已在列表不应再点按钮'
    assert len(drags) == 4, f'已在列表仍应滚顶,实际 {len(drags)}'

    # 异常画面:入口显式失败
    op_bad = _NoWindowOpenLightConeReplace(test_context)
    monkeypatch.setattr(OpenLightConeReplaceOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '主界面')
    enter_running_state(op_bad.ctx)
    try:
        with fast_sleep(op_bad):
            result = op_bad.check_entry()
    finally:
        reset_running_state(op_bad.ctx, op_bad)
    assert not result.is_success, '异常画面入口应显式失败'
    assert '不在光锥 TAB' in (result.status or '')
