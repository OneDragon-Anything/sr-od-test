"""ChallengeEchoOfWarCore 周本挑战循环核心测试。

锁设计约定(docs/develop/sr_od/application/echo_of_war/changes/weekly-challenge-core/
details/weekly-core.md 节点卡与 status 出口表):

- 节点声明:入口核对预算 5;发起链/弹窗防线预算 10;等待战斗结果/战斗超时收尾
  超时 = 家族常量(25 分钟口径);结算交互节点超时 3 分钟。
- 超时边结构:等待战斗结果与战斗超时收尾各有且仅一条「执行超时」fail 边,
  分别指向战斗超时收尾(不清场继续观察)与战斗卡死终局(自定义文案落终态)。
- 三弹窗防线:开拓力不足/本周次数耗尽/阵亡取消三个分支的识别与出口 status;
  阵亡取消沿边路由到阵亡传送恢复。
- support 'none' 兜底归一:'none' 与 None 同样跳过支援委托。
- 全流程(fixture 驱动,真实识别链):全胜循环/一败重试成功/本周次数耗尽/
  连败 5 次放弃/入口不符,八类出口 status 中可离线验的部分逐一对照。
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

from one_dragon.base.operation.operation import Operation
from sr_od.application.echo_of_war.challenge_echo_of_war_core import (
    RESULT_SETTLE_TIMEOUT_SECONDS,
    SCREEN_WEEKLY,
    STATUS_BATTLE_DEADLOCK,
    STATUS_GIVE_UP_ON_LOSING_STREAK,
    STATUS_NOT_IN_CHALLENGE_SCREEN,
    STATUS_PLAN_FINISHED,
    STATUS_POWER_INSUFFICIENT,
    STATUS_TIMEOUT_VICTORY_EXITED,
    STATUS_TIMES_EXHAUSTED,
    ChallengeEchoOfWarCore,
)
from sr_od.challenge_mission.use_trailblaze_power import (
    WAIT_RESULT_CLEANUP_TIMEOUT_SECONDS,
    WAIT_RESULT_TIMEOUT_SECONDS,
)
from sr_od.screen_state import battle_screen_state


class _WatchedCore(WatchdogOperationMixin, ChallengeEchoOfWarCore):
    """带看门狗的核心(流程测试防无限轮)。"""


def _make_core(test_context: SrTestContext, plan_times: int = 1,
               team_num: int = 0, support: str | None = None) -> ChallengeEchoOfWarCore:
    # 统一构造带看门狗的实例:节点级测试不看门狗(不调 _init_watchdog 即不生效),
    # 流程测试调 _init_watchdog 防无限轮
    return _WatchedCore(test_context, team_num=team_num,
                        plan_times=plan_times, support=support)


class TestCoreDeclarations:
    """节点声明值(预算/超时)与超时边结构。"""

    def test_node_budgets(self, test_context: SrTestContext) -> None:
        op = _make_core(test_context)
        op._init_network()
        assert op._node_map['入口核对'].node_max_retry_times == 5
        for name in ('点击挑战', '挑战后确认', '选择支援',
                     '编队后确认', '再来一次后确认'):
            assert op._node_map[name].node_max_retry_times == 10, name

    def test_timeout_declarations(self, test_context: SrTestContext) -> None:
        op = _make_core(test_context)
        op._init_network()
        assert op._node_map['等待战斗结果'].timeout_seconds == WAIT_RESULT_TIMEOUT_SECONDS
        assert op._node_map['战斗超时收尾'].timeout_seconds == (
            WAIT_RESULT_CLEANUP_TIMEOUT_SECONDS)
        for name in ('战斗结果处理', '超时退出与达标判定'):
            assert op._node_map[name].timeout_seconds == RESULT_SETTLE_TIMEOUT_SECONDS, name

    def test_timeout_edge_structure(self, test_context: SrTestContext) -> None:
        """两条超时链各有且仅一条「执行超时」fail 边,指向正确节点
        (主窗→继续观察;二次窗→卡死终局;被静默拆掉即红)。"""
        op = _make_core(test_context)
        op._init_network()

        main_edges = [
            e for e in op._node_edges_map.get('等待战斗结果', [])
            if not e.success and e.status == Operation.STATUS_TIMEOUT
        ]
        assert len(main_edges) == 1, f'主窗超时边应恰一条,实际 {main_edges}'
        assert main_edges[0].node_to.cn == '战斗超时收尾'

        cleanup_edges = [
            e for e in op._node_edges_map.get('战斗超时收尾', [])
            if not e.success and e.status == Operation.STATUS_TIMEOUT
        ]
        assert len(cleanup_edges) == 1, f'二次窗超时边应恰一条,实际 {cleanup_edges}'
        assert cleanup_edges[0].node_to.cn == '战斗卡死终局'

    def test_route_edges(self, test_context: SrTestContext) -> None:
        """关键路由边:阵亡取消三处入口、无对话框出边、重试发起、再来一次。"""
        op = _make_core(test_context)
        op._init_network()

        def _has_success_status(from_name: str, status: str, to_cn: str) -> bool:
            return any(
                e.success and e.status == status and e.node_to.cn == to_cn
                for e in op._node_edges_map.get(from_name, [])
            )

        def _has_fail_status(from_name: str, status: str, to_cn: str) -> bool:
            return any(
                not e.success and e.status == status and e.node_to.cn == to_cn
                for e in op._node_edges_map.get(from_name, [])
            )

        for from_node in ('挑战后确认', '编队后确认', '再来一次后确认'):
            assert _has_success_status(from_node, '阵亡弹框-取消', '阵亡传送恢复'), from_node
        assert _has_fail_status('挑战后确认', '无对话框', '选择配队')
        assert _has_fail_status('编队后确认', '无对话框', '等待战斗结果')
        assert _has_fail_status('再来一次后确认', '无对话框', '等待战斗结果')
        assert _has_success_status('失败画面继续', '重试再发起', '点击挑战')
        assert _has_success_status('战斗结果处理', '再来一次按钮', '再来一次后确认')
        assert _has_success_status('战斗超时收尾', '超时胜利待退出', '超时退出与达标判定')
        assert _has_success_status('战斗超时收尾', '超时判负', '失败画面继续')


class TestDialogBranches:
    """三弹窗防线的分支逻辑(桩识别直呼;识别链真伪归流程测试)。"""

    def _make_stubbbed(self, test_context: SrTestContext,
                       hit_area: str,
                       clicks: list[tuple[str, str]]) -> ChallengeEchoOfWarCore:
        op = _make_core(test_context)

        def _fake_find(screen, screen_name, area_name, **kw):
            return op.round_success() if area_name == hit_area else op.round_fail(area_name)

        def _fake_click(screen, screen_name, area_name, **kw):
            clicks.append(area_name)
            return op.round_success(area_name)

        op.round_by_find_area = _fake_find  # type: ignore[method-assign]
        op.round_by_find_and_click_area = _fake_click  # type: ignore[method-assign]
        return op

    def test_power_insufficient_dialog(self, test_context: SrTestContext) -> None:
        clicks: list[tuple[str, str]] = []
        op = self._make_stubbbed(test_context, '开拓力弹框-标题', clicks)
        result = op.confirm_after_challenge()
        assert result.is_success
        assert result.status == STATUS_POWER_INSUFFICIENT
        assert clicks == ['开拓力弹框-取消']

    def test_times_exhausted_dialog(self, test_context: SrTestContext) -> None:
        """次数耗尽按「标题+正文双锚」识别——单命中正文时由双锚检查放行。"""
        clicks: list[tuple[str, str]] = []
        op = self._make_stubbbed(test_context, '提示弹框-次数用完', clicks)

        original_find = op.round_by_find_area

        def _fake_find(screen, screen_name, area_name, **kw):
            # 标题与正文文本区都按命中桩(同一弹窗的两个锚)
            if area_name in ('提示弹框-标题', '提示弹框-次数用完'):
                return op.round_success()
            return original_find(screen, screen_name, area_name, **kw)

        op.round_by_find_area = _fake_find  # type: ignore[method-assign]
        result = op.confirm_after_challenge()
        assert result.is_success
        assert result.status == STATUS_TIMES_EXHAUSTED
        assert clicks == ['提示弹框-取消']

    def test_death_dialog_routes_cancel(self, test_context: SrTestContext) -> None:
        """阵亡弹窗:点取消,结果沿「阵亡弹框-取消」边路由(边结构在
        TestCoreDeclarations.test_route_edges 锁);此处锁点击目标与透传 status。"""
        clicks: list[tuple[str, str]] = []
        op = self._make_stubbbed(test_context, '阵亡弹框-标题', clicks)
        result = op.confirm_after_start()
        assert result.is_success
        assert result.status == '阵亡弹框-取消'
        assert clicks == ['阵亡弹框-取消']

    def test_no_dialog_returns_retry(self, test_context: SrTestContext) -> None:
        """无弹窗 → 无对话框重试等待(预算耗尽的 fail 出边在边结构测试锁)。"""
        op = self._make_stubbbed(test_context, '<命中不了任何区域>', [])
        result = op.confirm_after_challenge()
        assert not result.is_success
        assert result.status == '无对话框'
        assert result.result.name == 'RETRY'


class TestSupportNormalization:
    """support 'none' 兜底归一(包装层翻译是主责,此处锁核心防线)。"""

    def test_none_string_normalized_at_init(self, test_context: SrTestContext) -> None:
        op = _make_core(test_context, support='none')
        assert op.support is None

    def test_support_skipped_when_none(self,
                                       test_context: SrTestContext,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        op = _make_core(test_context, support=None)
        delegated: list = []
        monkeypatch.setattr(
            'sr_od.application.echo_of_war.challenge_echo_of_war_core.ChooseSupportInTeam',
            lambda ctx, character_id: delegated.append(character_id) or pytest.fail(
                'support=None 不应委托 ChooseSupportInTeam'),
        )
        result = op.choose_support()
        assert result.is_success
        assert delegated == []


class TestWaitAndTimeoutNodes:
    """等待/超时收尾/超时退出节点的行为分支(桩战斗态直呼)。"""

    def _patch_battle_state(self, monkeypatch: pytest.MonkeyPatch,
                            state: str) -> None:
        monkeypatch.setattr(
            battle_screen_state, 'get_tp_battle_screen_state',
            lambda ctx, screen, **kw: state)

    def _make_wait_op(self, test_context: SrTestContext,
                      monkeypatch: pytest.MonkeyPatch,
                      state: str) -> ChallengeEchoOfWarCore:
        op = _make_core(test_context)
        self._patch_battle_state(monkeypatch, state)
        op.screenshot = lambda *a, **kw: None  # type: ignore[method-assign]
        return op

    def test_wait_counts_success_and_fail(self,
                                          test_context: SrTestContext,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        op = self._make_wait_op(test_context, monkeypatch, '挑战成功')
        result = op.wait_battle_result()
        assert result.is_success
        assert result.status == '挑战成功'
        assert op.battle_success_times == 1

        self._patch_battle_state(monkeypatch, '战斗失败')
        result = op.wait_battle_result()
        assert result.status == '战斗失败'
        assert op.battle_fail_times == 1

        self._patch_battle_state(monkeypatch, '战斗')
        with fast_sleep():
            result = op.wait_battle_result()
        assert result.result.name == 'WAIT', f'仍在战斗应等待,实际 {result.result}'
        assert op.battle_success_times == 1 and op.battle_fail_times == 1

    def test_timeout_cleanup_routes_by_state(self,
                                             test_context: SrTestContext,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
        """二次观察窗:见胜利补记计数转退出判定;见判负转失败画面继续;仍无结算等待。"""
        op = self._make_wait_op(test_context, monkeypatch, '挑战成功')
        result = op.wait_battle_result_timeout()
        assert result.is_success
        assert result.status == '超时胜利待退出'
        assert op.battle_success_times == 1  # 主窗被打断的记账缺失在此补记

        self._patch_battle_state(monkeypatch, '战斗失败')
        result = op.wait_battle_result_timeout()
        assert result.is_success
        assert result.status == '超时判负'
        assert op.battle_success_times == 1  # 判负不补记

        self._patch_battle_state(monkeypatch, '战斗')
        with fast_sleep():
            result = op.wait_battle_result_timeout()
        assert result.result.name == 'WAIT', f'未结算应继续观察,实际 {result.result}'

    def _make_exit_op(self, test_context: SrTestContext,
                      clicks: list[str]) -> ChallengeEchoOfWarCore:
        op = _make_core(test_context)

        def _fake_click(screen, screen_name, area_name, **kw):
            clicks.append(area_name)
            return op.round_success(area_name)

        op.round_by_find_and_click_area = _fake_click  # type: ignore[method-assign]
        return op

    def test_timeout_exit_below_plan_reports_honest_status(
            self, test_context: SrTestContext) -> None:
        """超时胜利未达计划 → 「超时胜利已退出」(非假成功);点击先于达标判定。"""
        clicks: list[str] = []
        op = self._make_exit_op(test_context, clicks)
        op.battle_success_times = 0
        op.plan_times = 1
        result = op.exit_after_timeout()
        assert result.is_success
        assert result.status == STATUS_TIMEOUT_VICTORY_EXITED
        assert clicks == ['退出关卡按钮']

    def test_timeout_exit_reaching_plan_reports_finished(
            self, test_context: SrTestContext) -> None:
        clicks: list[str] = []
        op = self._make_exit_op(test_context, clicks)
        op.battle_success_times = 1
        op.plan_times = 1
        result = op.exit_after_timeout()
        assert result.is_success
        assert result.status == STATUS_PLAN_FINISHED

    def test_deadlock_end_fails_with_explicit_status(
            self, test_context: SrTestContext) -> None:
        op = _make_core(test_context)
        result = op.battle_deadlock_end()
        assert not result.is_success
        assert result.status == STATUS_BATTLE_DEADLOCK


class TestCoreFlow:
    """全流程 fixture 驱动(真实识别链)。"""

    def _run_flow(self, test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  op: ChallengeEchoOfWarCore,
                  phases: list[dict]):
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases(phases)
        op._init_watchdog()  # type: ignore[attr-defined]

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

    def test_full_win_loop_plan_times_2(self,
                                        test_context: SrTestContext,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
        """全胜循环:挑战→编队→战斗→胜→再来一次→胜→退出关卡。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '编队态'),
            ('战斗画面', '战斗中'),
            ('战斗画面', '挑战成功'),
        ])
        phases = [
            {'frame': ('挑战副本-历战余响', '挑战面板'),
             'exit': ('on_click_in', '挑战副本', '挑战按钮')},
            {'frame': ('挑战副本-历战余响', '编队态'),
             'exit': ('on_click_in', '挑战副本', '开始挑战按钮')},
            {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)},
            {'frame': ('战斗画面', '挑战成功'),
             'exit': ('on_click_in', '战斗画面', '再来一次按钮')},
            {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)},
            {'frame': ('战斗画面', '挑战成功'),
             'exit': ('on_click_in', '战斗画面', '退出关卡按钮')},
            {'frame': ('挑战副本-历战余响', '挑战面板')},
        ]
        op = _make_core(test_context, plan_times=2)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'全胜循环未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert result.status == STATUS_PLAN_FINISHED
        assert op.battle_success_times == 2
        assert ctrl.click_hit_area('挑战副本', '挑战按钮')
        assert ctrl.click_hit_area('挑战副本', '开始挑战按钮')
        assert ctrl.click_hit_area('战斗画面', '再来一次按钮')
        assert ctrl.click_hit_area('战斗画面', '退出关卡按钮')

    def test_lose_once_then_retry_success(self,
                                          test_context: SrTestContext,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """一败后重试成功:失败画面点空白回挑战画面,重新发起至达标。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '编队态'),
            ('战斗画面', '战斗中'),
            ('大世界-战斗失败', '战斗失败-历战余响'),
            ('战斗画面', '挑战成功'),
        ])
        phases = [
            {'frame': ('挑战副本-历战余响', '挑战面板'),
             'exit': ('on_click_in', '挑战副本', '挑战按钮')},
            {'frame': ('挑战副本-历战余响', '编队态'),
             'exit': ('on_click_in', '挑战副本', '开始挑战按钮')},
            {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)},
            {'frame': ('大世界-战斗失败', '战斗失败-历战余响'),
             'exit': ('on_click_in', '大世界-战斗失败', '点击区-空白继续')},
            {'frame': ('挑战副本-历战余响', '挑战面板'),
             'exit': ('on_click_in', '挑战副本', '挑战按钮')},
            {'frame': ('挑战副本-历战余响', '编队态'),
             'exit': ('on_click_in', '挑战副本', '开始挑战按钮')},
            {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)},
            {'frame': ('战斗画面', '挑战成功'),
             'exit': ('on_click_in', '战斗画面', '退出关卡按钮')},
            {'frame': ('挑战副本-历战余响', '挑战面板')},
        ]
        op = _make_core(test_context, plan_times=1)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'一败重试未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert result.status == STATUS_PLAN_FINISHED
        assert op.battle_fail_times == 1
        assert op.battle_success_times == 1
        assert ctrl.click_hit_area('大世界-战斗失败', '点击区-空白继续'), (
            f'失败画面未点空白:{ctrl.recorded_clicks}'
        )

    def test_times_exhausted_dialog_cancels(self,
                                            test_context: SrTestContext,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
        """0/3 点挑战弹次数耗尽框 → 取消 → 本周次数耗尽,无编队点击。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '次数耗尽弹窗'),
        ])
        phases = [
            {'frame': ('挑战副本-历战余响', '挑战面板'),
             'exit': ('on_click_in', '挑战副本', '挑战按钮')},
            {'frame': ('挑战副本-历战余响', '次数耗尽弹窗')},
        ]
        op = _make_core(test_context, plan_times=1)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'次数耗尽链未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert result.status == STATUS_TIMES_EXHAUSTED
        assert ctrl.click_hit_area(SCREEN_WEEKLY, '提示弹框-取消'), (
            f'未点次数耗尽弹窗取消:{ctrl.recorded_clicks}'
        )
        # 停在弹窗帧(剧本末 phase):挑战按钮与开始挑战按钮矩形重叠,不能按
        # 点击落点断言未进编队,以剧本推进位为准
        assert ctrl.phase_idx == 1, (
            f'次数耗尽不应离开弹窗帧:phase_idx={ctrl.phase_idx}'
        )

    def test_losing_streak_five_gives_up(self,
                                         test_context: SrTestContext,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
        """连败 5 次:每场经共享失败继续件回挑战画面,第 5 败后放弃。"""
        self._require_screens(test_context, [
            ('挑战副本-历战余响', '挑战面板'),
            ('挑战副本-历战余响', '编队态'),
            ('战斗画面', '战斗中'),
            ('大世界-战斗失败', '战斗失败-历战余响'),
        ])
        panel = {'frame': ('挑战副本-历战余响', '挑战面板'),
                 'exit': ('on_click_in', '挑战副本', '挑战按钮')}
        team = {'frame': ('挑战副本-历战余响', '编队态'),
                'exit': ('on_click_in', '挑战副本', '开始挑战按钮')}
        battle = {'frame': ('战斗画面', '战斗中'), 'exit': ('on_polls', 12)}
        fail = {'frame': ('大世界-战斗失败', '战斗失败-历战余响'),
                'exit': ('on_click_in', '大世界-战斗失败', '点击区-空白继续')}
        phases = [panel, team, battle]
        for _ in range(4):
            phases += [fail, panel, team, battle]
        phases += [fail, {'frame': ('挑战副本-历战余响', '挑战面板')}]

        op = _make_core(test_context, plan_times=1)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert result.success, (
            f'连败放弃链未成功:status={result.status};phase_idx={ctrl.phase_idx};'
            f'clicks={ctrl.recorded_clicks}'
        )
        assert result.status == STATUS_GIVE_UP_ON_LOSING_STREAK
        assert op.battle_fail_times == 5

    def test_entry_screen_mismatch_fails(self,
                                         test_context: SrTestContext,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
        """入口不符(大世界起跑)→ 显式失败「不在历战余响挑战画面」。"""
        self._require_screens(test_context, [('大世界', '普通')])
        phases = [{'frame': ('大世界', '普通')}]
        op = _make_core(test_context, plan_times=1)
        ctrl, result = self._run_flow(test_context, monkeypatch, op, phases)

        assert not result.success, f'入口不符应失败,实际 {result.status}'
        assert result.status == STATUS_NOT_IN_CHALLENGE_SCREEN
        assert ctrl.recorded_clicks == [], '入口不符不应有任何点击'
