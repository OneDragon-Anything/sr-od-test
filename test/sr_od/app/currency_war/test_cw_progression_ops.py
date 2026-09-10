"""推进型画面 op 行为锁(空决策形态;T-121/ADR-0584,A 族 10 op)。

合同(T-121 方案 §2.1,事实参照形 = CwScreenPlaneTransition):入口观察
(锚 miss = fail 不点击)→ 单次推进 → 可选验效 → 如实返回;节点单尝试
(node_max_retry_times=1,重试预算归外循环)。

离线桩手法 = test_cw_flow_ops 同款(FixtureController 假游戏 +
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
    cw_screen_shop_card_detail,
)
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
              hits: dict[str, bool], misses_after: int | None = None) -> None:
    """round_by_ocr 替身:词 → 是否命中;misses_after 次成功后全失败
    (模拟「重入裁决帧入口词已消失」,验证废除批骨架新增重入臂)。"""
    counter = [0]

    def _ocr(screen, target_cn: str, **k: Any) -> Any:
        if misses_after is not None and counter[0] >= misses_after:
            return op.round_fail('')
        counter[0] += 1
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


def test_progression_ops_reentry_adjudication_budget() -> None:
    """合同锁(L1-9 重推,验证废除批 2026-09-10):推进型 op 节点一律
    ``node_max_retry_times=2`` = 1 次推进 + 1 次重入观察裁决(验证废除后
    「单尝试合同」随之退役——M1③ 尝试概念消解,动作发出即职责完成,重试
    与否 = 观察驱动重决策,无人工尝试合同;账本 T-218 note 2026-09-10
    11:03:32 推定)。预算仍紧(其余重试归外循环),新 op 忘带即红。"""
    mods = [_progression_base, cw_screen_plane_detail,
            cw_screen_refresh_odds_popup, cw_screen_item_detail_popup,
            cw_screen_consumable_overlay, cw_screen_aha_equip_pick,
            cw_screen_prep_locked_return, cw_screen_role_detail_overlay,
            cw_screen_shop_card_detail,
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
            assert 'node_max_retry_times=2' in src, (
                f'{mod.__name__}.{name}: 推进 op 节点预算 ≠ 2(违反'
                f'「推进一击 + 重入裁决」合同,其余重试须归外循环)')


# ==================== A1 位面详情(重入裁决) ====================


def test_plane_detail_clicks_close_and_verifies(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-2 改写,验证废除批):标题命中 → 点「按钮-关闭位面详情」→
    机械交回 retry → 重入观察标题已消失 = success(验效半拆除,落地由
    重入裁决承载;出口语义 success 保持,0a4 bail 计数消费零漂移)。"""
    op, fc = _make_op(test_context, monkeypatch, cw_screen_plane_detail.CwScreenPlaneDetail)
    _stub_find(op, monkeypatch,
               [('货币战争-位面详情', '标识-位面详情标题')], misses_after=1)
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert result.success, f'位面详情关闭应成功(重入裁决):{result.status!r}'
    assert ('货币战争-位面详情', '按钮-关闭位面详情') in clicks


def test_plane_detail_verify_fail_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-3 改写,验证废除批):点 X 后标题仍在 → 重入再做一次推进
    (计节点预算 2),预算耗尽 FAIL bail(有界终止单;其余重试由外循环
    包装映射)。T-163 事故防线语义(点不掉 = 分钟级可见失败)保持。"""
    op, _fc = _make_op(test_context, monkeypatch, cw_screen_plane_detail.CwScreenPlaneDetail)
    # 入口命中(1 次)后重入裁决帧标题仍在(第 2 次起仍命中)
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
    """锁(验证废除批改写:入口命中 → 点「按钮-关闭概率表」建档中心
    (= 原 Point(1501,263),ADR-0584 §6.3-2 对拍离线腿);mouse_move bug#1
    缓解保留;原「点了就 success」骨架化为一击 + 重入裁决(锚消失 =
    success),桩 misses_after=1 模拟重入裁决帧锚已消失)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_refresh_odds_popup.CwScreenRefreshOddsPopup)
    _stub_find(op, monkeypatch, [('货币战争-商店刷新概率表', '标识-刷新概率表')],
               misses_after=1)
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
    """锁(验证废除批改写):「聘用书」命中 ∧ 非祈愿屏 → 点「按钮-关闭」
    建档中心(= 原 Point(1862,65),ADR-0584 §6.3-2 对拍离线腿);一击 +
    重入裁决(OCR 桩 misses_after=1 模拟裁决帧入口词已消失 = success)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_item_detail_popup.CwScreenItemDetailPopup)
    _stub_ocr(op, monkeypatch, {'聘用书': True}, misses_after=1)
    _stub_find(op, monkeypatch, [])

    result = _run(op)

    assert result.success, f'道具详情点×应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-道具详情弹窗', '按钮-关闭')
    hit = [p for p in fc.recorded_clicks if (p.x, p.y) == (1862, 65)]
    assert hit, f'点击落点应 = 原 Point(1862,65):{[str(p) for p in fc.recorded_clicks]}'


# ==================== A4/A7 ESC 族 ====================


def test_consumable_overlay_clicks_family_close(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(验证废除批改写):双 OCR 条件入口命中 → 点同族「道具详情弹窗/
    按钮-关闭」(×)(ESC 正形化清点批:ESC 在 modal 已自关时落备战误弹
    中断挑战,见 op 模块头);一击 + 重入裁决(OCR 桩 misses_after=1 模拟
    裁决帧入口词已消失 = success);入口不齐(缺「拖动到」)→ 不点击不按键。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_consumable_overlay.CwScreenConsumableOverlay)
    _stub_ocr(op, monkeypatch, {'消耗品': True, '拖动到': True}, misses_after=2)
    # (misses_after=2:entry_ok 每轮调 2 次 OCR,首轮双命中用掉配额,
    #  重入裁决帧起全 miss = 入口词已消失)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success, f'消耗品浮层点×应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-道具详情弹窗', '按钮-关闭')
    hit = [p for p in fc.recorded_clicks if (p.x, p.y) == (1862, 65)]
    assert hit, f'点击落点应 = 同族×建档中心:{[str(p) for p in fc.recorded_clicks]}'
    assert taps == [], '消耗品浮层禁 ESC'

    op2, _fc2 = _make_op(test_context, monkeypatch,
                         cw_screen_consumable_overlay.CwScreenConsumableOverlay)
    _stub_ocr(op2, monkeypatch, {'消耗品': True, '拖动到': False})
    taps2: list[str] = []
    monkeypatch.setattr(_fc2, 'btn_tap', lambda k: taps2.append(k), raising=False)
    result2 = _run(op2)
    assert not result2.success and taps2 == []


def test_role_detail_overlay_anchor_entry_blank_close_verify(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-4 改写,验证废除批;T-163 锚化语义保持):「装备推荐」锚
    命中即接管 → find_and_click 点面板外空白(区域-空白关闭 纯定位区,
    success_wait=1.5 等关闭动画)→ 机械交回 retry → 重入观察锚已消失 =
    success(0b bail 计数消费零漂移);全程零 ESC(锚化后旧「∨ 角色详情」
    全屏 OCR 判据退役,防与商店卡牌详情弹窗底部同名按钮全等撞车)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_role_detail_overlay.CwScreenRoleDetailOverlay)
    # 入口锚命中(第 1 次 find)后重入裁决帧锚消失(第 2 次起 miss)
    _stub_find(op, monkeypatch,
               [('货币战争-备战-角色详情', '按钮-装备推荐')], misses_after=1)
    click_calls: list[dict] = []

    def _click(screen, screen_name: str, area_name: str, **k: Any) -> Any:
        click_calls.append({'screen': screen_name, 'area': area_name, **k})
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _click)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success, f'详情弹窗点空白关应成功:{result.status!r}'
    assert click_calls == [{'screen': '货币战争-备战', 'area': '区域-空白关闭',
                            'success_wait': 1.5}], \
        f'推进点击应走 find_and_click(区域-空白关闭,等待 1.5s):{click_calls}'
    assert taps == [], '详情弹窗禁 ESC'


def test_role_detail_overlay_verify_fail_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-5 改写,验证废除批;T-163 D3「点了≠成了」防线语义保持):
    点空白后「装备推荐」仍在 → 重入再做一次推进(计节点预算 2),预算
    耗尽 FAIL 交外循环 retry 池(F2 后经 on_fail_retry 映射 round_retry,
    消费 retry 预算)。"""
    op, _fc = _make_op(test_context, monkeypatch,
                       cw_screen_role_detail_overlay.CwScreenRoleDetailOverlay)
    _stub_find(op, monkeypatch,
               [('货币战争-备战-角色详情', '按钮-装备推荐')])   # 恒命中 = 未消失
    _stub_find_and_click(op, monkeypatch, ok=True)
    result = _run(op)
    assert not result.success


# ==================== 0t 商店卡牌详情弹窗(T-163) ====================


def test_shop_card_detail_clicks_x_and_verifies(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-6 改写,验证废除批;T-163 D1/D3 语义保持):双 id_mark 锚
    (购买∧角色详情)命中 → 点 X(建档「按钮-关闭」)→ 机械交回 retry →
    重入观察 X 已消失 = success;**绝不点购买**(买不买归商店域,关闭动作
    不代替购买决策);零 ESC。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_shop_card_detail.CwScreenShopCardDetailPopup)
    # 入口两次探锚(购买+角色详情)命中后,重入裁决帧 X 消失(第 3 次 find 起 miss)
    _stub_find(op, monkeypatch,
               [('货币战争-商店卡牌详情', '按钮-购买'),
                ('货币战争-商店卡牌详情', '按钮-角色详情')], misses_after=2)
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)

    result = _run(op)

    assert result.success, f'商店卡牌详情点X关应成功(重入裁决):{result.status!r}'
    assert clicks == [('货币战争-商店卡牌详情', '按钮-关闭')], \
        f'只许点 X 关闭:{clicks}'
    assert taps == [], '商店卡牌详情禁 ESC'


def test_shop_card_detail_verify_fail_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(L1-7 改写,验证废除批;T-163 事故机理回归):X 点击后 X 仍在
    (点击零效果)→ 重入再做一次,预算耗尽 FAIL 交外循环 retry 池——
    26min 不可见死循环防线(锚在即红)保持。"""
    op, _fc = _make_op(test_context, monkeypatch,
                       cw_screen_shop_card_detail.CwScreenShopCardDetailPopup)
    # 全锚恒命中(含裁决锚 按钮-关闭)= 点 X 后 X 仍在(点击零效果形态)
    _stub_find(op, monkeypatch,
               [('货币战争-商店卡牌详情', '按钮-购买'),
                ('货币战争-商店卡牌详情', '按钮-角色详情'),
                ('货币战争-商店卡牌详情', '按钮-关闭')])
    _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert not result.success


def test_shop_card_detail_single_anchor_entry_fails_without_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁:单锚形态(仅「购买」命中,如其他带购买按钮的弹窗)→ 入口 fail
    不点击(双锚全中才接管,防误吞同族弹窗)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_shop_card_detail.CwScreenShopCardDetailPopup)
    _stub_find(op, monkeypatch,
               [('货币战争-商店卡牌详情', '按钮-购买')])
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert not result.success
    assert clicks == [] and fc.recorded_clicks == []


# ==================== A5 阿哈装备(固定策略申报) ====================


def test_aha_equip_clicks_first_equip_area(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(验证废除批改写):锚命中 → 点「按钮-简易装备首件」建档中心
    (= 原 Point(626,250),ADR-0584 §6.3-2 对拍离线腿);固定策略 = 点首件;
    一击 + 重入裁决(桩 misses_after=1 模拟裁决帧锚已消失 = success)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_aha_equip_pick.CwScreenAhaEquipPick)
    _stub_find(op, monkeypatch, [('货币战争-备战', '标识-简易装备')],
               misses_after=1)

    result = _run(op)

    assert result.success, f'阿哈装备点首件应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-备战', '按钮-简易装备首件')
    hit = [p for p in fc.recorded_clicks if (p.x, p.y) == (626, 250)]
    assert hit, f'点击落点应 = 原 Point(626,250):{[str(p) for p in fc.recorded_clicks]}'


# ==================== A6 备战暗色锁定(参数化) ====================


def test_prep_locked_return_parameterized_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(验证废除批改写):构造画面档对 → 入口与点击同一按钮锚;另一
    画面档不误判;一击 + 重入裁决(桩 misses_after=1 模拟裁决帧锚已消失)。"""
    op, fc = _make_op(
        test_context, monkeypatch, cw_screen_prep_locked_return.CwScreenPrepLockedReturn,
        '货币战争-备战-策略锁定', '按钮-返回投资策略选择')
    _stub_find(op, monkeypatch,
               [('货币战争-备战-策略锁定', '按钮-返回投资策略选择')],
               misses_after=1)
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
    """锁(L1-8 改写,验证废除批):双锚其一(套组标题)命中 → 点
    「按钮-关闭」→ 机械交回 retry → 重入观察锚已不在 = success;**禁 ESC**
    (bug#2:面板已关时 ESC 落备战弹中断挑战)。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_emblem_detail_popup.CwScreenEmblemDetailPopup)
    # 第一锚 miss、第二锚(套组标题)命中;misses_after=2 辖入口两次探锚,
    # 重入裁决(第 3 次 find)不再命中
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


def test_interrupt_dialog_clicks_close(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(验证废除批改写;删除波 1 重写:popup 行随 exogenous 流写入端
    退役):锚命中 → 点「按钮-关闭」+ park_cursor;一击 + 重入裁决
    (桩 misses_after=1 模拟裁决帧锚已消失 = success);绝不点「放弃并结算」。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_interrupt_dialog.CwScreenInterruptDialog)
    _stub_find(op, monkeypatch, [('货币战争-中断挑战弹窗', '标识-中断挑战')],
               misses_after=1)
    clicks = _stub_find_and_click(op, monkeypatch, ok=True)

    result = _run(op)

    assert result.success
    assert ('货币战争-中断挑战弹窗', '按钮-关闭') in clicks


def test_interrupt_dialog_x_retry_then_bounded_fail(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(C10 拆除改写,验证废除批):X 点击失败(按钮不在 = 旧帧)→
    恰一次动作即有界 fail 交外循环(op 内新帧重试拆除——重试归外循环重派,
    重派即新帧,语义等价);全程零 ESC,不静默兜过。"""
    op, fc = _make_op(test_context, monkeypatch,
                      cw_screen_interrupt_dialog.CwScreenInterruptDialog)
    _stub_find(op, monkeypatch, [('货币战争-中断挑战弹窗', '标识-中断挑战')])
    clicks = _stub_find_and_click(op, monkeypatch, ok=False)
    taps: list[str] = []
    monkeypatch.setattr(fc, 'btn_tap', lambda k: taps.append(k), raising=False)
    monkeypatch.setattr(fc, 'esc', lambda: taps.append('esc'), raising=False)

    result = _run(op)

    assert not result.success   # 有界 fail(节点单尝试合同),非静默成功
    assert len(clicks) == 1, f'应恰一次动作(op 内新帧重试已拆除):{clicks}'
    assert taps == [], '中断挑战弹窗禁 ESC'


# ==================== A10 前进按钮 ====================


def test_next_button_ocr_click(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁(验证废除批改写):OCR「下一步」命中 → ocr_and_click 推进
    (success_wait=2 同原值);一击 + 重入裁决(OCR 桩 misses_after=1 模拟
    裁决帧入口词已消失 = success);断言面仅命中臂——miss 臂走基类 handle
    入口锚 miss 路径,与全部推进 op 同一继承代码,由
    test_plane_detail_entry_miss_fails_without_click 辖。"""
    op, _fc = _make_op(test_context, monkeypatch, cw_screen_next_button.CwScreenNextButton)
    _stub_ocr(op, monkeypatch, {'下一步': True}, misses_after=1)
    click_calls: list[dict] = []

    def _ocr_click(screen, target_cn: str, **k: Any) -> Any:
        click_calls.append({'target': target_cn, **k})
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_ocr_and_click', _ocr_click)

    result = _run(op)

    assert result.success
    assert click_calls and click_calls[0]['target'] == '下一步'
    assert click_calls[0].get('success_wait') == 2
