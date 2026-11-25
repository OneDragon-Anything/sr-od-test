"""UseTrailblazePower 失败形态适配 mock 测试(升级 op 适配迭代块 A)。

锁设计约定(docs/develop/sr_od/application/cultivation/changes/
upgrade-ops-adaptation/details/fail-adaptation.md §1):
- 等待战斗结果的「战斗失败」status 改走「失败画面继续」节点:委托共享失败继续件
  ResumeFromBattleFail(自带新/旧两态分流)回挑战画面,按连败阈值 5 分流重发/关副本;
- 失败重发回「选择次数」节点——滑条按 plan_times-finish_times 重算,记账自洽;
- 失败场不计完成次数、不触发 on_battle_success 回调;
- 委托 fail 原样透传(现场交调用方,不收尾);
- 战斗结果处理只接胜利(达标退出/再来一次),连败判定移除;
- 超时收尾判负分支改委托共享件(超时语境不重试),判胜补记+退出不变。
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

from sr_od.application.trailblaze_power import use_trailblaze_power as use_tp_module
from sr_od.application.trailblaze_power.use_trailblaze_power import UseTrailblazePower
from sr_od.interastral_peace_guide.guide_def import (
    GuideCategory,
    GuideMission,
    GuideTab,
)


def _make_mission() -> GuideMission:
    """最小拟造花萼（赤）关卡对象(op 构造只用到分类/名字/体力)。"""
    cate = GuideCategory(GuideTab('生存索引'), '拟造花萼（赤）')
    return GuideMission(cate, '虚无之蕾', power=10)


def _make_op(test_context: SrTestContext, plan_times: int,
             on_battle_success=None) -> UseTrailblazePower:
    return UseTrailblazePower(test_context, _make_mission(),
                              team_num=1, plan_times=plan_times,
                              on_battle_success=on_battle_success)


def _stub_resume(monkeypatch: pytest.MonkeyPatch, success: bool,
                 status: str) -> None:
    """桩掉共享失败继续件(委托结果可控;嵌套流程由场景 1 的真件流测试覆盖)。"""

    class _StubResume:
        def __init__(self, ctx):
            pass

        def execute(self):
            return SimpleNamespace(success=success, status=status, data=None)

    monkeypatch.setattr(use_tp_module, 'ResumeFromBattleFail', _StubResume)


def _click_area_stub(screen_name: str, area_name: str):
    """桩子 op 类:execute 时点击指定 area 中心(驱动 fixture 帧推进)后返回成功。"""

    class _StubOp:
        def __init__(self, ctx, *args, **kwargs):
            self._ctx = ctx

        def execute(self):
            area = self._ctx.screen_loader.get_area(screen_name, area_name)
            self._ctx.controller.click(area.rect.center)
            return SimpleNamespace(success=True, status='成功', data=None)

    return _StubOp


def _noop_op_stub():
    """桩子 op 类:execute 直接返回成功,不点击。"""

    class _StubOp:
        def __init__(self, ctx, *args, **kwargs):
            pass

        def execute(self):
            return SimpleNamespace(success=True, status='成功', data=None)

    return _StubOp


class TestFailDelegateDirectCall:
    """失败画面继续节点直呼(桩共享件,锁三分支)。"""

    def test_fail_below_threshold_retries(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """连败未达阈值 → 委托成功 → 失败重发。"""
        _stub_resume(monkeypatch, success=True, status='已回挑战画面')
        op = _make_op(test_context, plan_times=1)
        op.battle_fail_times = 1

        with fast_sleep():
            result = op.after_battle_fail()

        assert result.is_success
        assert result.status == '失败重发'

    def test_fail_at_threshold_gives_up(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """连败达阈值 5 → 委托成功 → 连败关副本(止损出口)。"""
        _stub_resume(monkeypatch, success=True, status='已回挑战画面')
        op = _make_op(test_context, plan_times=5)
        op.battle_fail_times = 5

        with fast_sleep():
            result = op.after_battle_fail()

        assert result.is_success
        assert result.status == '连败关副本'

    def test_shared_op_fail_passes_through(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """共享件 fail → 原样透传(现场交调用方,不收尾)。"""
        _stub_resume(monkeypatch, success=False, status='失败画面未能离开')
        op = _make_op(test_context, plan_times=1)
        op.battle_fail_times = 1

        with fast_sleep():
            result = op.after_battle_fail()

        assert not result.is_success
        assert result.status == '失败画面未能离开'


class TestFailRetryFlow:
    """fixture 驱动全流程(真实识别链):一败重发至达标 / 连败止损。"""

    def _run_flow(self, test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  op: UseTrailblazePower,
                  phases: list[dict]):
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases(phases)
        # UseTrailblazePower 未挂 WatchdogOperationMixin——fixture 自带轮次上限兜底

        enter_running_state(test_context)
        try:
            with fast_sleep(op):
                result = op.execute()
        finally:
            reset_running_state(test_context, op)
        return ctrl, result

    def _require_screens(self, test_context: SrTestContext,
                         frames: list[tuple[str, str]]) -> None:
        for screen_name, state in frames:
            if not test_context.has_screen(screen_name, state):
                pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')

    def _install_click_stubs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """桩掉导航/编队子 op,但保留点击(驱动 fixture 帧推进);共享件/战斗态走真件。"""
        monkeypatch.setattr(use_tp_module, 'GuideTransport',
                            _click_area_stub('挑战副本-历战余响', '标题-历战余响'))
        monkeypatch.setattr(use_tp_module, 'ChooseChallengeTimes', _noop_op_stub())
        monkeypatch.setattr(use_tp_module, 'ClickChallenge',
                            _click_area_stub('挑战副本-历战余响', '挑战按钮'))
        monkeypatch.setattr(use_tp_module, 'ChooseTeam', _noop_op_stub())
        monkeypatch.setattr(use_tp_module, 'ClickStartChallenge',
                            _click_area_stub('挑战副本-历战余响', '开始挑战按钮'))
        monkeypatch.setattr(use_tp_module, 'BackToNormalWorldPlus', _noop_op_stub())

    def test_fail_once_then_retry_success(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """一败重发至达标:失败 → 共享件回挑战画面 → 滑条重发 → 胜 → 退出。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '编队态'),
            ('战斗画面', '战斗中'),
            ('大世界-战斗失败', '战斗失败'),
            ('战斗画面', '挑战成功'),
        ])
        self._install_click_stubs(monkeypatch)
        panel = {'frame': ('挑战副本-历战余响', '挑战面板'),
                 'exit': ('on_click_in', '挑战副本-历战余响', '挑战按钮')}
        team = {'frame': ('挑战副本-历战余响', '编队态'),
                'exit': ('on_click_in', '挑战副本-历战余响', '开始挑战按钮')}
        battle = {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)}
        fail = {'frame': ('大世界-战斗失败', '战斗失败'),
                'exit': ('on_click_in', '大世界-战斗失败', '点击区-空白继续')}
        phases = [
            panel, team, battle, fail,
            panel, team, battle,
            {'frame': ('战斗画面', '挑战成功'),
             'exit': ('on_click_in', '战斗画面', '退出关卡按钮')},
            {'frame': ('挑战副本-历战余响', '挑战面板')},
        ]
        op = _make_op(test_context, plan_times=1)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'一败重发未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert op.battle_fail_times == 1
        assert op.finish_times == 1
        assert ctrl.click_hit_area('大世界-战斗失败', '点击区-空白继续'), (
            f'失败画面未点空白:{ctrl.recorded_clicks}'
        )

    def test_losing_streak_five_gives_up(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """连败 5 次 → 连败关副本 → 收尾,finish_times 保持 0。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '编队态'),
            ('战斗画面', '战斗中'),
            ('大世界-战斗失败', '战斗失败'),
        ])
        self._install_click_stubs(monkeypatch)
        panel = {'frame': ('挑战副本-历战余响', '挑战面板'),
                 'exit': ('on_click_in', '挑战副本-历战余响', '挑战按钮')}
        team = {'frame': ('挑战副本-历战余响', '编队态'),
                'exit': ('on_click_in', '挑战副本-历战余响', '开始挑战按钮')}
        battle = {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)}
        fail = {'frame': ('大世界-战斗失败', '战斗失败'),
                'exit': ('on_click_in', '大世界-战斗失败', '点击区-空白继续')}
        phases = [panel, team, battle]
        for _ in range(4):
            phases += [fail, panel, team, battle]
        phases += [fail, {'frame': ('挑战副本-历战余响', '挑战面板')}]
        op = _make_op(test_context, plan_times=5)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'连败止损未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert op.battle_fail_times == 5
        assert op.finish_times == 0
