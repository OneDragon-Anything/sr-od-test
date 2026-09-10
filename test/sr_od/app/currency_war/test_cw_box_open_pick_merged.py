"""开箱-选卡同动作闭环锁(第二次复跑诊断,21:06 链;批3a 改形版)。

证据:21:06:19 OpenBox 开箱槽 7 → overlay 弹出 ✓(OCR 同帧见「简易武装箱
请选择1个」),但下一决策帧 box_overlay_open 判 False(对话框已离场)→
选卡臂够不着 → OpenBox/ClickSpheres 空转 3 环。根修 = 开箱成功后**同一
动作内立即选卡**。批3a(A3 判效拆除,用户裁定 2026-09-10):原「轮询验
overlay 弹出/离场」判效半删除,改 DD-011 固定动画等待;弹窗就位与否交
下一帧观察;子步(选卡)的点击事实仍门控期望态补登记(机械发出事实,
非成败回执)。
"""
from types import SimpleNamespace

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_prep_actions import OpenBox
from sr_od.application.currency_war.prep_actions import PrepActionExecutor


def _executor(monkeypatch, pick_result, session=None):
    """构造最小 executor:读箱/选卡全桩,固定等待打桩,记录选卡调用。"""
    ex = object.__new__(PrepActionExecutor)
    ex._op = SimpleNamespace(screenshot=lambda: None)
    ex._ctx = SimpleNamespace(
        controller=SimpleNamespace(mouse_move=lambda p: None,
                                   click=lambda p: None),
        cw_match=SimpleNamespace(session=session) if session is not None
        else None)
    monkeypatch.setattr(prep_actions, 'read_supply_boxes',
                        lambda ctx, screen: [(7, SimpleNamespace(x=100,
                                                                 y=900))])
    monkeypatch.setattr(prep_actions.time, 'sleep', lambda s: None)
    picks: list = []
    monkeypatch.setattr(ex, '_pick_box_card',
                        lambda a: picks.append(a) or pick_result)
    return ex, picks


class TestOpenBoxPickMerged:

    def test_open_success_triggers_same_action_pick(self, monkeypatch):
        """开箱发出 ⇒ 同一动作内立即选卡(选卡调用在案,摘要含选卡)。"""
        ex, picks = _executor(monkeypatch,
                              pick_result=(True, '选卡 修复枪'))
        detail, emitted = ex._open_box(OpenBox())
        assert emitted is True
        assert '选卡' in detail
        assert len(picks) == 1

    def test_merged_pick_registers_pickbox_effect(self, monkeypatch):
        """三审 C1:合并路径补 PickBoxCard 期望态登记 ⇒
        last_owned_equips 含所选装备(外层 OpenBox 登记零状态变更,
        内层不补 = 选到的装备丢失/动态权重漂移)。"""
        sess = SimpleNamespace(last_owned_equips=[])
        ex, _picks = _executor(monkeypatch,
                               pick_result=(True, '选卡 修复枪'),
                               session=sess)
        _detail, _emitted = ex._open_box(OpenBox())
        assert sess.last_owned_equips == ['修复枪']

    def test_pick_not_issued_registers_nothing(self, monkeypatch):
        """选卡子步未发出(overlay 未现,无卡可读)⇒ 不登记(未发出,
        无逻辑后果;下一帧观察重派)。"""
        sess = SimpleNamespace(last_owned_equips=[])
        ex, _picks = _executor(monkeypatch,
                               pick_result=(False, '武装箱 overlay 未开(先 OpenBox)'),
                               session=sess)
        detail, emitted = ex._open_box(OpenBox())
        assert emitted is True   # 开箱点击已发(机械事实)
        assert '选卡未发出' in detail
        assert sess.last_owned_equips == []

    def test_pick_not_issued_reported_explicitly(self, monkeypatch):
        """选卡子步未发出 ⇒ OpenBox 摘要显式回报(不再以开箱成功掩盖
        未消费;交下一帧观察重派)。"""
        ex, picks = _executor(monkeypatch,
                              pick_result=(False, 'OCR 未读到卡名'))
        detail, _emitted = ex._open_box(OpenBox())
        assert '选卡未发出' in detail
        assert len(picks) == 1

    def test_no_box_is_precondition_refusal(self, monkeypatch):
        """环境无对象(无补给箱)= 执行前输入契约拒绝 → 未发出
        (M6 边界面;非判效)。"""
        ex = object.__new__(PrepActionExecutor)
        ex._op = SimpleNamespace(screenshot=lambda: None)
        ex._ctx = SimpleNamespace(
            controller=SimpleNamespace(mouse_move=lambda p: None,
                                       click=lambda p: None),
            cw_match=None)
        monkeypatch.setattr(prep_actions, 'read_supply_boxes',
                            lambda ctx, screen: [])
        detail, emitted = ex._open_box(OpenBox())
        assert emitted is False and '无补给箱' in detail


class TestPickBoxCardFallback:

    def test_ocr_empty_falls_back_to_first_card(self, monkeypatch):
        """简易武装箱变体兜底:卡名行 OCR 不可得 ⇒ 点装备卡-1(选中即
        确认),固定等待(原离场验证轮询拆除,批3a)⇒ 点击已发出。"""
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
        monkeypatch.setattr(prep_actions.time, 'sleep', lambda s: None)
        clicked, msg = ex._pick_box_card(PickBoxCard())
        assert clicked is True
        assert '兜底' in msg
        assert len(clicks) >= 1
