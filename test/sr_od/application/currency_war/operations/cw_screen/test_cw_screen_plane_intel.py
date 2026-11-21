"""位面情报采集 op 查看位面判据测试(CwScreenPlaneIntel 双环信号):

- 语料帧信号:查看位面判据 = 查看态白环命中位优先 + 当前位面金环兜底。
  金环是当前位面恒亮标记而非选中信号,只按金环判会把「查看位面2/3」
  误判成「仍在位面1」——白环帧判 2 锁白环优先级,金环帧判 1 锁白环
  不误命中金环卡,浮层负样本帧判 None;
- sim 改道口:呈现面在场 → 直出 selected_plane,零模板匹配(语义不变);
- 联动核:点卡后复查同一判据,命中即放行(零重试)。

帧资产 = 测试仓 ``screens/货币战争-位面详情/``(金环态 = 位面详情全屏 /
位面1选中-棋盘格纹理 / 位面1查看态-开场;白环态 = 位面2查看态-白环);
负样本 = 敌人信息浮层(帧实属敌人信息浮层屏,浮层独立建屏后语料随迁其
目录 ``screens/货币战争-敌人信息浮层/``,按帧实属屏加载)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext

from sr_od.application.currency_war.operations.cw_screen.cw_screen_plane_intel import (
    CwScreenPlaneIntel,
)

_PD: str = '货币战争-位面详情'
_EI: str = '货币战争-敌人信息浮层'

# (存档屏, 存档 state 名, 期望查看位面号 | None=两族模板全 miss)
_CORPUS_FRAMES: tuple[tuple[str, str, int | None], ...] = (
    (_PD, '位面详情全屏', 1),
    (_PD, '位面1选中-棋盘格纹理', 1),
    (_PD, '位面1查看态-开场', 1),
    (_PD, '位面2查看态-白环', 2),
    (_EI, '敌人信息浮层', None),
)


def _require_frames(test_context: SrTestContext) -> None:
    for screen, state, _ in _CORPUS_FRAMES:
        if not test_context.has_screen(screen, state):
            pytest.skip(f'存档截图缺失:screens/{screen}/{state}.webp')


def test_selected_plane_signal_on_corpus_frames(
        test_context: SrTestContext) -> None:
    """判据信号在全部语料帧上稳定(模板信号不依赖 OCR 检测参数)。"""
    _require_frames(test_context)
    op = CwScreenPlaneIntel(test_context)
    for screen, state, expected in _CORPUS_FRAMES:
        frame = test_context.load_screen(screen, state)
        assert op._selected_plane_no(frame) == expected, \
            f'帧 {screen}/{state} 期望查看位面判读={expected}'


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
