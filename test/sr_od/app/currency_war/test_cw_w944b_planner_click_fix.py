"""W944 迭代③:策划事件点位布局漂移修复锁(match3 实锤 2026-08-31)。

真因:卡上移(旧 rect y 280-560 → 当前 y 180-455)后硬编码 (1225,480) 落卡外
→ 未选中 → 确认无效 → round_retry ×5 失败(match3 07:45 两次「返回状态 失败」)。
修复:点击点由 area rect 推导(71% 高度+详情钮避让 clamp)+ press_time 0.15 加固。
守卫移除红检目标 = ①rect 回退旧值 ②_card_point 改回硬编码 → 本文件锁红。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.operations.handlers import _overlay_confirm
from sr_od.application.currency_war.operations.handlers.handle_planner_event import (
    HandlePlannerEvent,
)


def test_card_point_inside_updated_area_and_avoids_detail(test_context) -> None:
    """推导点位落在当前布局卡 rect 内、且相对避让生效(双卡)。

    避让断言用 rect 相对几何(底缘上移 DETAIL_MARGIN_RATIO),非绝对 y
    (W952 P2-1:绝对常数对多布局不成立——弹窗整体平移时相对断言仍成立)。
    """
    op = HandlePlannerEvent(test_context)
    for idx in (0, 1):
        area = test_context.screen_loader.get_area(
            HandlePlannerEvent.CARD_AREA_SCREEN,
            HandlePlannerEvent.CARD_AREAS[idx])
        assert area is not None, f'卡 area 缺失:idx={idx}'
        rect = area.pc_rect
        p = op._card_point(idx)
        assert rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2, (
            f'idx={idx} 点 ({p.x},{p.y}) 落在卡 rect {rect} 外(布局漂移复发形态)')
        detail_top = rect.y2 - int(rect.height * HandlePlannerEvent.DETAIL_MARGIN_RATIO)
        assert p.y <= detail_top, (
            f'idx={idx} 点 y={p.y} 进入详情钮相对避让带(>={detail_top})')
        assert p.y >= rect.y1 + 60, f'idx={idx} 点过于靠卡顶(上半部点击=详情面板实证)'


def test_card_point_falls_back_to_legacy_safe_band(
    test_context, monkeypatch) -> None:
    """area 缺失 → 兜底点位=旧实证安全带(W952 P1-1 强断言,非平凡 in-rect)。

    旧实证安全点 (755/1225,480) ∈ [460,480];绝对 clamp 425 曾把兜底压到
    旧布局 51.8% 卡高——(755,400) 型详情危险带与安全点之间未验证带。
    """
    monkeypatch.setattr(test_context.screen_loader, 'get_area', lambda *a, **k: None)
    op = HandlePlannerEvent(test_context)
    for idx in (0, 1):
        p = op._card_point(idx)
        lx, ly, rx, ry = HandlePlannerEvent._LEGACY_CARD_RECTS[idx]
        assert lx <= p.x <= rx, f'idx={idx} x={p.x} 不在旧 rect 内'
        assert 460 <= p.y <= 480, (
            f'idx={idx} 兜底 y={p.y} 出旧实证安全带 [460,480](详情危险带发作形态)')


def test_press_time_hardening_wired() -> None:
    """加固接线:点卡/确认都走 0.15 按压;共享助手默认 0.1(其它 handler 零影响)。"""
    src = inspect.getsource(HandlePlannerEvent)
    assert 'press_time=self.CLICK_PRESS_TIME' in src, '点卡未带按压加固'
    assert 'press_time=self.CLICK_PRESS_TIME)' in inspect.getsource(
        HandlePlannerEvent.handle) or 'press_time=self.CLICK_PRESS_TIME' in src
    assert 'press_time: float = 0.1' in inspect.getsource(_overlay_confirm), (
        'confirm_and_verify 默认值变了(会波及其它 handler)')
    assert 'press_time=press_time' in inspect.getsource(_overlay_confirm), (
        '确认点击未透传 press_time')


def test_match3_frame_regression_points(test_context) -> None:
    """match3 帧回归:旧硬编码点 (1225,480) 必须落在更新后的右卡 rect 外
    (锁 rect 更新本身——rect 回退旧值 = 本锁红)。"""
    area = test_context.screen_loader.get_area('货币战争-骇入策划', '骇入选项-右卡')
    assert area is not None
    rect = area.pc_rect
    assert not (rect.x1 <= 1225 <= rect.x2 and rect.y1 <= 480 <= rect.y2), (
        '右卡 rect 回退旧布局(y 280-560)——match3 点位漂移根因复发')
