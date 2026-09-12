"""EmailApp 邮件领取节点测试(节点级,mock 一帧 + 调节点 + 断言,对齐 ZZZ email_app)。

覆盖:
- 有邮件红点的菜单(菜单-邮件红点):``_click_email`` 识别 EMAILS + 红点 →
  ``STATUS_WITH_ALERT``(有邮件可领,点击进邮件列表)。
- 无邮件红点的菜单(菜单-无邮件红点):``_click_email`` 识别 EMAILS 但无红点 →
  ``STATUS_NO_ALERT``(无邮件,不点击)。
- 邮件列表(有可领/无可领):``_claim`` 识别 ``邮件-全部领取`` area(两种列表态都识别)。

fixture(screens/):
- ``菜单/菜单-邮件红点.webp``:手机菜单,右侧邮件图标有红点(有未领邮件)。
- ``菜单/菜单-无邮件红点.webp``:手机菜单,邮件图标无红点。
- ``邮件/邮件列表-有可领.webp``:邮件列表,有可领附件(全部领取亮)。
- ``邮件/邮件列表.webp``:邮件列表无可领(全部领取灰,仍识别)。

注:
- EmailApp 用 phone_menu 的 ``邮件-全部领取`` area + phone_menu template(EMAILS),
  不依赖 ``get_match_screen_name`` 精准(邮件列表画面被识别为「菜单」模糊,is_precise=false)。
- 节点方法直接调(参照 ZZZ ``test_email_app``):mock 一帧 → ``op.screenshot()`` 取帧到
  ``last_screenshot`` → 调节点 → 断言 ``OperationRoundResult``。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.email.email_app import EmailApp


class TestEmailApp:
    """EmailApp 邮件领取节点测试。"""

    def _make_op(self, test_context: SrTestContext, screen: str, state: str) -> EmailApp:
        """mock 某画面子态并取帧,返回已就绪的 EmailApp。"""
        test_context.mock_screen(screen, state)
        op = EmailApp(test_context)
        op.screenshot()
        return op

    def test_click_email_with_alert(self, test_context: SrTestContext) -> None:
        """有邮件红点的菜单 → _click_email 识别 EMAILS + 红点 → STATUS_WITH_ALERT。"""
        if not test_context.has_screen('菜单', '菜单-邮件红点'):
            pytest.skip('存档截图缺失:screens/菜单/菜单-邮件红点.webp')
        op = self._make_op(test_context, '菜单', '菜单-邮件红点')
        result = op._click_email()
        assert result.is_success, '应识别到邮件图标(EMAILS template)'
        assert result.status == EmailApp.STATUS_WITH_ALERT, (
            f'有红点应为 WITH_ALERT,实际 status={result.status}'
        )

    def test_click_email_without_alert(self, test_context: SrTestContext) -> None:
        """无邮件红点的菜单 → _click_email 识别 EMAILS 但无红点 → STATUS_NO_ALERT(不点击)。"""
        if not test_context.has_screen('菜单', '菜单-无邮件红点'):
            pytest.skip('存档截图缺失:screens/菜单/菜单-无邮件红点.webp')
        op = self._make_op(test_context, '菜单', '菜单-无邮件红点')
        result = op._click_email()
        assert result.status == EmailApp.STATUS_NO_ALERT, (
            f'无红点应为 NO_ALERT,实际 status={result.status}'
        )

    def test_claim_with_rewards(self, test_context: SrTestContext) -> None:
        """有可领邮件列表 → _claim 识别并点击「邮件-全部领取」。"""
        if not test_context.has_screen('邮件', '邮件列表-有可领'):
            pytest.skip('存档截图缺失:screens/邮件/邮件列表-有可领.webp')
        op = self._make_op(test_context, '邮件', '邮件列表-有可领')
        result = op._claim()
        assert result.is_success, '应识别并点击「全部领取」'

    def test_claim_without_rewards(self, test_context: SrTestContext) -> None:
        """无可领邮件列表(全部领取灰)→ _claim 仍识别「邮件-全部领取」area。"""
        if not test_context.has_screen('邮件', '邮件列表'):
            pytest.skip('存档截图缺失:screens/邮件/邮件列表.webp')
        op = self._make_op(test_context, '邮件', '邮件列表')
        result = op._claim()
        assert result.is_success, '无可领(灰色)也应识别「全部领取」'
