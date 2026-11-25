"""开拓商店买卡/刷新 op 剧本测试(harness;守卫分支 + 补位/生效验证分支)。

锁的设计约定(被测单一源 = cw_buy_train_shop_card / cw_refresh_train_shop;
读法标定证据帧 = sr-od-test/screens/货币战争-备战-开拓商店/panel_*_r13、
panel_slots_{d,e}_r15):

- 构造守卫:买槽 slot 值域 1-4(刷新钮轮转占位,占用槽由快照节点执行期
  判出显式 fail),越界 ValueError 带可用值;
- 面板态守卫:非开拓商店画面 fail / 中央展示卡态 fail(软锁守卫,真帧 =
  panel_showcase_r13〔首开空池〕,详情按钮锚真 OCR 判定,零点击零消耗;
  恢复态死锁帧画面同构,同判据同出口,不重复设用例)/ 刷新钮不在场 fail
  (r15 帧四槽全商品真帧,刷新 op 专属出口);
- 补位验证分支(读链打桩):名行变化或帕姆推进任一命中 → success 带
  前后对照 data;均未变化 → fail(不重试不重点,防重复购买);验证帧名行
  读空不得当补位(瞬时失读 ≠ 补位);目标槽是刷新钮(名行锚)→ fail 不误买;
- 刷新生效验证分支:余额扣减 / 槽带变化 / 帕姆推进三选一;刷新钮轮转
  占位(打桩定位槽 4)点击随槽位;
- MCP 反射面:describe_operation 透出参数口径与守卫/验证出口。

真帧只进守卫判定(test_context 真实 OCR,memo 温缓存);快照/验证读链
monkeypatch 打桩(读数真值由 test_cw_trainshop_obs 真帧测试分头锁定)。
点击期望坐标 = 商品卡-N 建档 rect 中心(同 test_cw_toggle_shop_panel
「建档 rect 中心同源现算」先例口径)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

import sr_od.application.currency_war.operations.actions.cw_buy_train_shop_card as buy_mod
import sr_od.application.currency_war.operations.actions.cw_refresh_train_shop as refresh_mod
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.kernel.cw_obs_core import (
    PIONEER_SHOP_SCREEN_NAME,
)
from sr_od.application.currency_war.operations.actions.cw_buy_train_shop_card import (
    CwBuyTrainShopCard,
)
from sr_od.application.currency_war.operations.actions.cw_refresh_train_shop import (
    CwRefreshTrainShop,
)

_SCREEN: str = '货币战争-备战-开拓商店'
#: 槽带态帧(第十一局 013815,槽 1 = 刷新钮形态)/ 中央展示卡态帧(首开空池
#: 软锁 013105)/ 四槽全商品帧(第二十四局 1-6 首购前,刷新钮不在场形态)。
_SLOTS_FRAME: tuple[str, str] = (_SCREEN, 'panel_slots_a_r13')
_SHOWCASE_FRAME: tuple[str, str] = (_SCREEN, 'panel_showcase_r13')
_FULL4_FRAME: tuple[str, str] = (_SCREEN, 'panel_slots_d_r15')

_FULL_BUY_OP_ID: str = ('sr_od.application.currency_war.operations.actions.'
                        'cw_buy_train_shop_card.CwBuyTrainShopCard')
_FULL_REFRESH_OP_ID: str = ('sr_od.application.currency_war.operations.actions.'
                            'cw_refresh_train_shop.CwRefreshTrainShop')


class _WatchedBuy(WatchdogOperationMixin, CwBuyTrainShopCard):
    """带看门狗的买卡 op(流程测试防无限轮)。"""


class _WatchedRefresh(WatchdogOperationMixin, CwRefreshTrainShop):
    """带看门狗的刷新 op(流程测试防无限轮)。"""


def _patch_reads(monkeypatch: pytest.MonkeyPatch, module,
                 lines: list[tuple[str, int | None]],
                 pams: list[tuple[int, int] | None],
                 balances: list[int | None] | None = None) -> None:
    """按调用序打桩模块内读链(第 N 次调用返第 N 值,越界复读末值)。"""
    seq = {'line': 0, 'pam': 0, 'bal': 0}

    def fake_line(ctx, screen, idx):
        v = lines[min(seq['line'], len(lines) - 1)]
        seq['line'] += 1
        return v

    def fake_pam(ctx, screen):
        v = pams[min(seq['pam'], len(pams) - 1)]
        seq['pam'] += 1
        return v

    def fake_bal(ctx, screen):
        if not balances:
            return None
        v = balances[min(seq['bal'], len(balances) - 1)]
        seq['bal'] += 1
        return v

    monkeypatch.setattr(module, 'read_trainshop_slot_line', fake_line)
    monkeypatch.setattr(module, 'read_pam_progress', fake_pam)
    if hasattr(module, 'read_trainshop_balance'):   # 刷新 op 独有读链
        monkeypatch.setattr(module, 'read_trainshop_balance', fake_bal)


def _run_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
            op, phases: list[dict]) -> tuple[FixtureController, OperationResult]:
    """装假控制器 + 跑完整 execute(),返回(控制器, 结果)供断言。

    ``op`` = 已构造好的 watched op(构造参数守卫在生产 __init__ 内,测试
    直构 watched 类继承的同一构造链)。
    """
    ctrl = FixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases(phases)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result


def _require_screens(test_context: SrTestContext,
                     frames: list[tuple[str, str]]) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in frames:
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _area_center(test_context: SrTestContext, area_name: str) -> tuple[int, int]:
    """商品卡-N 建档 rect 中心(期望坐标与被测同源:screen_info 单一真相源)。"""
    area = test_context.screen_loader.get_area(PIONEER_SHOP_SCREEN_NAME,
                                               area_name)
    assert area is not None and area.pc_rect is not None, f'缺 {area_name} area'
    rect = area.pc_rect
    return (rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2


class TestBuyTrainShopCard:
    """CwBuyTrainShopCard:构造守卫 + 守卫分支 + 补位验证分支。"""

    def test_slot_domain_guard(self, test_context: SrTestContext) -> None:
        """越界槽:构造期 ValueError 带可用值 1-4(刷新钮占用槽执行期判)。"""
        for bad in (5, 0, -1):
            with pytest.raises(ValueError, match='1-4'):
                CwBuyTrainShopCard(test_context, slot=bad)

    def test_wrong_screen_fails(self, test_context: SrTestContext,
                                monkeypatch: pytest.MonkeyPatch) -> None:
        """非开拓商店画面(备战帧):入口判定 fail,零点击。"""
        prep_frame = ('货币战争-备战', 'shop_closed')
        _require_screens(test_context, [prep_frame])
        op = _WatchedBuy(test_context, slot=3)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': prep_frame}])
        assert not result.success
        assert '不在开拓商店面板' in result.status
        assert ctrl.recorded_clicks == []

    def test_showcase_softlock_guard_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """中央展示卡态真帧(软锁):守卫 fail 带解锁路径提示,零点击。"""
        _require_screens(test_context, [_SHOWCASE_FRAME])
        op = _WatchedBuy(test_context, slot=3)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SHOWCASE_FRAME}])
        assert not result.success
        assert '中央展示卡' in result.status
        assert '解锁' in result.status
        assert ctrl.recorded_clicks == []

    def test_buy_slot1_on_full4_frame(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """四槽全商品帧(槽 1 = 商品)买槽 1:守卫不再误判展示卡态 → 跑通。

        r15 首购前帧 = 旧读层把四槽带误判 showcase、op 拒买的证据帧;
        修后槽 1 合法(值域 1-4),快照→直购→帕姆推进判补位。
        """
        _require_screens(test_context, [_FULL4_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('星期日', 35), ('幸运一击率Ⅰ', 15)],
            pams=[(15, 500), (30, 500)])
        op = _WatchedBuy(test_context, slot=1, expect_name='星期日')
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _FULL4_FRAME}])
        assert result.success, f'status={result.status}'
        assert result.data['slot'] == 1
        assert result.data['pam_before'] == [15, 500]
        assert result.data['pam_after'] == [30, 500]
        assert len(ctrl.recorded_clicks) == 1
        assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == \
            _area_center(test_context, '商品卡-1')

    def test_buy_refresh_slot_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """目标槽是「全部刷新」钮(轮转占位,快照名行锚判出):fail 不误买。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('全部刷新', 1)],
            pams=[(0, 500)])
        op = _WatchedBuy(test_context, slot=1)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert not result.success
        assert '全部刷新' in result.status
        assert 'CwRefreshTrainShop' in result.status
        assert ctrl.recorded_clicks == []

    def test_buy_success_refill(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """槽带态买槽 3:快照→直购点击→名行变化判补位 → success 带对照。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('三月七', 15), ('幸运一击率Ⅰ', 15)],
            pams=[(0, 500), (15, 500)])
        op = _WatchedBuy(test_context, slot=3, expect_name='三月七')
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert result.success, f'status={result.status}'
        assert result.data['slot'] == 3
        assert result.data['old_name'] == '三月七'
        assert result.data['new_name'] == '幸运一击率Ⅰ'
        assert result.data['pam_after'] == [15, 500]
        # 直购点击 = 商品卡-3 建档 rect 中心,恰好一次
        assert len(ctrl.recorded_clicks) == 1
        assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == \
            _area_center(test_context, '商品卡-3')

    def test_buy_pam_advance_counts_as_refill(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """同名同价补位(池重摇同名卡)由帕姆推进兜证 → success。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('后台强度Ⅰ', 15), ('后台强度Ⅰ', 15)],
            pams=[(45, 500), (60, 500)])
        op = _WatchedBuy(test_context, slot=4)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert result.success, f'status={result.status}'
        assert result.data['pam_before'] == [45, 500]
        assert result.data['pam_after'] == [60, 500]
        assert len(ctrl.recorded_clicks) == 1

    def test_buy_no_effect_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """点击被吞(名行/帕姆均未变化):fail 带对照值,不重点(防重复购买)。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('三月七', 15), ('三月七', 15)],
            pams=[(0, 500), (0, 500)])
        op = _WatchedBuy(test_context, slot=3)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert not result.success
        assert '买槽未生效' in result.status
        assert len(ctrl.recorded_clicks) == 1

    def test_buy_blank_line_not_refill(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """验证帧名行瞬时读空:不充当补位证据 → fail。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, buy_mod,
            lines=[('三月七', 15), ('', None)],
            pams=[(0, 500), None])
        op = _WatchedBuy(test_context, slot=3)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert not result.success
        assert '买槽未生效' in result.status
        assert len(ctrl.recorded_clicks) == 1

    def test_describe_surfaces_params_and_exits(self) -> None:
        """MCP 反射面:describe_operation 透出槽值域口径与守卫/验证出口。"""
        from sr_od.backend.operation_registry import describe_operation

        info = describe_operation(None, _FULL_BUY_OP_ID)
        doc = info['docstring'] or ''
        assert '1-4' in doc, 'describe 未透出槽值域'
        assert '轮转占位' in doc, 'describe 未透出刷新钮轮转占位口径'
        assert '中央展示卡' in doc, 'describe 未透出软锁守卫出口'
        assert '补位' in doc, 'describe 未透出补位验证出口'
        assert any(p['name'] == 'slot' for p in info['params'])
        assert any(p['name'] == 'expect_name' for p in info['params'])


class TestRefreshTrainShop:
    """CwRefreshTrainShop:守卫分支 + 生效验证分支(余额/槽带/帕姆三选一)。"""

    def test_showcase_softlock_guard_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """中央展示卡态真帧:无刷新钮可点,守卫 fail,零点击。"""
        _require_screens(test_context, [_SHOWCASE_FRAME])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SHOWCASE_FRAME}])
        assert not result.success
        assert '中央展示卡' in result.status
        assert ctrl.recorded_clicks == []

    def test_refresh_absent_button_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """刷新钮不在场(r15 帧四槽全商品真帧,定位真 OCR):fail 零点击。

        旧守卫把该帧误报「中央展示卡态」;修后显式「刷新钮不在场」出口
        (轮转占位口径:候出现帧再刷),文案不再误导调用方去点展示卡。
        """
        _require_screens(test_context, [_FULL4_FRAME])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _FULL4_FRAME}])
        assert not result.success
        assert '刷新钮不在场' in result.status
        assert ctrl.recorded_clicks == []

    def test_refresh_rotated_slot4_click(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """刷新钮轮转占位(打桩定位槽 4,第二十四局 2-4 实拍形态):点击随槽位。

        守卫详情锚走 r13 真帧(4/4);find_refresh_slot 打桩返 4 模拟轮转
        占位——r13/r15 真帧都无槽 4 刷新钮形态 fixture,定位读链真值由
        test_cw_trainshop_obs 真帧分头锁定,此处只锁「点击落定位槽」。
        """
        _require_screens(test_context, [_SLOTS_FRAME])
        monkeypatch.setattr(refresh_mod, 'find_refresh_slot',
                            lambda ctx, screen: 4)
        _patch_reads(
            monkeypatch, refresh_mod,
            lines=[('后台强度Ⅰ', 15)] * 2,
            pams=[(0, 500), (0, 500)],
            balances=[100, 99])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert result.success, f'status={result.status}'
        assert result.data['balance_before'] == 100
        assert result.data['balance_after'] == 99
        assert len(ctrl.recorded_clicks) == 1
        assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == \
            _area_center(test_context, '商品卡-4')

    def test_refresh_success_by_balance_drop(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """池同 roll 名行不变时余额扣减兜证 → success;点击落槽 1 中心。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, refresh_mod,
            lines=[('全部刷新', 1)] * 2,
            pams=[(0, 500), (0, 500)],
            balances=[20, 19])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert result.success, f'status={result.status}'
        assert result.data['balance_before'] == 20
        assert result.data['balance_after'] == 19
        assert len(ctrl.recorded_clicks) == 1
        assert (ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y) == \
            _area_center(test_context, '商品卡-1')

    def test_refresh_success_by_pam_advance(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """刷新计消费口径:余额失读(两侧 None)时帕姆推进兜证 → success。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, refresh_mod,
            lines=[('全部刷新', 1)] * 2,
            pams=[(15, 500), (16, 500)],
            balances=[None, None])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert result.success, f'status={result.status}'

    def test_refresh_no_effect_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """三证据全无:fail 带对照值,不重点。"""
        _require_screens(test_context, [_SLOTS_FRAME])
        _patch_reads(
            monkeypatch, refresh_mod,
            lines=[('全部刷新', 1)] * 2,
            pams=[(0, 500), (0, 500)],
            balances=[20, 20])
        op = _WatchedRefresh(test_context)
        ctrl, result = _run_op(test_context, monkeypatch, op,
                               [{'frame': _SLOTS_FRAME}])
        assert not result.success
        assert '刷新未生效' in result.status
        assert len(ctrl.recorded_clicks) == 1

    def test_describe_surfaces_params_and_exits(self) -> None:
        """MCP 反射面:describe_operation 透出消耗口径与守卫/验证出口。"""
        from sr_od.backend.operation_registry import describe_operation

        info = describe_operation(None, _FULL_REFRESH_OP_ID)
        doc = info['docstring'] or ''
        assert '1 开拓力' in doc, 'describe 未透出消耗口径'
        assert '轮转占位' in doc, 'describe 未透出刷新钮轮转占位口径'
        assert '中央展示卡' in doc, 'describe 未透出软锁守卫出口'
        assert '不在场' in doc, 'describe 未透出不在场守卫出口'
        assert any(p['name'] == 'expect_note' for p in info['params'])
