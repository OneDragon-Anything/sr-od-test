"""r317 退局 op 投资策略屏卡点机制根修测试(第三次实录 2026-08-25)。

实录:ExitCurrencyWarMatch 卡投资策略屏 141x「等待」循环(444s+),零分支推进。
三个机制根因(2026-08-25 实录 + 离线验证):

① :76「备战阶段」裸 OCR(lcs=0.5)在投资策略屏误命中「返回备战界面」
   (LCS「备战」2/4=0.5;find_by_ocr 直接 LCS 匹配、无 difflib 前置过滤)
   → 每轮 esc(无效)→ round_wait 死循环(实录零 [cw-exit] 日志的真首卡点);
② :73「返回备战界面」全屏 OCR 点击 OCR 检测框中心 (1790,57),但按钮热区
   中心 ≈ (1850,60)(像素实测,OCR 框 1717-1863 vs 底框 1780-1920)
   → 点击落空 → 若走到此分支同样死循环;
③ 分支顺序:投资策略屏(独立屏)必须**先**走「选卡+确认」(area 定位,
   手动 (460,475)+(978,984) 实证有效),不能被①/②短路。

根修(机制层,非坐标):① 备战阶段 lcs=0.8;②/③ 投资策略分支移到
「返回备战界面」之前 + 结算按钮 OCR 统一 lcs=0.8(battle_loop 3b 同款,
防「继续挑战」误匹配战斗暂停屏「继续战斗」ratio=0.75)。
"""
from __future__ import annotations

import inspect

import pytest

from one_dragon.base.geometry.point import Point
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


class _ExitFixtureController(FixtureController):
    """补真机控制器才有的 stub:btn_tap/mouse_move(纯 op 流程测试用)。"""

    def btn_tap(self, key: str) -> None:
        pass

    def mouse_move(self, game_pos: Point) -> None:
        pass


class _WatchedExit(WatchdogOperationMixin, ExitCurrencyWarMatch):
    """带看门狗的退局 op(防 WAIT 段死循环)。"""


def test_invest_strategy_branch_before_return_btn() -> None:
    """顺序锁:投资策略分支(选卡+确认)必须在「返回备战界面」分支之前。

    回归防:若「返回备战界面」(全屏 OCR)被放回前面,投资策略屏会先被它命中
    并点击落空 → 死循环复现(r317 根修点 ②③)。
    """
    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    pos_invest = src.index("'标识-请选择投资策略'")
    pos_return = src.index("'返回备战界面'")
    assert pos_invest < pos_return, (
        '投资策略分支必须在「返回备战界面」之前(投资策略屏正确退出=选卡+确认,'
        '非点返回按钮;r317 根修点 ②③)'
    )


def test_settlement_ocr_lcs_tightened() -> None:
    """lcs 锁:结算按钮 OCR 统一 lcs_percent=0.8(防「继续战斗」误匹配)。

    回归防:若「继续挑战」退回默认 0.5,战斗暂停屏「继续战斗」(ratio 0.75)
    会被当结算按钮点击 → 恢复战斗 → 退局打转(r317 根修点 ②,实录 03:59:35-
    04:01:35 段)。
    """
    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    for btn in ('继续挑战', '下一步', '下一页', '返回货币战争', '返回备战界面'):
        # 每个 round_by_ocr_and_click 调用都应带 lcs_percent=0.8
        idx = src.index(f"'{btn}'")
        call_region = src[idx:idx + 80]
        assert 'lcs_percent=0.8' in call_region, (
            f'按钮 {btn} 的 OCR 调用应收紧 lcs_percent=0.8(r317 根修点 ②)'
        )


def test_battle_prep_detection_area_based() -> None:
    """T#103 化债锁:「备战阶段」检测走 screen_info area(标识-备战阶段),
    裸 OCR 调用退役。

    r317 曾以 lcs=0.8 收紧裸 OCR(默认 0.5 在投资策略屏误命中「返回备战界面」);
    T#103 建 positional rect 后误配面被结构性消灭,回归面 = 别再退回全屏扫。
    """
    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    assert "'标识-备战阶段'" in src, (
        '「备战阶段」检测应使用 screen_info 标识-备战阶段 area(T#103)'
    )
    assert "round_by_ocr(screen, '备战阶段'" not in src, (
        '「备战阶段」不应再走全屏 OCR(r317 误配史:T#103 已 area 化,勿回退)'
    )


def test_invest_strategy_screen_takes_select_confirm_path(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """集成锁:投资策略屏 fixture → op 走「选卡+确认」,不点「返回备战界面」。

    剧本:投资策略屏(默认态)→ 点左卡推进 → 投资策略屏(已选卡)→ 点确认推进
    → 大厅(terminal)。断言:点击序列含左卡 (460,475) 与确认 area 中心
    (978,983),且无任何点击落在「返回备战界面」按钮区(右上角 x>1700)。
    """
    phases = [
        {  # 投资策略屏默认态:点左卡 (460,475) 选中 → 推进
            'frame': ('货币战争-投资策略', 'default'),
            'exit': ('on_click_in', [400, 450, 520, 500]),
        },
        {  # 投资策略屏已选卡:点确认 (978,983) → 推进
            'frame': ('货币战争-投资策略', 'card1_selected'),
            'exit': ('on_click_in', '货币战争-投资策略', '按钮-确认'),
        },
        {  # 大厅:terminal(退局完成)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    for screen_name, state in (p['frame'] for p in phases):
        if not test_context.has_screen(screen_name, state):
            return  # fixture 缺失则跳过(非失败)

    ctrl = _ExitFixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    ctrl.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', ctrl)

    op = _WatchedExit(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, (
        f'投资策略屏退局应成功回大厅:status={result.status};'
        f'phase_idx={ctrl.phase_idx}'
    )
    # 选卡+确认路径点击(area 中心/手动实证点)
    clicks = ctrl.recorded_clicks
    assert any(
        abs(p.x - 460) <= 20 and abs(p.y - 475) <= 20 for p in clicks
    ), f'应点击左卡 (460,475),实际点击={clicks}'
    assert any(
        abs(p.x - 978) <= 20 and abs(p.y - 983) <= 20 for p in clicks
    ), f'应点击确认 area 中心 (978,983),实际点击={clicks}'
    # 不应点击「返回备战界面」按钮区(右上角)——r317 根修点 ②③
    assert not any(p.x > 1700 and p.y < 120 for p in clicks), (
        f'不应点击右上角「返回备战界面」按钮区(点击落空死循环根因),实际点击={clicks}'
    )
