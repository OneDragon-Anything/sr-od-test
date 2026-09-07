"""推进型画面 op 行为锁(空决策形态;T-121/ADR-0584,A 族 10 op)。

合同(T-121 方案 §2.1,事实参照形 = CwScreenPlaneTransition):入口观察
(锚 miss = fail 不点击)→ 单次推进 → 可选验效 → 如实返回;节点单尝试
(node_max_retry_times=1,重试预算归外循环)。

离线桩手法 = test_cw_w971_p3a_flow_ops 同款(FixtureController 假游戏 +
round_by_* 判定替身 + fast_sleep);坐标类断言消费真实 screen_info
(按钮-关闭概率表/按钮-关闭/按钮-简易装备首件 三处 area 化产物,矩形
中心 = 原 Point,ADR-0584 §6.3-2 对拍的离线腿)。

测试纪律:零真实副作用(telemetry 替身、存图/移光标替身)、execute() 包
fast_sleep、运行态用 enter/reset_running_state。
"""
from __future__ import annotations

import inspect
from typing import Any

import pytest

from sr_od.application.currency_war.operations.cw_screen import (
    _progression_base,
    cw_screen_aha_equip_pick,
    cw_screen_consumable_overlay,
    cw_screen_emblem_detail_popup,
    cw_screen_interrupt_dialog,
    cw_screen_item_detail_popup,
    cw_screen_next_button,
    cw_screen_plane_detail,
    cw_screen_prep_locked_return,
    cw_screen_refresh_odds_popup,
    cw_screen_role_detail_overlay,
)
from sr_od.application.currency_war.telemetry import recorder as cw_recorder
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_FRAME = ('货币战争-备战', 'shop_closed')


def _require_frame(test_context: SrTestContext) -> None:
    if not test_context.has_screen(*_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_FRAME[0]}/{_FRAME[1]}.webp')


def _watched(op_cls: type) -> Any:
    return type('W', (WatchdogOperationMixin, op_cls), {})


def _make_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
             op_cls: type, *args: Any,
             **kwargs: Any) -> tuple[Any, FixtureController]:
    """装配被测 op(带参 op 经 args/kwargs 透传)。"""
    _require_frame(test_context)
    fc = FixtureController(test_context)
    fc.set_phases([{'frame': _FRAME}])
    monkeypatch.setattr(test_context, 'controller', fc)
    op = _watched(op_cls)(test_context, *args, **kwargs)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(fc, 'mouse_move', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc


def _stub_find(op: Any, monkeypatch: pytest.MonkeyPatch,
               hits: list[tuple[str, str]],
               misses_after: int | None = None) -> None:
    """round_by_find_area 替身:命中集内成功;misses_after 次成功后全失败
    (模拟「入口锚在、出口锚消失」的真转移)。"""
    counter = [0]

    def _find(screen, screen_name: str, area_name: str, **k: Any) -> Any:
        if misses_after is not None and counter[0] >= misses_after:
            return op.round_fail('')
        counter[0] += 1
        if (screen_name, area_name) in hits:
            return op.round_success('')
        return op.round_fail('')

    monkeypatch.setattr(op, 'round_by_find_area', _find)


def _stub_ocr(op: Any, monkeypatch: pytest.MonkeyPatch,
              hits: dict[str, bool]) -> None:
    """round_by_ocr 替身:词 → 是否命中。"""
    def _ocr(screen, target_cn: str, **k: Any) -> Any:
        return (op.round_success('') if hits.get(target_cn)
                else op.round_fail(''))

    monkeypatch.setattr(op, 'round_by_ocr', _ocr)


def _stub_find_and_click(op: Any, monkeypatch: pytest.MonkeyPatch,
                         ok: bool = True) -> list[tuple[str, str]]:
    """round_by_find_and_click_area 替身:记录 (screen, area) 并返回预置成败。"""
    calls: list[tuple[str, str]] = []

    def _click(screen, screen_name: str, area_name: str, **k: Any) -> Any:
        calls.append((screen_name, area_name))
        return op.round_success('') if ok else op.round_fail('')

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click)
    return calls


def _run(op: Any) -> Any:
    enter_running_state(op.ctx)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


# ==================== 合同强度(全部推进 op) ====================


def test_progression_ops_single_attempt() -> None:
    """合同强度(ADR-0584 §2.1,方案审 N10):推进型新 op 节点一律
    node_max_retry_times=1(单尝试,重试预算归外循环);新 op 忘带即红。"""
    mods = [_progression_base, cw_screen_plane_detail,
            cw_screen_refresh_odds_popup, cw_screen_item_detail_popup,
            cw_screen_consumable_overlay, cw_screen_aha_equip_pick,
            cw_screen_prep_locked_return, cw_screen_role_detail_overlay,
            cw_screen_emblem_detail_popup, cw_screen_interrupt_dialog,
            cw_screen_next_button]
    for mod in mods:
        for name in dir(mod):
            obj = getattr(mod, name)
            if not (isinstance(obj, type)
                    and issubclass(obj, _progression_base.CwProgressionScreenOp)
                    and obj is not _progression_base.CwProgressionScreenOp):
                continue
            src = inspect.getsource(obj.handle)
            assert 'node_max_retry_times=1' in src, (
                f'{mod.__name__}.{name}: 推进 op 非单尝试(违反空决策形态合同)')


# ==================== A1 位面详情(有验效) ====================


def test_plane_detail_clicks_close_and_verifies(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:标题命中 → 点「按钮-关闭位面详情」→ 验标题消失 = 成功。"""
    op, fc = _make_op(test_context, monkeypatch, cw_screen_plane_detail.CwScreenPlaneDetail)
    _stub_find(op, monkeypatch,
               [('货币战争-位面详情', '标识-位面详情标题')], misses_after=1)
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert result.success, f'位面详情关闭应成功:{result.status!r}'
    assert ('货币战争-位面详情', '按钮-关闭位面详情') in clicks


def test_plane_detail_verify_fail_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:点 X 后标题仍在 → fail(单尝试;重试由外循环包装映射)。"""
    op, _fc = _make_op(test_context, monkeypatch, cw_screen_plane_detail.CwScreenPlaneDetail)
    # 入口命中(1 次)后验效帧标题仍在(第 2 次仍命中)
    _stub_find(op, monkeypatch,
               [('货币战争-位面详情', '标识-位面详情标题')])
    _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert not result.success


def test_plane_detail_entry_miss_fails_without_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:入口锚未命中 → fail 且不点击(入口观察合同)。"""
    op, fc = _make_op(test_context, monkeypatch, cw_screen_plane_detail.CwScreenPlaneDetail)
    _stub_find(op, monkeypatch, [])
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert not result.success
    assert clicks == [] and fc.recorded_clicks == []


# ==================== A2 概率表弹窗(坐标 area 化对拍腿) ====================


def test_refresh_odds_clicks_registered_close_area(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:入口命中 → 点「按钮-关闭概率表」建档中心(= 原 Point(1501,263),
    ADR-0584 §6.3-2 对拍离线腿);mouse_move bug#1 缓解保留。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_refresh_odds_popup.CwScreenRefreshOddsPopup)
    _stub_find(op, monkeypatch, [('货币战争-商店刷新概率表', '标识-刷新概率表')])
    moves: list[Any] = []
    monkeypatch.setattr(fc, 'mouse_move',
                        lambda p: moves.append(p), raising=False)

    result = _run(op)

    assert result.success, f'概率表点×应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-商店刷新概率表', '按钮-关闭概率表')
    hit = [p for p in fc.recorded_clicks
           if (p.x, p.y) == (1501, 263)]
    assert hit, f'点击落点应 = 原 Point(1501,263):{[str(p) for p in fc.recorded_clicks]}'
    assert moves, 'mouse_move 缺失(bug#1 缓解被删)'


# ==================== A3 道具详情弹窗(OCR 入口 + 排他) ====================


def test_item_detail_wish_exclusion_fails_entry(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:祈愿屏排他(「聘用书」命中 ∧ 祈愿锚命中)→ 入口 fail 不点击
    (r31 死循环修复语义随 op)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_item_detail_popup.CwScreenItemDetailPopup)
    _stub_ocr(op, monkeypatch, {'聘用书': True})
    _stub_find(op, monkeypatch, [('货币战争-祈愿试炼', '标识-祈愿试炼')])

    result = _run(op)

    assert not result.success
    assert fc.recorded_clicks == []


def test_item_detail_clicks_registered_close_area(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:「聘用书」命中 ∧ 非祈愿屏 → 点「按钮-关闭」建档中心
    (= 原 Point(1862,65),ADR-0584 §6.3-2 对拍离线腿)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_item_detail_popup.CwScreenItemDetailPopup)
    _stub_ocr(op, monkeypatch, {'聘用书': True})
    _stub_find(op, monkeypatch, [])

    result = _run(op)

    assert result.success, f'道具详情点×应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-道具详情弹窗', '按钮-关闭')
    hit = [p for p in fc.recorded_clicks if (p.x, p.y) == (1862, 65)]
    assert hit, f'点击落点应 = 原 Point(1862,65):{[str(p) for p in fc.recorded_clicks]}'


# ==================== A4/A7 ESC 族 ====================


def test_consumable_overlay_esc(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:双 OCR 条件入口命中 → ESC;入口不齐(缺「拖动到」)→ 不按键。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_consumable_overlay.CwScreenConsumableOverlay)
    _stub_ocr(op, monkeypatch, {'消耗品': True, '拖动到': True})
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success and taps == ['esc']

    op2, _fc2 = _make_op(test_context, monkeypatch,
                         cw_screen_consumable_overlay.CwScreenConsumableOverlay)
    _stub_ocr(op2, monkeypatch, {'消耗品': True, '拖动到': False})
    taps2: list[str] = []
    monkeypatch.setattr(_fc2, 'btn_tap', lambda k: taps2.append(k), raising=False)
    result2 = _run(op2)
    assert not result2.success and taps2 == []


def test_role_detail_overlay_either_ocr_esc(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:「可合成列表」∨「角色详情」其一命中即接管 → ESC(∨ 语义)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_role_detail_overlay.CwScreenRoleDetailOverlay)
    _stub_ocr(op, monkeypatch, {'可合成列表': False, '角色详情': True})
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success and taps == ['esc']


# ==================== A5 阿哈装备(固定策略申报) ====================


def test_aha_equip_clicks_first_equip_area(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:锚命中 → 点「按钮-简易装备首件」建档中心(= 原 Point(626,250),
    ADR-0584 §6.3-2 对拍离线腿);固定策略 = 点首件。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_aha_equip_pick.CwScreenAhaEquipPick)
    _stub_find(op, monkeypatch, [('货币战争-备战', '标识-简易装备')])

    result = _run(op)

    assert result.success, f'阿哈装备点首件应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-备战', '按钮-简易装备首件')
    hit = [p for p in fc.recorded_clicks if (p.x, p.y) == (626, 250)]
    assert hit, f'点击落点应 = 原 Point(626,250):{[str(p) for p in fc.recorded_clicks]}'


# ==================== A6 备战暗色锁定(参数化) ====================


def test_prep_locked_return_parameterized_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:构造画面档对 → 入口与点击同一按钮锚;另一画面档不误判。"""
    op, fc = _make_op(
        test_context, monkeypatch, cw_screen_prep_locked_return.CwScreenPrepLockedReturn,
        '货币战争-备战-策略锁定', '按钮-返回投资策略选择')
    _stub_find(op, monkeypatch,
               [('货币战争-备战-策略锁定', '按钮-返回投资策略选择')])
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert result.success
    assert ('货币战争-备战-策略锁定', '按钮-返回投资策略选择') in clicks

    # 遭遇锁定档:判据替身只认遭遇锁定锚 → 策略锁定 op 入口 fail
    op2, _fc2 = _make_op(
        test_context, monkeypatch, cw_screen_prep_locked_return.CwScreenPrepLockedReturn,
        '货币战争-备战-遭遇锁定', '按钮-返回遭遇选择')
    _stub_find(op2, monkeypatch,
               [('货币战争-备战-策略锁定', '按钮-返回投资策略选择')])
    result2 = _run(op2)
    assert not result2.success


# ==================== A8 星徽详情(不用 ESC) ====================


def test_emblem_detail_clicks_close_never_esc(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:双锚其一(套组标题)命中 → 点「按钮-关闭」;**禁 ESC**
    (bug#2:面板已关时 ESC 落备战弹中断挑战)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_emblem_detail_popup.CwScreenEmblemDetailPopup)
    # 第一锚 miss、第二锚(套组标题)命中;misses_after=2 辖入口两次探锚,
    # 出口验效(第 3 次)不再命中
    _stub_find(op, monkeypatch,
               [('货币战争-星徽详情', '标识-套组标题')], misses_after=2)
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success
    assert ('货币战争-星徽详情', '按钮-关闭') in clicks
    assert taps == [], '星徽详情禁 ESC(bug#2 理由随迁,ADR-0584)'


# ==================== A9 中断挑战(真模态) ====================


def test_interrupt_dialog_clicks_close_records_popup(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:锚命中 → 外生 popup 行 + 点「按钮-关闭」+ park_cursor;X 失败
    兜底 ESC;绝不点「放弃并结算」。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_interrupt_dialog.CwScreenInterruptDialog)
    _stub_find(op, monkeypatch, [('货币战争-中断挑战弹窗', '标识-中断挑战')])
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)
    exog: list[tuple] = []
    monkeypatch.setattr(cw_screen_interrupt_dialog.recorder, 'record_exogenous',
                        lambda *a, **k: exog.append(a))
    assert cw_screen_interrupt_dialog.recorder is cw_recorder   # 同源替身

    result = _run(op)

    assert result.success
    assert ('货币战争-中断挑战弹窗', '按钮-关闭') in clicks
    assert exog and exog[0][1] == 'popup'


def test_interrupt_dialog_esc_fallback(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:X 点击失败 → ESC 兜底(实测无副作用),仍算消费完成。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_interrupt_dialog.CwScreenInterruptDialog)
    _stub_find(op, monkeypatch, [('货币战争-中断挑战弹窗', '标识-中断挑战')])
    _stub_find_and_click(op, monkeypatch, ok=False)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)
    monkeypatch.setattr(fc, 'esc', lambda: taps.append('esc'), raising=False)
    monkeypatch.setattr(cw_screen_interrupt_dialog.recorder, 'record_exogenous',
                        lambda *a, **k: None)

    result = _run(op)

    assert result.success
    assert taps == ['esc']


# ==================== A10 前进按钮 ====================


def test_next_button_ocr_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:OCR「下一步」命中 → ocr_and_click 推进(success_wait=2 同原值);
    未命中 → fail 不点击。"""
    op, _fc = _make_op(test_context, monkeypatch, cw_screen_next_button.CwScreenNextButton)
    _stub_ocr(op, monkeypatch, {'下一步': True})
    click_calls: list[dict] = []

    def _ocr_click(screen, target_cn: str, **k: Any) -> Any:
        click_calls.append({'target': target_cn, **k})
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_ocr_and_click', _ocr_click)

    result = _run(op)

    assert result.success
    assert click_calls and click_calls[0]['target'] == '下一步'
    assert click_calls[0].get('success_wait') == 2
