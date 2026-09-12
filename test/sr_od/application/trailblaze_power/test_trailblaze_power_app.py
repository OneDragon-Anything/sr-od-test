"""TrailblazePowerApp 开拓力 check_task 纯配置测试(节点级,mock + 调节点 + 断言,对齐 echo_of_war)。

覆盖 ``check_task``(纯配置逻辑,不读截图):
- 有计划(``get_next_plan`` 非 None)→ ``STATUS_WITH_PLAN``。
- 无计划(``get_next_plan``=None)→ ``STATUS_NO_PLAN``。

注:
- ``check_task`` 是纯配置节点(``is_start_node``),不读截图 —— 用 ``monkeypatch`` 替换
  ``TrailblazePowerConfig.get_next_plan`` 控制分支,不写 config(类级,测试后自动还原)。
- ``check_task`` 首行 ``ctx.power_config.check_plan_run_times()`` 走**真实**代码路径(不再
  monkeypatch):该函数曾对空 plan_list 死循环,已在 ``TrailblazePowerConfig.check_plan_run_times``
  加空 list 守卫修复(见 ``.debug/temp/zzz/2026-07-29-check-plan-empty-infinite-loop.md``);本测试
  用 test 实例(99)跑,兼作该修复的回归守卫(谁回退修复就卡住暴露)。
- ``execute_plan``(挑战,含 SimUniApp / ChallengeOrnamentExtraction / UseTrailblazePower,消耗体力)
  需 running + 消耗,不 mock。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.trailblaze_power.trailblaze_power_app import TrailblazePowerApp
from sr_od.application.trailblaze_power.trailblaze_power_config import (
    TrailblazePowerConfig,
)


class TestTrailblazePowerApp:
    """TrailblazePowerApp 开拓力 check_task 测试。"""

    def _make_op(self, test_context: SrTestContext) -> TrailblazePowerApp:
        """返回已就绪的 TrailblazePowerApp(check_task 不读图,无需 mock_screen)。"""
        return TrailblazePowerApp(test_context)

    def test_check_task_with_plan(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """有计划(get_next_plan 非 None)→ STATUS_WITH_PLAN。"""
        monkeypatch.setattr(
            TrailblazePowerConfig, 'get_next_plan', lambda self, last_tried_plan=None: object()
        )
        op = self._make_op(test_context)
        result = op.check_task()
        assert result.status == TrailblazePowerApp.STATUS_WITH_PLAN, (
            f'有计划应为 WITH_PLAN,实际 status={result.status}'
        )

    def test_check_task_no_plan(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无计划(get_next_plan=None)→ STATUS_NO_PLAN。"""
        monkeypatch.setattr(
            TrailblazePowerConfig, 'get_next_plan', lambda self, last_tried_plan=None: None
        )
        op = self._make_op(test_context)
        result = op.check_task()
        assert result.status == TrailblazePowerApp.STATUS_NO_PLAN, (
            f'无计划应为 NO_PLAN,实际 status={result.status}'
        )
