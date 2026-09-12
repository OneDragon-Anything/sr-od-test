"""开箱动作纯机械执行锁(T-142 拆分;原「同动作选卡闭环」随 ADR-0601 拆除)。

结构:``_open_box`` = 找箱槽 → 点开启 → 固定动画等待,纯机械执行
(ADR-0601:动作 op 机械执行,决策归决策面);选卡动作归下一决策帧的
决策面闭环——观察侧每步现读 ``box_overlay_open`` → 策略器 prep 实体
面臂发射 ``PickBoxCard``(发射臂锁 = test_cw_box_pick_arm)→
``_dispatch_direct`` → ``_pick_box_card`` 执行。

历史注记:原同动作内联选卡(commit 698631b19)的诊断动机 = 跨帧分离时
overlay 观察判 False 致选卡臂够不着、OpenBox 空转 3 环;该形态是
「决策与点卡同执行链闭环」违例——跨帧承接面失真治在观察/建档面,
不在执行链内联第二决策点。本文件负锁钉「内联不复活」:行为面
(开箱动作零选卡调用 + 期望态零 PickBoxCard 登记)+ 源码面
(prep_actions 单文件分派位唯一,与 test_equip_op_kernel_criteria_free
同型)。
"""
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war import prep_actions
from sr_od.application.currency_war.kernel.cw_prep_actions import OpenBox
from sr_od.application.currency_war.prep_actions import PrepActionExecutor


def _executor(monkeypatch, pick_result, session=None):
    """构造最小 executor:读箱/选卡全桩,固定等待打桩,记录选卡调用。

    选卡桩仅作**负锁观测面**(断言零调用);执行器本体已不内联选卡,
    桩被触即拆分回归信号。
    """
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


class TestOpenBoxMechanicalOnly:

    def test_open_success_does_not_pick_in_action(self, monkeypatch):
        """开箱发出 ⇒ 同一动作内零选卡调用(选卡归下一决策帧决策面臂),
        摘要收敛为「开箱槽N」(旧合并形态「+选卡」后缀随拆分退役)。"""
        ex, picks = _executor(monkeypatch,
                              pick_result=(True, '选卡 修复枪'))
        detail, emitted = ex._open_box(OpenBox())
        assert emitted is True
        assert detail == '开箱槽7', f'摘要形态漂移:{detail!r}'
        assert picks == [], f'执行链内联选卡复活(ADR-0601 违例回归):{picks!r}'

    def test_open_registers_no_pickbox_effect(self, monkeypatch):
        """开箱动作零 PickBoxCard 期望态登记 ⇒ last_owned_equips 不变。

        选卡效果登记唯一通道 = 真 PickBoxCard 动作经 execute() 统一
        推进;原内联补推进面(contextlib.suppress + apply_op_effect)
        随拆分删除,开箱发出不再产生任何装备账推进。"""
        sess = SimpleNamespace(last_owned_equips=[])
        ex, _picks = _executor(monkeypatch,
                               pick_result=(True, '选卡 修复枪'),
                               session=sess)
        _detail, _emitted = ex._open_box(OpenBox())
        assert sess.last_owned_equips == [], \
            f'开箱动作越权登记装备账(内联补推进复活):{sess.last_owned_equips!r}'

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

    def test_inline_pick_source_free(self):
        """源码面负锁:prep_actions.py 单文件 ``self._pick_box_card(``
        调用恰 1 处(= _dispatch_direct 分派位,独立 PickBoxCard 动作
        唯一入口);旧合并形态摘要特征串零出现(与
        test_equip_op_kernel_criteria_free 同型)。"""
        src_path = (Path(__file__).resolve().parents[5] / 'src'
                    / 'sr_od/application/currency_war/prep_actions.py')
        text = src_path.read_text(encoding='utf-8')
        n_call = text.count('self._pick_box_card(')
        assert n_call == 1, \
            f'_pick_box_card 调用点漂移(期望恰 _dispatch_direct 一处,内联复活信号): {n_call}'
        offenders = [t for t in ('+选卡', '选卡未发出') if t in text]
        assert not offenders, f'旧合并形态摘要特征串残留: {offenders}'


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
