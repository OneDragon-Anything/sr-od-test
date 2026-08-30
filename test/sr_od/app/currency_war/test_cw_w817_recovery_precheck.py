"""w817 启动恢复态预检测试。

病灶(局10/11 实证):上局中途停机后客户端停在「战斗暂停/关卡信息」面板,
app 起跑时 ``_in_match`` 把它判成「已在对局中」(带 货币战争- 前缀)跳过
enter/start 交 loop,loop 不识该面板 → 局10 死于「右上角返回」节点 /
局11 死于「持久未识别画面」停机钩子。

修复:``CurrencyWarApp._enter_lobby`` / ``_start_match`` 入口先做恢复态预检
(「战斗暂停」独有文本锚),命中 → 委托 ``ExitCurrencyWarMatch`` 走
撤退 → 放弃并结算 → 下一步 → 大厅 恢复链(编排者手动实机验证范式),
回大厅后继续正常启动流;未命中零介入(正常启动只多一次小区域 OCR)。

覆盖:
1. 识别锁:恢复态 fixture 命中「标识-战斗暂停」area;大厅 fixture 不命中(负例)。
2. 恢复链触发:暂停面板帧起跑 → 三步恢复点击按序落在对应 area → 落回大厅。
3. 零介入:大厅帧起跑 → 零点击、零恢复动作。
"""
from __future__ import annotations

import pytest
from cv2.typing import MatLike

from sr_od.application.currency_war import currency_war_app as cw_app_module
from sr_od.application.currency_war.currency_war_app import CurrencyWarApp
from sr_od.application.currency_war.operations.entry.exit_currency_war_match import (
    ExitCurrencyWarMatch,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# ---------------------------------------------------------------------------
# 识别锁(fixture 级,离线 OCR,无 controller)
# ---------------------------------------------------------------------------


def _rect_has_text(ctx: SrTestContext, screen: MatLike, area_screen: str,
                   area_name: str, kw: str) -> bool:
    """在指定 area 的 pc_rect 内做 OCR,判关键词是否出现。"""
    area = ctx.screen_loader.get_area(area_screen, area_name)
    assert area is not None, f'area 未建档:{area_screen}/{area_name}'
    texts = [m.data for m in ctx.ocr_service.get_ocr_result_list(
        image=screen, rect=area.pc_rect)]
    return any(kw in t for t in texts)


def test_pause_fixture_hits_mark(test_context: SrTestContext) -> None:
    """恢复态 fixture:战斗暂停锚在画面上(预检正例)。"""
    screen = test_context.load_screen(CurrencyWarApp.PAUSE_SCREEN, 'paused')
    assert _rect_has_text(test_context, screen,
                          CurrencyWarApp.PAUSE_SCREEN, CurrencyWarApp.PAUSE_MARK,
                          '战斗暂停'), '暂停面板帧应命中「标识-战斗暂停」area'


def test_lobby_fixture_no_pause_mark(test_context: SrTestContext) -> None:
    """负例:大厅帧在战斗暂停锚 rect 内无该文本(正常启动不触发预检)。"""
    screen = test_context.load_screen('货币战争-大厅', 'lobby')
    assert not _rect_has_text(test_context, screen,
                              CurrencyWarApp.PAUSE_SCREEN, CurrencyWarApp.PAUSE_MARK,
                              '战斗暂停')


def test_pause_screen_areas_onboarded() -> None:
    """恢复链依赖的 screen_info area 齐:标识 + 三按钮(撤退/重新挑战/继续战斗)。"""
    import yaml

    with open('assets/game_data/screen_info/currency_war_battle_pause.yml',
              encoding='utf-8') as f:
        d = yaml.safe_load(f)
    names = {a['area_name'] for a in d['area_list']}
    assert {'标识-战斗暂停', '按钮-撤退', '按钮-重新挑战',
            '按钮-继续战斗'} <= names


# ---------------------------------------------------------------------------
# 恢复链行为测试(FixtureController 剧本)
# ---------------------------------------------------------------------------


class _WatchedExitCurrencyWarMatch(WatchdogOperationMixin, ExitCurrencyWarMatch):
    """带看门狗的退局 op(防恢复链 WAIT 死循环拖挂测试)。"""


def _recovery_phases() -> list[dict]:
    """暂停面板 → 撤退 → 放弃并结算 → 下一步 → 大厅(手动验证范式)。"""
    return [
        {
            'frame': ('货币战争-战斗暂停', 'paused'),
            'exit': ('on_click_in', '货币战争-战斗暂停', '按钮-撤退'),
        },
        {
            'frame': ('货币战争-中断挑战弹窗', 'open'),
            'exit': ('on_click_in', '货币战争-中断挑战弹窗', '按钮-放弃并结算'),
        },
        {
            'frame': ('货币战争-挑战失败', 'failed'),
            'exit': ('on_click_in', '货币战争-挑战失败', '按钮-下一步'),
        },
        {  # 大厅:恢复链终点(exit op 大厅锚命中 → success;预检后回大厅)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    return ctrl


def _require_screens(test_context: SrTestContext, phases: list[dict]) -> None:
    for phase in phases:
        screen_name, state = phase['frame']
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _patch_watched_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """app 内构造的退局 op 换成看门狗版(防死循环)。"""
    def _factory(ctx) -> ExitCurrencyWarMatch:
        op = _WatchedExitCurrencyWarMatch(ctx)
        op._init_watchdog()  # type: ignore[attr-defined]
        return op
    monkeypatch.setattr(cw_app_module, 'ExitCurrencyWarMatch', _factory)


def test_pause_panel_triggers_recovery_chain_to_lobby(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """暂停面板起跑:预检命中 → 恢复链三点击按序落地 → 回大厅。"""
    phases = _recovery_phases()
    _require_screens(test_context, phases)
    _patch_watched_exit(monkeypatch)
    fixture_controller.set_phases(phases)

    app = CurrencyWarApp(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)

    assert result.is_success, f'恢复链未走通到大厅:status={result.status}'
    assert fixture_controller.click_hit_area('货币战争-战斗暂停', '按钮-撤退'), (
        f'未点「撤退」:{fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area('货币战争-中断挑战弹窗', '按钮-放弃并结算'), (
        f'未点「放弃并结算」:{fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area('货币战争-挑战失败', '按钮-下一步'), (
        f'未点「下一步」:{fixture_controller.recorded_clicks}')
    # 恢复链终点 = 大厅(末 phase),此后正常启动流接管
    assert fixture_controller.phase_idx == len(phases) - 1

    # 回大厅后重跑入口节点:走「已在 CW」常规分支,不再触发恢复
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result2 = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)
    assert result2.is_success and result2.status == '已在 CW(大厅/对局中),跳过 enter', (
        f'回大厅后应走常规分支:status={result2.status}')


def test_normal_lobby_start_zero_intervention(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """正常启动(大厅帧):预检零介入 —— 零点击、直接走「已在 CW」分支。"""
    phases = [{'frame': ('货币战争-大厅', 'lobby')}]
    _require_screens(test_context, phases)
    fixture_controller.set_phases(phases)

    app = CurrencyWarApp(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep():
            app.screenshot()
            result = app._enter_lobby()
    finally:
        reset_running_state(test_context, app)

    assert result.is_success and result.status == '已在 CW(大厅/对局中),跳过 enter', (
        f'大厅帧应走常规分支:status={result.status}')
    assert fixture_controller.recorded_clicks == [], (
        f'正常启动不应有任何恢复介入点击:{fixture_controller.recorded_clicks}')
