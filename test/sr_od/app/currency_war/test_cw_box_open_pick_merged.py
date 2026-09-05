"""开箱-选卡同动作闭环锁(第二次复跑诊断,21:06 链)。

证据:21:06:19 OpenBox 开箱槽 7 → overlay 弹出 ✓(OCR 同帧见「简易武装箱
请选择1个」),但下一决策帧 box_overlay_open 判 False(对话框已离场)→
选卡臂够不着 → OpenBox/ClickSpheres 空转 3 环。根修 = 开箱成功后**同一
动作内立即选卡**,选卡失败显式回报(不再以"开箱成功"掩盖未消费)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_prep_actions import OpenBox
from sr_od.application.currency_war.prep_actions import PrepActionExecutor


def _executor(monkeypatch, poll_results, pick_result):
    """构造最小 executor:读箱/轮询/选卡全桩,记录选卡调用。"""
    ex = object.__new__(PrepActionExecutor)
    ex._op = SimpleNamespace(screenshot=lambda: None)
    ex._ctx = SimpleNamespace(controller=SimpleNamespace(
        mouse_move=lambda p: None, click=lambda p: None))
    monkeypatch.setattr(prep_actions, 'read_supply_boxes',
                        lambda ctx, screen: [(7, SimpleNamespace(x=100,
                                                                 y=900))])
    polls = iter(poll_results)
    monkeypatch.setattr(ex, '_poll_transition', lambda fn, t: next(polls))
    picks: list = []
    monkeypatch.setattr(ex, '_pick_box_card',
                        lambda a: picks.append(a) or pick_result)
    return ex, picks


class TestOpenBoxPickMerged:

    def test_open_success_triggers_same_action_pick(self, monkeypatch):
        """开箱成功 ⇒ 同一动作内立即选卡(选卡调用在案,返回含选卡)。"""
        ex, picks = _executor(monkeypatch, poll_results=[True],
                              pick_result=(True, '选卡 修复枪'))
        ok, msg = ex._open_box(OpenBox())
        assert ok is True
        assert '选卡' in msg
        assert len(picks) == 1

    def test_pick_failure_reported_explicitly(self, monkeypatch):
        """选卡失败 ⇒ OpenBox 显式回报失败(不再以开箱成功掩盖未消费)。"""
        ex, picks = _executor(monkeypatch, poll_results=[True],
                              pick_result=(False, 'OCR 未读到卡名'))
        ok, msg = ex._open_box(OpenBox())
        assert ok is False
        assert '选卡未生效' in msg
        assert len(picks) == 1

    def test_poll_fail_no_pick_attempt(self, monkeypatch):
        """overlay 未弹 ⇒ OpenBox 失败且不触发选卡(轮询守卫在前)。"""
        ex, picks = _executor(monkeypatch, poll_results=[False],
                              pick_result=(True, 'x'))
        ok, msg = ex._open_box(OpenBox())
        assert ok is False
        assert picks == []
        assert '未弹' in msg


class TestPickBoxCardFallback:

    def test_ocr_empty_falls_back_to_first_card(self, monkeypatch):
        """简易武装箱变体兜底:卡名行 OCR 不可得 ⇒ 点装备卡-1(选中即
        确认),overlay 离场验证通过 ⇒ 成功。"""
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            PickBoxCard,
        )
        ex = object.__new__(PrepActionExecutor)
        ex._op = SimpleNamespace(
            screenshot=lambda: SimpleNamespace(),
            round_by_find_area=lambda screen, sc, area: SimpleNamespace(
                is_success=True))
        clicks: list = []
        ex._ctx = SimpleNamespace(controller=SimpleNamespace(
            mouse_move=lambda p: clicks.append(p),
            click=lambda p: None))
        monkeypatch.setattr(
            prep_actions, '_area_rect',
            lambda ctx, area, screen: SimpleNamespace(
                x1=545, y1=225, x2=700, y2=345)
            if area == '装备卡-1' else None)
        monkeypatch.setattr(
            prep_actions, '_ocr',
            lambda ctx, screen, rect: [])
        polls = iter([True])   # 离场验证通过
        monkeypatch.setattr(ex, '_poll_transition', lambda fn, t: next(polls))
        ok, msg = ex._pick_box_card(PickBoxCard())
        assert ok is True
        assert '兜底' in msg
        assert len(clicks) >= 1
