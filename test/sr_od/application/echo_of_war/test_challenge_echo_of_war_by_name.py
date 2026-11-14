"""ChallengeEchoOfWarByName 周本按名挑战包装测试。

锁设计约定(docs/develop/sr_od/application/echo_of_war/changes/weekly-challenge-core/
details/trace-integration.md「周本按名挑战包装」节):

- mission 解析:ID 精确匹配优先,中文名互相包含;多命中 ValueError 带候选列表,
  零命中 ValueError 带可选值清单。
- 配队不从参数传:固定查周本计划该关卡项;'none' 翻译为 None 再传核心;
  team_num=0 = 沿用当前编队(合法值)。
- 核心 status 全名单显式分支:六类成功收口(本周次数耗尽清 left_times 记账),
  其余一切(含未列明)fail 原样透传。
- 全链委托:回大世界→传送→核心→收尾;成功终态恒「已返回大世界」;核心 fail
  原样透传且不收尾导航。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.echo_of_war import challenge_echo_of_war_by_name as by_name_mod
from sr_od.application.echo_of_war.challenge_echo_of_war_by_name import (
    ChallengeEchoOfWarByName,
)
from sr_od.application.echo_of_war.challenge_echo_of_war_core import (
    STATUS_BATTLE_DEADLOCK,
    STATUS_GIVE_UP_ON_LOSING_STREAK,
    STATUS_NOT_IN_CHALLENGE_SCREEN,
    STATUS_PLAN_FINISHED,
    STATUS_POWER_INSUFFICIENT,
    STATUS_TIMEOUT_VICTORY_EXITED,
    STATUS_TIMES_EXHAUSTED,
    STATUS_WITH_DEAD_RECOVERED,
)
from sr_od.application.trailblaze_power.trailblaze_power_config import (
    TrailblazePowerPlanItem,
)
from sr_od.interastral_peace_guide.guide_def import (
    GuideCategory,
    GuideMission,
    GuideTab,
)


def _fake_war_list() -> list[GuideMission]:
    """两本可控周本关卡(解析测试不依赖资产数据的实际关卡集)。"""
    cate = GuideCategory(GuideTab('生存索引'), '历战余响')
    return [
        GuideMission(cate, '坏灭的喜剧', 30),
        GuideMission(cate, '尘梦的赞歌', 30),
    ]


def _patch_war_list(monkeypatch: pytest.MonkeyPatch) -> list[GuideMission]:
    war_list = _fake_war_list()
    monkeypatch.setattr(by_name_mod, 'get_war_mission_list',
                        lambda guide_data: war_list)
    return war_list


def _patch_plan_list(test_context: SrTestContext,
                     monkeypatch: pytest.MonkeyPatch,
                     mission: GuideMission,
                     team_num: int = 0,
                     support: str = 'none') -> None:
    monkeypatch.setattr(
        test_context.echo_of_war_config, 'plan_list',
        [TrailblazePowerPlanItem(mission_id=mission.unique_id, team_num=team_num,
                                 support=support, plan_times=1)],
    )


class TestMissionResolve:
    """mission 解析四态。"""

    def test_resolve_by_display_name(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[0])
        op = ChallengeEchoOfWarByName(test_context, '坏灭的喜剧')
        assert op.mission_obj is war_list[0]

    def test_resolve_by_unique_id_exact(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[1])
        op = ChallengeEchoOfWarByName(test_context, war_list[1].unique_id)
        assert op.mission_obj is war_list[1]

    def test_resolve_multi_hit_raises_with_candidates(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_war_list(monkeypatch)
        with pytest.raises(ValueError) as exc_info:
            ChallengeEchoOfWarByName(test_context, '的')
        message = str(exc_info.value)
        assert '坏灭的喜剧' in message and '尘梦的赞歌' in message, (
            f'多命中应带候选列表:{message}'
        )

    def test_resolve_zero_hit_raises_with_options(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        war_list = _patch_war_list(monkeypatch)
        with pytest.raises(ValueError) as exc_info:
            ChallengeEchoOfWarByName(test_context, '不存在的周本')
        message = str(exc_info.value)
        for war in war_list:
            assert war.display_name in message, f'零命中应带可选值清单:{message}'

    def test_invalid_params_raise(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_war_list(monkeypatch)
        with pytest.raises(ValueError):
            ChallengeEchoOfWarByName(test_context, '  ')
        war_list = _fake_war_list()
        _patch_plan_list(test_context, monkeypatch, war_list[0])
        with pytest.raises(ValueError):
            ChallengeEchoOfWarByName(test_context, '坏灭的喜剧', plan_times=0)


class TestPlanTeamResolve:
    """配队固定查周本计划(单一源,无 override 参数)。"""

    def test_team_and_support_from_plan(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[0],
                         team_num=3, support='1001')
        op = ChallengeEchoOfWarByName(test_context, '坏灭的喜剧')
        assert op.team_num == 3
        assert op.support == '1001'

    def test_support_none_translated_to_none(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """'none' 在包装层翻译为 None(核心只认 None 的兜底归一另测)。"""
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[0],
                         team_num=0, support='none')
        op = ChallengeEchoOfWarByName(test_context, '坏灭的喜剧')
        assert op.team_num == 0
        assert op.support is None


class TestCoreStatusBranches:
    """核心 status 全名单显式分支(桩核心直呼挑战循环节点)。"""

    def _make_op_with_stub_core(self, test_context: SrTestContext,
                                monkeypatch: pytest.MonkeyPatch,
                                success: bool, status: str
                                ) -> tuple[ChallengeEchoOfWarByName, dict]:
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[0],
                         team_num=2, support='1001')
        monkeypatch.setattr(test_context, 'echo_of_war_run_record',
                            SimpleNamespace(left_times=3))

        captured: dict = {}

        class _StubCore:
            def __init__(self, ctx, team_num, plan_times, support=None):
                captured['team_num'] = team_num
                captured['plan_times'] = plan_times
                captured['support'] = support
                self.battle_success_times = 1

            def execute(self):
                return SimpleNamespace(success=success, status=status)

        monkeypatch.setattr(by_name_mod, 'ChallengeEchoOfWarCore', _StubCore)
        op = ChallengeEchoOfWarByName(test_context, '坏灭的喜剧', plan_times=2)
        return op, captured

    def test_success_statuses_pass_through(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        success_statuses = [
            STATUS_PLAN_FINISHED,
            STATUS_TIMEOUT_VICTORY_EXITED,
            STATUS_GIVE_UP_ON_LOSING_STREAK,
            STATUS_TIMES_EXHAUSTED,
            STATUS_POWER_INSUFFICIENT,
            STATUS_WITH_DEAD_RECOVERED,
        ]
        for status in success_statuses:
            op, _ = self._make_op_with_stub_core(test_context, monkeypatch,
                                                 success=True, status=status)
            result = op.run_core()
            assert result.is_success, f'{status} 应成功收口,实际 {result.status}'
            assert result.status == status

    def test_times_exhausted_clears_left_times(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """次数耗尽分支清 left_times(带使命语义层的记账动作)。"""
        op, _ = self._make_op_with_stub_core(
            test_context, monkeypatch,
            success=True, status=STATUS_TIMES_EXHAUSTED)
        result = op.run_core()
        assert result.is_success
        assert test_context.echo_of_war_run_record.left_times == 0, (
            '次数耗尽必须清剩余次数'
        )

    def test_fail_and_unknown_statuses_pass_through(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """已知 fail 与未列明 status 一律 fail 原样透传。"""
        for status in (STATUS_NOT_IN_CHALLENGE_SCREEN,
                       STATUS_BATTLE_DEADLOCK,
                       '未列明的任意状态'):
            op, _ = self._make_op_with_stub_core(test_context, monkeypatch,
                                                 success=False, status=status)
            result = op.run_core()
            assert not result.is_success, f'{status} 应 fail 透传'
            assert result.status == status, f'{status} 应原样透传'

    def test_core_receives_plan_team(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        op, captured = self._make_op_with_stub_core(
            test_context, monkeypatch,
            success=True, status=STATUS_PLAN_FINISHED)
        op.run_core()
        assert captured == {'team_num': 2, 'plan_times': 2, 'support': '1001'}


class TestFullChain:
    """全链委托(桩子 op,锁节点图接线):成功终态恒「已返回大世界」,fail 不收尾。"""

    def _install_stub_ops(self, monkeypatch: pytest.MonkeyPatch,
                          core_success: bool, core_status: str) -> dict:
        calls: dict = {'back': 0, 'transport': 0, 'core': 0}

        class _StubSubOp:
            def __init__(self, ctx):
                pass

            def execute(self):
                return SimpleNamespace(success=True, status='成功', data=None)

        class _StubBack(_StubSubOp):
            def __init__(self, ctx):
                super().__init__(ctx)
                calls['back'] += 1

        class _StubTransport(_StubSubOp):
            def __init__(self, ctx, mission):
                super().__init__(ctx)
                calls['transport'] += 1

        class _StubCore(_StubSubOp):
            def __init__(self, ctx, team_num, plan_times, support=None):
                super().__init__(ctx)
                calls['core'] += 1
                self.battle_success_times = 1

            def execute(self):
                return SimpleNamespace(success=core_success, status=core_status,
                                       data=None)

        monkeypatch.setattr(by_name_mod, 'BackToNormalWorldPlus', _StubBack)
        monkeypatch.setattr(by_name_mod, 'GuideTransport', _StubTransport)
        monkeypatch.setattr(by_name_mod, 'ChallengeEchoOfWarCore', _StubCore)
        return calls

    def _run(self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
             core_success: bool, core_status: str):
        war_list = _patch_war_list(monkeypatch)
        _patch_plan_list(test_context, monkeypatch, war_list[0])
        calls = self._install_stub_ops(monkeypatch, core_success, core_status)
        op = ChallengeEchoOfWarByName(test_context, '坏灭的喜剧')

        # 注入 FixtureController:绕过框架前置「检测游戏窗口」对真窗口的触达
        # (子 op 全部已桩,帧不参与断言,任意已归档帧占位)
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases([{'frame': ('大世界', '普通')}])
        if not test_context.has_screen('大世界', '普通'):
            pytest.skip('存档截图缺失:screens/大世界/普通.webp')

        enter_running_state(test_context)
        try:
            with fast_sleep(op):
                result = op.execute()
        finally:
            reset_running_state(test_context, op)
        return result, calls

    def test_success_chain_ends_at_world(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        result, calls = self._run(test_context, monkeypatch,
                                  True, STATUS_PLAN_FINISHED)
        assert result.success
        assert result.status == ChallengeEchoOfWarByName.STATUS_BACK_TO_WORLD, (
            f'成功终态应恒为已返回大世界,实际 {result.status}'
        )
        assert calls == {'back': 2, 'transport': 1, 'core': 1}, (
            f'全链应 回大世界×2(起+收)+传送×1+核心×1,实际 {calls}'
        )

    def test_core_fail_passes_through_without_cleanup(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        result, calls = self._run(
            test_context, monkeypatch,
            False, STATUS_NOT_IN_CHALLENGE_SCREEN)
        assert not result.success
        assert result.status == STATUS_NOT_IN_CHALLENGE_SCREEN, (
            f'fail 应原样透传,实际 {result.status}'
        )
        assert calls['back'] == 1, f'fail 不收尾导航(仅起点回大世界),实际 {calls}'
        assert calls['core'] == 1
