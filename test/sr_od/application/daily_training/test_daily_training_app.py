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
- ``claim_reward`` 节点的语义锁(未完成=良性跳过)用全 mock 节点级测试,不依赖存档截图
  (W294:礼盒模板对灰态礼盒也命中,当天实训未做时不可把「还未完成」当硬失败)。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext

from one_dragon.base.matcher.match_result import MatchResult
from sr_od.application.daily_training import (
    daily_training_app as daily_training_app_module,
)
from sr_od.application.daily_training.daily_training_app import DailyTrainingApp
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


class TestClaimRewardSemantics:
    """claim_reward 节点语义锁(W294):「还未完成」= 良性业务态,跳过收批不失败。

    背景:礼盒模板(带红叹号)对未达标的灰态礼盒也会命中(2026-08-27 两次实机实证),
    当天实训没做时点击礼盒无效果,旧逻辑把「复核未完成」当 round_fail 沿失败链把
    一条龙整组标失败。现有模板无法区分「未达标不可领」与「可领但点击无效」,选择
    跳过语义(实训次日刷新可自愈)。全 mock,不依赖存档截图。
    """

    def _make_app(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        completed_returns: list[bool],
    ) -> DailyTrainingApp:
        """构造全 mock 的 app:页面判定恒 True,completed 按队列依次返回,点击/sleep no-op。"""
        app = DailyTrainingApp(test_context)
        completed_queue = list(completed_returns)

        monkeypatch.setattr(app, 'last_screenshot', None, raising=False)
        monkeypatch.setattr(app, 'screenshot', lambda: None, raising=False)
        monkeypatch.setattr(
            daily_training_app_module.common_screen_state, 'in_secondary_ui',
            lambda ctx, screen, name: True,
        )
        monkeypatch.setattr(
            daily_training_app_module.phone_menu_utils, 'get_training_reward_claim_btn_pos',
            lambda ctx, screen: SimpleNamespace(center=SimpleNamespace(x=1045, y=320)),
        )

        def _fake_completed(ctx: object, screen: object) -> bool:
            return completed_queue.pop(0) if completed_queue else True

        monkeypatch.setattr(
            daily_training_app_module.phone_menu_utils, 'is_training_reward_completed',
            _fake_completed,
        )
        monkeypatch.setattr(test_context.controller, 'click', lambda pos: None)
        monkeypatch.setattr(daily_training_app_module.time, 'sleep', lambda s: None)
        return app

    def test_already_completed_success(self, test_context: SrTestContext,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """实训奖励已领完(completed=True)→ 成功收批(既有语义不回退)。"""
        app = self._make_app(test_context, monkeypatch, completed_returns=[True])
        result = app.claim_reward()
        assert result.is_success, '已领完应成功收批'
        assert '已领取' in result.status, f'状态应含「已领取」,实际 {result.status}'

    def test_incomplete_is_benign_skip(self, test_context: SrTestContext,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        """点击礼盒后复核仍未完成(当天实训未做)→ 良性跳过成功收批,不失败(W294)。"""
        app = self._make_app(test_context, monkeypatch, completed_returns=[False, False])
        result = app.claim_reward()
        assert result.is_success, (
            f'还未完成是良性业务态应成功收批,实际 status={result.status}'
        )
        assert '还未完成' in result.status, f'状态应保留「还未完成」字样,实际 {result.status}'

    def test_not_completed_after_claim_marks_no_fail_flag(
            self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """跳过路径不得再留失败标记(旧逻辑的 self.failed 已删除,防回归)。"""
        app = self._make_app(test_context, monkeypatch, completed_returns=[False, False])
        result = app.claim_reward()
        assert not hasattr(app, 'failed') or not app.failed, (
            '良性跳过不应留下失败标记(旧失败链语义已删)'
        )
        assert result.is_success
