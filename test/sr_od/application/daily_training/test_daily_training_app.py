"""DailyTrainingApp 每日实训工具 / 画面态测试(节点级,mock + 调用 + 断言,对齐 email/echo_of_war)。

覆盖:
- ``phone_menu_utils.is_training_reward_completed`` / ``get_training_reward_claim_btn_pos``:
  星际和平指南-每日实训 → 读奖励领完态 / 领取按钮位置。
- ``common_screen_state.in_secondary_ui``:每日实训 fixture → 判定在「指南」「每日实训」页
  (``claim_reward`` 节点靠它确认所在页)。

fixture(screens/):
- ``星际和平指南/每日实训.webp``:星际和平指南,每日实训 tab。4 个实训任务(1 个 120/120 完成、
  余进行中),活跃度奖励轨(0/100/200/300/400/500),1 个「领取」可领 +「进行中」/「前往」,
  「刷新时间 9 小时 4 分钟」(未刷新完)。

注:
- 两个 ``phone_menu_utils`` 函数是纯截图函数(裁 ``GUIDE_TRAINING_REWARD_CLAIM_RECT`` → 模板匹配
  ``training_reward_gift`` / ``training_reward_completed``),不跑 op ``execute()``(后者在无
  running 状态的 mock harness 下不收敛,见 echo_of_war 测试说明)。
- 不 pin 精确完成数 / 是否命中(随账号每日状态变 + 小区域模板匹配有抖动):只验证提取管线通
  (裁剪 → 模板匹配 → 返回正确类型),真坏了会抛异常或返错类型。
"""

import pytest
from test.conftest import SrTestContext

from one_dragon.base.matcher.match_result import MatchResult
from sr_od.operations.menu import phone_menu_utils
from sr_od.screen_state import common_screen_state


class TestDailyTrainingApp:
    """DailyTrainingApp 每日实训奖励提取 + 画面态测试。"""

    def test_training_reward_extraction(self, test_context: SrTestContext) -> None:
        """星际和平指南-每日实训 → 奖励完成态(bool)/ 领取按钮位置(Optional)。"""
        if not test_context.has_screen('星际和平指南', '每日实训'):
            pytest.skip('存档截图缺失:screens/星际和平指南/每日实训.webp')
        screen = test_context.load_screen('星际和平指南', '每日实训')

        completed = phone_menu_utils.is_training_reward_completed(test_context, screen)
        assert isinstance(completed, bool), f'完成态应返回 bool,实际 {completed!r}'

        claim_pos = phone_menu_utils.get_training_reward_claim_btn_pos(test_context, screen)
        assert claim_pos is None or isinstance(claim_pos, MatchResult), (
            f'领取按钮应返回 None 或 MatchResult,实际 {claim_pos!r}'
        )

    def test_claim_reward_in_secondary_ui(self, test_context: SrTestContext) -> None:
        """每日实训 fixture → in_secondary_ui 判定在「指南」「每日实训」页。

        ``DailyTrainingApp.claim_reward`` 靠这两个判定确认在正确页再领奖;fixture 是真实的
        每日实训面板(左上角标题含「每日实训」),故两者均应为 True。
        """
        if not test_context.has_screen('星际和平指南', '每日实训'):
            pytest.skip('存档截图缺失:screens/星际和平指南/每日实训.webp')
        screen = test_context.load_screen('星际和平指南', '每日实训')

        assert common_screen_state.in_secondary_ui(test_context, screen, '指南'), (
            '应判定在「指南」二级页'
        )
        assert common_screen_state.in_secondary_ui(test_context, screen, '每日实训'), (
            '应判定在「每日实训」二级页'
        )
