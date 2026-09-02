"""SimUniExit「打开菜单⇄点击结算」无界循环加界测试。

背景(2026-09-02 一条龙清体力-饰品提取段实证):提取局打完后 SimUniExit 的
``click_exit`` 找不到「菜单-结束并结算」→ ``round_success(STATUS_BACK_MENU)``
→ 经 success 边回 ``open_menu``(Esc)→ 再找 → 循环。循环全走 success 边,
不消耗任何 retry 预算 → 无界空转 27 分钟。

修复:op 实例自带 ``_back_menu_cycles`` 连续计数(命中结算项或确认已在大世界
时归零),达 ``MAX_BACK_MENU_CYCLES`` 后 ``round_fail`` 结束,交上层
(BackToNormalWorldPlus.sim_uni_exit)的 round_retry 兜底。

测试构造:所有 find_and_click 按「剧本」决定命中与否(缺省恒未命中),
画面状态恒 NORMAL_IN_WORLD(让 check_screen 每次都判有进展,循环只在
open_menu⇄click_exit 之间)。断言:

- 用例①:恒不命中 → op 有界 FAIL(轮次 ≈ 1 + MAX×2,看门狗不触发);
- 用例②:循环中途命中一次结算项 → 计数归零,EXIT_CLICKED 链走通 op 成功,
  计数器归零(失败上界重新计满的语义由用例①的预算锁 + 本用例的归零锁合成)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

import sr_od.application.sim_universe.operations.sim_uni_exit as sue_module
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from sr_od.application.sim_universe import sim_uni_screen_state
from sr_od.application.sim_universe.operations.sim_uni_exit import SimUniExit
from sr_od.operations.sr_operation import SrOperation


class _WatchedSimUniExit(WatchdogOperationMixin, SimUniExit):
    """带看门狗的 SimUniExit(防测试自身死循环)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx) -> None:
        """跳过游戏窗口前置节点(MockController 无 game_win,与本测试无关)。"""
        SrOperation.__init__(
            self, ctx, op_name='模拟宇宙 结束并结算(测试)', need_check_game_win=False,
        )
        # 绕过 SimUniExit.__init__ 后手工补其业务字段(与生产构造语义一致)
        self.is_in_x = False
        self.temporarily_leave = False
        self._back_menu_cycles = 0


def _make_exit_op(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
    hit_script: dict[str, list[str]] | None = None,
) -> tuple[_WatchedSimUniExit, list[str]]:
    """构造 SimUniExit 假环境,返回 (op, esc 记录)。

    - 画面状态恒 NORMAL_IN_WORLD:check_screen 每次都判「已在大世界」,
      循环被压缩到 open_menu⇄click_exit 之间(事故现场正是这个子图);
    - ``round_by_find_and_click_area`` 按 ``hit_script`` 决定命中:键=area 名,
      值=按调用顺序弹出的剧本(值 'hit' 表示该次命中),缺省恒未命中——
      未命中返回 round_wait 只作「未命中」载体(点击成功与否由 is_success
      判断,wait 结果即非命中语义);
    - controller.esc 补桩并记录(MockController 无该属性)。
    """
    script: dict[str, list[str]] = hit_script or {}

    def _fake_find_and_click(
        self, screen, screen_name: str, area_name: str, *args, **kwargs,
    ) -> OperationRoundResult:
        plan = script.get(area_name, [])
        if plan:
            outcome = plan.pop(0)
            if outcome == 'hit':
                return self.round_success(status=area_name)
        return self.round_wait(status=f'未找到 {area_name}')

    monkeypatch.setattr(
        SimUniExit, 'round_by_find_and_click_area', _fake_find_and_click,
    )
    monkeypatch.setattr(
        sue_module.sim_uni_screen_state,
        'get_sim_uni_screen_state',
        lambda *args, **kwargs: sim_uni_screen_state.ScreenState.NORMAL_IN_WORLD.value,
    )

    op = _WatchedSimUniExit(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    escs: list[str] = []
    monkeypatch.setattr(
        op.ctx.controller, 'esc', lambda: escs.append('esc'), raising=False,
    )
    return op, escs


class TestSimUniExitBoundedLoop:

    def test_stuck_back_menu_fails_bounded(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """恒找不到结算入口:op 应有界 FAIL(修复前 success 边无界空转)。"""
        op, escs = _make_exit_op(test_context, monkeypatch)

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 修复后:连续 MAX_BACK_MENU_CYCLES 圈未命中 → click_exit round_fail。
        assert not result.success, (
            f'恒不命中场景不应 success:status={result.status}'
        )
        # 轮次有界:看门狗(60)未触发,总轮次 ≈ 1(画面识别) + MAX×2(每圈
        # 打开菜单 + 点击结算) = 11。
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert rounds <= 20, f'轮次超界({rounds}),疑似无界循环未修复'
        assert rounds >= 10, f'轮次异常偏少({rounds}),应计满 {SimUniExit.MAX_BACK_MENU_CYCLES} 圈才 FAIL'
        # 每圈都真的发过一次 Esc(open_menu 执行了 MAX 圈)。
        assert len(escs) == SimUniExit.MAX_BACK_MENU_CYCLES, (
            f'Esc 次数({len(escs)}) != 圈数上限({SimUniExit.MAX_BACK_MENU_CYCLES})'
        )
        # FAIL 时计数器停在上限(未在别处被误归零)。
        assert op._back_menu_cycles == SimUniExit.MAX_BACK_MENU_CYCLES, (
            f'FAIL 时计数器应为上限,实际 {op._back_menu_cycles}'
        )

    def test_exit_clicked_resets_counter(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """循环中途命中结算项:计数归零,EXIT_CLICKED 链走通 op 成功。"""
        hit_script = {
            # click_exit 每圈先试「菜单-结束并结算」:前两圈未命中,第三圈命中
            '菜单-结束并结算': ['miss', 'miss', 'hit'],
            # 命中后的确认弹窗与结算空白页都命中 → 走到图末端 op 成功结束
            '退出对话框-确认': ['hit'],
            '点击空白处继续': ['hit'],
        }
        op, escs = _make_exit_op(test_context, monkeypatch, hit_script)

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 命中结算项 → 确认 → 空白页 → 无后继节点,op 成功结束(修复前该
        # 命中同样成功,但本用例锁的是:成功路径上计数器已被归零)。
        assert result.success, f'命中场景应 success:status={result.status}'
        assert op._back_menu_cycles == 0, (
            f'命中结算项后计数器应归零,实际 {op._back_menu_cycles}'
        )
        # open_menu 在每次 click_exit 前各发一次 Esc:命中发生在第三次
        # click_exit,此前 open_menu 执行了 3 次(初始 + 两圈未命中回流)。
        assert len(escs) == 3, f'Esc 次数应为 3(第三次 click_exit 前命中),实际 {len(escs)}'
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        # 1(画面识别) + 2×2(两圈未命中循环) + 1(命中圈) + 2(确认+空白) = 8
        assert rounds <= 12, f'轮次异常({rounds}),命中后不应再进循环'
