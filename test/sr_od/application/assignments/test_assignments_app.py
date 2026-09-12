"""AssignmentsApp 委托节点测试(节点级,mock + 调节点 + 断言,对齐 email_app)。

覆盖:
- 委托派遣中(``委托派遣中``):``_check_status`` → ``STATUS_ASSIGNING``(派遣中,无奖励可领,
  返回后 ``back_at_last`` 回大世界,不领取)。
- 委托可领(``委托可领``):``_check_status`` → ``STATUS_HAS_REWARD`` + ``_claim_reward``(点
  ``委托-领取奖励``)。**fixture 已采**(2026-07-29;一条龙会自动领掉,采前曾关 assignments enabled,已回滚)。
- 领取后弹窗(``委托领取弹窗``):``_click_empty``(点 ``委托-点击空白处关闭`` 关掉领奖弹窗)。**fixture 已采**(2026-07-30)。

fixture(screens/):
- ``委托/委托派遣中.webp``:委托画面,4 槽派遣中(委托-委托派遣中 area)。✅ 已有。
- ``委托/委托可领.webp``:委托画面,有可领奖励(``委托-领取奖励`` area 命中)。✅ 已有(2026-07-29)。
- ``委托/委托领取弹窗.webp``:领奖后的「获得物品 / 点击空白处关闭」弹窗(``委托-点击空白处关闭`` area)。✅ 已有(2026-07-30)。

注:
- AssignmentsApp 用 phone_menu 的委托 area(``委托-领取奖励`` / ``委托-委托派遣中`` /
  ``委托-点击空白处关闭``)+ phone_menu template(ASSIGNMENTS 主网格项,``alert=False``),
  无独立 assignments screen_info(委托画面被识别为「菜单」模糊或未定义 screen,is_precise=false)。
- ``_claim_reward`` / ``_click_empty`` 用 ``round_by_find_and_click_area``(单轮 find+click,不循环,
  可在 mock harness 测);``_check_status`` 用 ``round_by_find_area``。
- fixture 齐备(委托派遣中 / 委托可领 / 委托领取弹窗),4 用例均运行无 skip。
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

    def test_check_status_has_reward(self, test_context: SrTestContext) -> None:
        """委托可领 → _check_status → STATUS_HAS_REWARD(``委托-领取奖励`` area 命中)。"""
        if not test_context.has_screen('委托', '委托可领'):
            pytest.skip('存档截图缺失:screens/委托/委托可领.webp(委托有可领奖励时采)')
        op = self._make_op(test_context, '委托', '委托可领')
        result = op._check_status()
        assert result.status == AssignmentsApp.STATUS_HAS_REWARD, (
            f'有奖励应为 HAS_REWARD,实际 status={result.status}'
        )

    def test_claim_reward(self, test_context: SrTestContext) -> None:
        """委托可领 → _claim_reward 点 ``委托-领取奖励``(round_by_find_and_click_area 命中)。"""
        if not test_context.has_screen('委托', '委托可领'):
            pytest.skip('存档截图缺失:screens/委托/委托可领.webp')
        op = self._make_op(test_context, '委托', '委托可领')
        result = op._claim_reward()
        assert result.is_success, (
            f'应命中并点击 委托-领取奖励,实际 status={result.status}'
        )

    def test_click_empty(self, test_context: SrTestContext) -> None:
        """领取后弹窗 → _click_empty 点 ``委托-点击空白处关闭``。"""
        if not test_context.has_screen('委托', '委托领取弹窗'):
            pytest.skip('存档截图缺失:screens/委托/委托领取弹窗.webp(领奖后弹窗)')
        op = self._make_op(test_context, '委托', '委托领取弹窗')
        result = op._click_empty()
        assert result.is_success, (
            f'应命中并点击 委托-点击空白处关闭,实际 status={result.status}'
        )
