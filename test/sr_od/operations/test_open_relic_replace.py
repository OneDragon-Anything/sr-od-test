"""OpenRelicReplaceOp(打开替换遗器列表)节点流程测试。

测试层级声明:节点流程为打桩流程测试(画面判定 / 查找区域 / 点击打桩);
交互链本体(着装页点遗器位 → 进列表)由生产实机摸底覆盖(EquipRelicOp
同源交互链),不在此重复。

锁的内容(出处 src/sr_od/operations/open_relic_replace.py):
- 入口画面级判定:着装页起点点目标遗器位;已在列表时**读部位筛选**,
  目标部位幂等、不符点返回回着装页(重入部位不符,EquipRelicOp 实机教训);
  异常画面显式失败(前置导航缺失);
- 打开后滚回列表顶(每轮一次拖拽,轮间画面判定兜底),OPENED 结束。
"""

from __future__ import annotations

import numpy as np
import pytest

from sr_od.operations import open_relic_replace as open_module
from sr_od.operations.open_relic_replace import OpenRelicReplaceOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _NoWindowOpenRelicReplace(OpenRelicReplaceOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        OpenRelicReplaceOp.__init__(self, ctx, pos=1)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_open_from_tab_wrong_pos_and_bad_screen(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """着装页起点:点目标遗器位 → 画面判定确认进列表 → 滚顶 → OPENED;
    已在列表但部位不符:点返回回着装页再点遗器位 → OPENED;异常画面 → 显式失败。"""

    op = _NoWindowOpenRelicReplace(test_context)

    scene = {'screen': 'tab', 'pos': 1}  # 替换列表的部位筛选读数

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '遗器-替换' if scene['screen'] == 'replace' else '角色-遗器'

    def _fake_detect_pos(self, ctx, image):
        return scene['pos'] if scene['screen'] == 'replace' else None

    drags: list = []
    clicks: list = []

    def _fake_click(pos, **kwargs):
        clicks.append(pos)
        y = pos.y if hasattr(pos, 'y') else pos.center.y
        if y < 100:  # 替换界面右上「按钮-返回」
            scene['screen'] = 'tab'
        elif y > 250:  # 着装页「遗器位-头部」槽位
            scene['screen'] = 'replace'
            scene['pos'] = 1

    monkeypatch.setattr(OpenRelicReplaceOp, 'check_and_update_current_screen',
                        _fake_check_screen)
    monkeypatch.setattr(open_module.RelicReplaceRecognizer,
                        '_detect_pos_from_tabs', _fake_detect_pos)
    monkeypatch.setattr(test_context.controller, 'click', _fake_click)
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda *args, **kwargs: drags.append(1))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    # 着装页起点:全链 execute → OPENED(点遗器位 1 次 + 滚顶 4 次拖拽)
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(op.ctx, op)
    assert result.success and result.status == 'OPENED'
    assert len(clicks) == 1, '着装页起点应点击一次遗器位'
    assert len(drags) == 4, f'打开后应滚顶 4 次拖拽,实际 {len(drags)}'

    # 已在列表但部位不符:点返回 → 回着装页 → 点遗器位 → 滚顶 → OPENED
    scene['screen'] = 'replace'
    scene['pos'] = 2  # 停在别的部位筛选
    op_wrong = _NoWindowOpenRelicReplace(test_context)
    drags.clear()
    clicks.clear()
    enter_running_state(op_wrong.ctx)
    try:
        with fast_sleep(op_wrong):
            result = op_wrong.execute()
    finally:
        reset_running_state(op_wrong.ctx, op_wrong)
    assert result.success and result.status == 'OPENED'
    assert len(clicks) == 2, f'部位不符应点返回+点遗器位各一次,实际 {len(clicks)}'
    assert len(drags) == 4

    # 异常画面:入口显式失败
    op_bad = _NoWindowOpenRelicReplace(test_context)
    monkeypatch.setattr(OpenRelicReplaceOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '主界面')
    enter_running_state(op_bad.ctx)
    try:
        with fast_sleep(op_bad):
            result = op_bad.check_entry()
    finally:
        reset_running_state(op_bad.ctx, op_bad)
    assert not result.is_success, '异常画面入口应显式失败'
    assert '不在遗器着装页' in (result.status or '')


def test_invalid_pos_rejected() -> None:
    """部位号越界构造即拒绝(1-6 之外显式报错,不误跑)。"""
    with pytest.raises(ValueError):
        OpenRelicReplaceOp(test_context_stub, pos=7)


from types import SimpleNamespace  # noqa: E402

test_context_stub = SimpleNamespace()  # 构造校验在 ctx 使用前发生,桩即可
