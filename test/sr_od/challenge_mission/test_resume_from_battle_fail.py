"""ResumeFromBattleFail 共享失败继续件测试。

锁设计约定(docs/develop/sr_od/application/echo_of_war/changes/weekly-challenge-core/
details/fail-form-adaptation.md「方案:共享失败继续件」节):

1. 节点声明:node_max_retry_times=5、timeout_seconds=180(点空白与旧结算锚均失效
   时的最终出口)。
2. 行为(设计「入口两态分流 + 连等封顶」):
   - 每轮先查挑战态锚(挑战副本·挑战按钮),回归即 round_success('已回挑战画面');
   - 新形态(「大世界-战斗失败」·标题-战斗失败在场)点 点击区-空白继续;
   - 旧结算形态(「战斗画面」·退出关卡按钮在场)点 退出关卡按钮;
   - 同一形态连等 5 轮未回归 → 转试另一态,转态前先验其锚在场,不在场直接
     round_fail('失败画面未能离开')(防按「未找到按钮」路径耗尽预算、status 落
     框架默认文案);旧形态再连等 5 轮仍未回归 → 同文案失败。
3. 全流程(fixture 驱动,真实识别链):周本失败画面(版本更新新形态)点空白 →
   挑战画面回归,落 STATUS_RESUMED。
"""

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.challenge_mission.resume_from_battle_fail import (
    RESUME_TIMEOUT_SECONDS,
    SAME_FORM_MAX_ROUNDS,
    ResumeFromBattleFail,
)


class _WatchedResume(WatchdogOperationMixin, ResumeFromBattleFail):
    """带看门狗的失败继续件(流程测试防无限轮)。"""


class TestResumeFromBattleFail:
    """共享失败继续件的声明与行为分支。"""

    def _make_op(self, test_context: SrTestContext) -> ResumeFromBattleFail:
        return ResumeFromBattleFail(test_context)

    def test_node_declarations(self, test_context: SrTestContext) -> None:
        """连等封顶/预算/兜底超时的声明值锁定(设计口径)。"""
        assert SAME_FORM_MAX_ROUNDS == 5
        assert RESUME_TIMEOUT_SECONDS == 3 * 60
        op = self._make_op(test_context)
        op._init_network()
        node = op._node_map['失败画面继续']
        assert node.node_max_retry_times == 5
        assert node.timeout_seconds == RESUME_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # 行为分支直呼(桩识别,锁节点逻辑;识别链真伪归流程测试)
    # ------------------------------------------------------------------

    def _stub_recognition(self, op: ResumeFromBattleFail,
                          behavior: dict[str, object],
                          clicks: list[tuple[str, str]]) -> None:
        """按命中表桩掉识别与点击。

        behavior: '画面|区域' → bool 或 (call_idx -> bool) 函数;call_idx 是该
        area 被查询的第几次(节点每轮对每个 area 恰查一次,故即轮序号,从 1 起)。
        未配置的 area 恒不命中。点击记录 (画面, 区域) 后恒返回成功。
        """
        counts: dict[str, int] = {}

        def _fake_find(screen, screen_name, area_name, **kw):
            key = f'{screen_name}|{area_name}'
            counts[key] = counts.get(key, 0) + 1
            rule = behavior.get(key, False)
            hit = rule(counts[key]) if callable(rule) else bool(rule)
            return op.round_success() if hit else op.round_fail(area_name)

        def _fake_click(screen, screen_name, area_name, **kw):
            clicks.append((screen_name, area_name))
            return op.round_success(area_name)

        op.round_by_find_area = _fake_find  # type: ignore[method-assign]
        op.round_by_find_and_click_area = _fake_click  # type: ignore[method-assign]
        op.screenshot = lambda *a, **kw: None  # type: ignore[method-assign]

    def test_new_form_click_blank_then_anchor_returns(
            self, test_context: SrTestContext) -> None:
        """新形态:点空白后挑战锚回归 → 成功。"""
        op = self._make_op(test_context)
        clicks: list[tuple[str, str]] = []
        self._stub_recognition(op, {
            '挑战副本|挑战按钮': lambda n: n >= 2,
            '大世界-战斗失败|标题-战斗失败': lambda n: n == 1,
        }, clicks)

        with fast_sleep():
            first = op.resume()
            assert first.result.name == 'WAIT', f'首轮应点空白等待,实际 {first.result}'
            assert clicks == [('大世界-战斗失败', '点击区-空白继续')]
            second = op.resume()
        assert second.is_success
        assert second.status == ResumeFromBattleFail.STATUS_RESUMED

    def test_new_form_stuck_switches_to_old_form(
            self, test_context: SrTestContext) -> None:
        """新形态连等封顶后转试旧形态:旧锚在场 → 点退出关卡。"""
        op = self._make_op(test_context)
        clicks: list[tuple[str, str]] = []
        self._stub_recognition(op, {
            # 新形态锚前 5 轮在场,之后画面异动不回归
            '大世界-战斗失败|标题-战斗失败': lambda n: n <= SAME_FORM_MAX_ROUNDS,
            # 旧结算锚从第 2 轮起一直在场(转态前验锚可通过)
            '战斗画面|退出关卡按钮': lambda n: n >= 2,
        }, clicks)

        with fast_sleep():
            for _ in range(SAME_FORM_MAX_ROUNDS):
                assert op.resume().result.name == 'WAIT'
            switched = op.resume()

        assert switched.result.name == 'WAIT', f'转态轮应点退出关卡等待,实际 {switched.result}'
        assert clicks[-1] == ('战斗画面', '退出关卡按钮')

    def test_both_forms_exhausted_fails_with_explicit_status(
            self, test_context: SrTestContext) -> None:
        """两态各连等封顶仍未回归 → 显式失败文案(非框架默认)。"""
        op = self._make_op(test_context)
        clicks: list[tuple[str, str]] = []
        self._stub_recognition(op, {}, clicks)  # 全部不命中,含转态前验锚

        with fast_sleep():
            for _ in range(SAME_FORM_MAX_ROUNDS):
                assert op.resume().result.name == 'WAIT'
            switched = op.resume()
            # 转态前验锚不在场 → 直接失败(不走旧形态连等)
            assert not switched.is_success
            assert switched.status == ResumeFromBattleFail.STATUS_NOT_LEFT
        assert clicks == [], f'两态皆不中不应有点击:{clicks}'

    def test_old_form_click_exit_then_anchor_returns(
            self, test_context: SrTestContext) -> None:
        """入口即旧结算形态:点退出关卡后挑战锚回归 → 成功(点空白分支未走)。"""
        op = self._make_op(test_context)
        clicks: list[tuple[str, str]] = []
        self._stub_recognition(op, {
            '挑战副本|挑战按钮': lambda n: n >= 2,
            '战斗画面|退出关卡按钮': True,
        }, clicks)

        with fast_sleep():
            first = op.resume()
            assert first.result.name == 'WAIT'
            assert clicks == [('战斗画面', '退出关卡按钮')]
            second = op.resume()

        assert second.is_success
        assert second.status == ResumeFromBattleFail.STATUS_RESUMED


class TestResumeFromBattleFailFlow:
    """全流程 fixture 驱动(真实识别链):周本失败画面点空白回挑战画面。"""

    def test_new_form_failure_screen_returns_to_challenge(
            self,
            test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        if not test_context.has_screen('大世界-战斗失败', '战斗失败-历战余响'):
            pytest.skip('存档截图缺失:screens/大世界-战斗失败/战斗失败-历战余响.webp')
        if not test_context.has_screen('挑战副本-历战余响', '挑战面板'):
            pytest.skip('存档截图缺失:screens/挑战副本-历战余响/挑战面板.webp')

        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases([
            {
                'frame': ('大世界-战斗失败', '战斗失败-历战余响'),
                'exit': ('on_click_in', '大世界-战斗失败', '点击区-空白继续'),
            },
            {
                'frame': ('挑战副本-历战余响', '挑战面板'),
                # terminal
            },
        ])

        op = _WatchedResume(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep(op):
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'失败继续件未成功:status={result.status};'
            f'phase_idx={ctrl.phase_idx};clicks={ctrl.recorded_clicks}'
        )
        assert result.status == ResumeFromBattleFail.STATUS_RESUMED
        assert ctrl.click_hit_area('大世界-战斗失败', '点击区-空白继续'), (
            f'未记录到点空白继续 click:{ctrl.recorded_clicks}'
        )
        assert ctrl.phase_idx == 1, f'剧本未推进到挑战画面:phase_idx={ctrl.phase_idx}'
