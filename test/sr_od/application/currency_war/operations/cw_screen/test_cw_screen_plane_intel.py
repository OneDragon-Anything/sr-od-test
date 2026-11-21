"""位面情报采集 op 联动判据测试(CwScreenPlaneIntel 选中态模板信号):

- 语料帧信号:判据在归档语料帧上稳定——位面1选中帧(钻石切面纹理 /
  棋盘格纹理事故帧)判 1,卡区被浮层模糊盖住的帧判 None。前判据
  「详情条节点编号 OCR」在全局 det_limit_side_len=1920 下漏读事故帧
  编号(零检测框)致联动判定永假、点位面卡重试空转;模板信号不依赖
  OCR 检测参数,帧类免疫;
- sim 改道口:呈现面在场 → 直出 selected_plane,零模板匹配(语义不变);
- 联动核:点卡后复查同一判据,命中即放行(零重试)。

帧资产 = 测试仓 ``screens/货币战争-位面详情/``(钻石切面纹理 =
位面详情全屏;棋盘格纹理 = 位面1选中-棋盘格纹理,原 OCR 判据漏读
的现场帧;负样本 = 敌人信息浮层)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext

from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
    CwScreenPlaneIntel,
)

_PD: str = '货币战争-位面详情'

# (存档 state 名, 期望选中位面号 | None=三卡位全 miss)
_CORPUS_FRAMES: tuple[tuple[str, int | None], ...] = (
    ('位面详情全屏', 1),
    ('位面1选中-棋盘格纹理', 1),
    ('敌人信息浮层', None),
)


def _require_frames(test_context: SrTestContext) -> None:
    for state, _ in _CORPUS_FRAMES:
        if not test_context.has_screen(_PD, state):
            pytest.skip(f'存档截图缺失:screens/{_PD}/{state}.webp')


def test_selected_plane_signal_on_corpus_frames(
        test_context: SrTestContext) -> None:
    """判据信号在全部语料帧上稳定(模板信号不依赖 OCR 检测参数)。"""
    _require_frames(test_context)
    op = CwScreenPlaneIntel(test_context)
    for state, expected in _CORPUS_FRAMES:
        frame = test_context.load_screen(_PD, state)
        assert op._selected_plane_no(frame) == expected, \
            f'帧 {state} 期望选中位面判读={expected}'


def test_selected_plane_sim_port_passthrough(
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """sim 改道口语义不变:呈现面在场 → 直出 selected_plane。"""
    import sr_od.application.currency_war.sim.cw_sim_ports as ports

    class _FakeView:
        selected_plane = 3

    class _FakeBackend:
        def plane_intel_view(self):
            return _FakeView()

    monkeypatch.setattr(ports, '_BACKEND', _FakeBackend())
    op = CwScreenPlaneIntel(test_context)
    assert op._selected_plane_no(None) == 3


def test_select_plane_click_then_verify_by_template_signal(
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """联动核:点位面卡1 → 复查同一判据命中 → 放行(None,零重试)。"""
    if not test_context.has_screen(_PD, '位面详情全屏'):
        pytest.skip(f'存档截图缺失:screens/{_PD}/位面详情全屏.webp')
    from test.harness.cw_fixture_controller import CwFixtureController
    from test.harness.fixture_controller import fast_sleep
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # 固定帧剧本(无 exit):位面1选中帧恒在场,判据应直接命中放行
    ctrl.set_phases([{'frame': (_PD, '位面详情全屏')}])
    op = CwScreenPlaneIntel(test_context)
    with fast_sleep(op):
        rs = op._select_plane(1)
    assert rs is None, f'选中态命中应放行,实际 {getattr(rs, "status", None)!r}'
    assert ctrl.click_hit_area(_PD, '按钮-位面卡1'), \
        f'应点击按钮-位面卡1,实际点击 {ctrl.recorded_clicks}'
