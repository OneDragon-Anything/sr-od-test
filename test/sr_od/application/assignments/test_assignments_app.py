"""AssignmentsApp 委托节点测试(节点级,mock + 调节点 + 断言,对齐 email_app)。

覆盖:
- 委托派遣中(委托派遣中):``_check_status`` → ``STATUS_ASSIGNING``(派遣中,无奖励可领,
  返回后 ``back_at_last`` 回大世界,不领取)。

fixture(screens/):
- ``委托/委托派遣中.webp``:委托画面,4 槽派遣中(委托派遣中 area + 4/4)。

注:
- AssignmentsApp 用 phone_menu 的委托 area(``委托-领取奖励`` / ``委托-委托派遣中`` /
  ``委托-点击空白处关闭``)+ phone_menu template(ASSIGNMENTS 主网格项,``alert=False``),
  无独立 assignments screen_info(委托画面被识别为「菜单」模糊或未定义 screen,is_precise=false)。
- 「委托可领(STATUS_HAS_REWARD)+ ``_claim``」分支 fixture 待条件(委托有可领奖励时采)。
- 验证(2026-07-29):实跑 ``AssignmentsApp`` success —— 委托 area 有效,**版本未大改影响**,
  无需修复。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.assignments.assignments_app import AssignmentsApp


class TestAssignmentsApp:
    """AssignmentsApp 委托节点测试。"""

    def _make_op(self, test_context: SrTestContext, screen: str, state: str) -> AssignmentsApp:
        """mock 某画面子态并取帧,返回已就绪的 AssignmentsApp。"""
        test_context.mock_screen(screen, state)
        op = AssignmentsApp(test_context)
        op.screenshot()
        return op

    def test_check_status_assigning(self, test_context: SrTestContext) -> None:
        """委托派遣中 → _check_status → STATUS_ASSIGNING(无奖励,返回)。"""
        if not test_context.has_screen('委托', '委托派遣中'):
            pytest.skip('存档截图缺失:screens/委托/委托派遣中.webp')
        op = self._make_op(test_context, '委托', '委托派遣中')
        result = op._check_status()
        assert result.status == AssignmentsApp.STATUS_ASSIGNING, (
            f'派遣中应为 ASSIGNING,实际 status={result.status}'
        )
