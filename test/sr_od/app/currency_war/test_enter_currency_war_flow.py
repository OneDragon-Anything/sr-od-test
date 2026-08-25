"""EnterCurrencyWar 入口分流测试(fixture 驱动;2026-08-17 修复回归)。

修复背景(18:29 事故):传送已落地/恢复场景下,「前往参与」节点因按钮不在画面判死
(3 次「找不到 前往参与」→ op 失败),而画面已在朝露公馆入口只差按 F。修复后按钮
不在 → round_success 交给 wait_lobby 分流(入口按 F / 指南页重点击 / 大厅即成功)。

剧本(指南两步用替身 op,聚焦被修节点的分流行为):
大世界普通 →(已传送)朝露公馆入口(无「前往参与」)→ F → 货币战争大厅。
"""
from __future__ import annotations

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.operations.entry import enter_currency_war
from sr_od.application.currency_war.operations.entry.enter_currency_war import (
    EnterCurrencyWar,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _WatchedEnterCurrencyWar(WatchdogOperationMixin, EnterCurrencyWar):
    """带看门狗的 EnterCurrencyWar(防 WAIT 段死循环)。"""


class _FakeGuideStepOp:
    """打开指南 / 选择 TAB 的替身:直接成功(本测试聚焦「前往参与」节点分流)。"""

    def __init__(self, *args, **kwargs) -> None:  # 与真 op 构造签名解耦(ctx / ctx+tab)
        pass

    def execute(self) -> OperationResult:
        return OperationResult(success=True, status='mock-成功')


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
    # 指南两步替身(真实 GuideOpen/GuideChooseTab 需要大世界导航链 fixture,超出本测试焦点)
    monkeypatch.setattr(enter_currency_war, 'GuideOpen', _FakeGuideStepOp)
    monkeypatch.setattr(enter_currency_war, 'GuideChooseTab', _FakeGuideStepOp)
    return ctrl


def test_enter_recovers_when_transport_already_done(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """传送已落地场景:「前往参与」按钮不在 → 不判死,分流到 wait_lobby 按F进大厅。"""
    phases = [
        {  # 大世界普通:打开指南/选TAB(替身成功)两轮后推进
            'frame': ('大世界', '普通'),
            'exit': ('on_polls', 2),
        },
        {  # 朝露公馆入口(已传送):无「前往参与」→ 修复点:交 wait_lobby → F 分支按 F
            'frame': ('大世界', '朝露公馆入口'),
            'exit': ('on_polls', 4),
        },
        {  # 大厅:terminal(wait_lobby 命中「标识-创业指南」→ op 成功)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    for screen_name, state in (p['frame'] for p in phases):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')

    fixture_controller.set_phases(phases)
    op = _WatchedEnterCurrencyWar(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, (
        f'传送已落地场景应恢复到达大厅而非判死「找不到 前往参与」:'
        f'status={result.status};phase_idx={fixture_controller.phase_idx}'
    )
    assert fixture_controller.phase_idx == len(phases) - 1, (
        f'剧本应推进到末 phase(大厅):phase_idx={fixture_controller.phase_idx}'
    )
