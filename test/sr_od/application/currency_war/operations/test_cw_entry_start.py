"""CwEntryStart 入口链测试:挂起对局处置分支(重入旗标短路)+ 新局路径
单容器剧本。

新局路径单容器(镜像锚 = cw_entry_start.py::_discard_stale_once /
_establish_match_once;规范单一源 = skill sr-od-dev-currency-war
references/flow/entry-exit.md §1「新局确凿信号三屏」+ references/journal.md
§10):难度确认屏与简报屏是同一条新局路径上的两个「新局确凿」
信号,弃置判定每链只做一次——首个信号建容器后,后续信号幂等不弃不重建。
锁的故障形态:实机新局路径 7 次运行全中「一局双档案」——简报屏把 6 秒前
本链自建的容器当「上一局残留」弃掉重建,被弃容器带走了难度确认屏读到的
职级(整局 selected_difficulty 为空),重建容器的种子行又挂在被弃容器的
run 号下,装出一份只有种子行的空壳档。

mock 分发锁形态:识别层按画面状态机应答,点击动作驱动状态转移。
"""
from types import SimpleNamespace

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.harness.run_id_clock import advancing_run_clock

import sr_od.application.currency_war.obs.cw_observation as cw_observation_module
import sr_od.application.currency_war.operations.cw_entry.cw_entry_exit as cw_entry_exit_module
import sr_od.application.currency_war.operations.cw_entry.cw_entry_start as cw_entry_start_module
import sr_od.application.currency_war.strategies.impl.cw_strategy as cw_strategy_module
import sr_od.application.currency_war.strategies.impl.cw_strategy_manager as cw_strategy_manager_module
from sr_od.application.currency_war.operations.cw_entry.cw_entry_start import (
    CwEntryStart,
)
from sr_od.operations.sr_operation import SrOperation

_LOBBY = '货币战争-大厅'
_ONGOING = '货币战争-模式选择-进行中'
_CONFIRM = '货币战争-模式选择-结束结算确认'
_DIFFICULTY = '货币战争-难度确认'
_BRIEFING = '货币战争-简报'
_PREP = '货币战争-备战'

_BLANK = np.zeros((1080, 1920, 3), dtype=np.uint8)


class _WatchedCwEntryStart(WatchdogOperationMixin, CwEntryStart):
    """带看门狗的 CwEntryStart(防测试自身死循环),跳过游戏窗口前置。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx) -> None:
        SrOperation.__init__(
            self, ctx, op_name='开始货币战争对局', need_check_game_win=False,
        )
        # 直构绕过 CwEntryStart.__init__(need_check_game_win 不透传),
        # 实例状态属性按生产构造形态手动补齐。
        self._advance_steps = 0
        self._stale_discarded = False
        self._lobby_anchor_rounds = 0
        self._residual_closed = False
        self._residual_reentered = False
        self._disposed_pending_match = False


class TestPendingDisposeReentry:
    """挂起局委托处置 → 旗标重入剧本。"""

    @staticmethod
    def _install_mocks(
        monkeypatch: pytest.MonkeyPatch,
        state: dict[str, str],
        clicks: list[tuple[str, str]],
        exit_calls: dict[str, int],
    ) -> None:
        """按画面状态机装识别/点击/委托桩。

        点开始按钮的转移按「挂起局是否已结算」分流(真实游戏语义):委托已
        发生 = 服务端挂起局已放弃,点开始进正常新局链(剧本直达备战);
        委托未发生 = 服务端仍有挂起局,点开始落「模式选择-进行中」。
        委托假类 execute 成功 = 挂起局已结算回大厅(驱动状态转移)。
        """

        def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
            cur = state['screen']
            if cur == _PREP and s_name == CwEntryStart.PREP_SCREEN:
                return self.round_success(status=a_name)
            if cur == _LOBBY and s_name == CwEntryStart.LOBBY_SCREEN \
                    and a_name == '标识-玩法名':
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            cur = state['screen']
            if cur == _LOBBY and s_name == CwEntryStart.LOBBY_SCREEN \
                    and a_name == '按钮-开始货币战争':
                clicks.append((s_name, a_name))
                # 转移按「挂起局是否已结算」分流(真实游戏语义):委托已发生
                # = 服务端挂起局已放弃,点开始进正常新局链(剧本直达备战);
                # 委托未发生 = 服务端仍有挂起局,点开始落「模式选择-进行中」。
                if exit_calls['executed'] > 0:
                    state['screen'] = _PREP
                else:
                    state['screen'] = _ONGOING
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_ocr(self, screen, text, *args, **kwargs):
            return self.round_wait(status=f'OCR 未命中 {text}')

        def _fake_match(ctx, screen, screen_name_list=None):
            s = state['screen']
            names = screen_name_list or []
            return s if s in names else None

        class _FakeCwEntryExit:
            """记录调用的 CwEntryExit 假类(委托成功 = 已回大厅)。"""

            def __init__(self, ctx) -> None:
                exit_calls['constructed'] += 1

            def execute(self):
                exit_calls['executed'] += 1
                state['screen'] = _LOBBY
                return SimpleNamespace(success=True, status='已返回货币战争大厅')

        monkeypatch.setattr(
            CwEntryStart, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            CwEntryStart, 'round_by_find_and_click_area', _fake_find_and_click)
        monkeypatch.setattr(CwEntryStart, 'round_by_ocr', _fake_ocr)
        monkeypatch.setattr(CwEntryStart, 'round_by_ocr_and_click', _fake_ocr)
        monkeypatch.setattr(
            cw_entry_start_module, 'get_match_screen_name', _fake_match)
        # 委托假类桩在 cw_entry_exit 模块属性上:生产侧节点内惰性 import
        # (from cw_entry_exit import CwEntryExit),import 时读模块属性。
        monkeypatch.setattr(cw_entry_exit_module, 'CwEntryExit', _FakeCwEntryExit)

    @staticmethod
    def _run(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch) -> tuple[object,
                                                        list[tuple[str, str]],
                                                        dict[str, int]]:
        state = {'screen': _LOBBY}
        clicks: list[tuple[str, str]] = []
        exit_calls: dict[str, int] = {'constructed': 0, 'executed': 0}
        TestPendingDisposeReentry._install_mocks(
            monkeypatch, state, clicks, exit_calls)

        op = _WatchedCwEntryStart(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)
        return result, clicks, exit_calls

    def test_dispose_then_reentry_clicks_start_not_close(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """挂起态起跑:委托处置回大厅后走旗标重入(点开始),不走残留逃逸(点关闭)。"""
        result, clicks, exit_calls = self._run(test_context, monkeypatch)

        assert result.success, f'应经处置+重开到达备战,status={result.status}'
        assert result.status == CwEntryStart.STATUS_AT_PREP
        assert exit_calls['executed'] == 1, (
            f'委托退出 op 应恰执行一次(实际 {exit_calls["executed"]})')
        # 旗标重入的错位锁:点开始发生、点关闭(残留逃逸首步)零发生。
        assert (_LOBBY, '按钮-开始货币战争') in clicks, f'点击记录:{clicks}'
        assert (_LOBBY, '按钮-关闭') not in clicks, (
            f'处置回大厅误走残留逃逸(点关闭),点击记录:{clicks}')

    def test_residual_confirm_popup_redelegates(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """委托中途失败残留的确认弹窗:advance 循环直接点名 → 重新委托收敛。

        与上一剧本共用转移骨架,起点画面改为确认弹窗(click_start 点开始后
        落在弹窗而非进行中形态,模拟上一轮委托残留)。
        """
        state = {'screen': _LOBBY}
        clicks: list[tuple[str, str]] = []
        exit_calls: dict[str, int] = {'constructed': 0, 'executed': 0}
        self._install_mocks(monkeypatch, state, clicks, exit_calls)

        # 点开始落在确认弹窗(委托中途失败的残留态):重装点击桩,
        # 首次「点开始」转移落弹窗,旗标重入的第二次「点开始」直达备战。
        installed_find_click = CwEntryStart.round_by_find_and_click_area

        def _patched_first_click(self, screen, s_name, a_name, *args, **kwargs):
            cur = state['screen']
            if cur == _LOBBY and s_name == CwEntryStart.LOBBY_SCREEN \
                    and a_name == '按钮-开始货币战争':
                if getattr(self, '_first_start_done', False):
                    state['screen'] = _PREP
                else:
                    self._first_start_done = True
                    state['screen'] = _CONFIRM
                return self.round_success(status=a_name)
            return installed_find_click(self, screen, s_name, a_name,
                                        *args, **kwargs)

        monkeypatch.setattr(
            CwEntryStart, 'round_by_find_and_click_area', _patched_first_click)

        op = _WatchedCwEntryStart(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, f'弹窗残留应由重新委托收敛,status={result.status}'
        assert exit_calls['executed'] == 1


class TestNewGameSignalsSingleContainer:
    """新局路径剧本:大厅 → 难度确认屏 → 简报屏 → 备战。

    前置 = 生产形态:进程里已有一个收尾的上局 run(新局种子行若取「进程
    当前号」就会挂进它);run_id 跨秒时钟(两次铸造必不同号)。假简报 op 走
    真实上报口 ``report_screen_briefing_obs`` 写三读数 = 「种子行之后的后续行」
    样本。断言面 = design §2.3 判据三样:容器恰一次、流水同号且版本自 1
    连续、职级写入行在、装配恰一局。
    """

    @staticmethod
    def _install_mocks(
        monkeypatch: pytest.MonkeyPatch,
        state: dict[str, str],
        seen: dict[str, object],
    ) -> None:
        """按画面状态机装识别/点击桩 + 职级读数桩 + 假简报 op + 漏斗探针。

        探针包住真实函数透传(计 establish 调用次数与实际弃置次数,不替代
        被测逻辑);「按钮-开始对局」点击时刻记下当时容器 = 难度确认屏建
        的那个,供事后比对同一性。
        """

        def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
            cur = state['screen']
            hit = (
                (cur == _PREP and s_name == CwEntryStart.PREP_SCREEN
                 and a_name == '备战标识-购买经验'),
                (cur == _DIFFICULTY and s_name == CwEntryStart.DIFFICULTY_SCREEN
                 and a_name in ('标识-当前职级难度效果', '按钮-开始对局')),
                (cur == _BRIEFING and s_name == CwEntryStart.BRIEFING_SCREEN
                 and a_name == '标识-本场对局首领'),
            )
            if any(hit):
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            cur = state['screen']
            if cur == _LOBBY and s_name == CwEntryStart.LOBBY_SCREEN \
                    and a_name == '按钮-开始货币战争':
                state['screen'] = _DIFFICULTY
                return self.round_success(status=a_name)
            if cur == _DIFFICULTY and s_name == CwEntryStart.DIFFICULTY_SCREEN \
                    and a_name == '按钮-开始对局':
                seen['at_start_click'] = self.ctx.cw_match
                state['screen'] = _BRIEFING
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_ocr(self, screen, text, *args, **kwargs):
            return self.round_wait(status=f'OCR 未命中 {text}')

        def _fake_match(ctx, screen, screen_name_list=None):
            return None

        class _FakeCwScreenBriefing:
            """假简报 op:真实上报口写三读数进本局容器,再推进到备战。"""

            def __init__(self, ctx) -> None:
                self.ctx = ctx
                seen['briefing_constructed'] = (
                    seen.get('briefing_constructed', 0) + 1)

            def execute(self):
                from sr_od.application.currency_war.kernel.cw_screen_report.briefing import (
                    CwScreenBriefingObs,
                    report_screen_briefing_obs,
                )
                report_screen_briefing_obs(
                    self.ctx.cw_match.gs,
                    CwScreenBriefingObs(enemy_affixes=['词缀样本'],
                                        plane_bosses=['首领样本'],
                                        enemy_difficulty=3))
                state['screen'] = _PREP
                return SimpleNamespace(success=True)

        real_establish = cw_strategy_manager_module.establish_new_match
        real_discard = cw_strategy_module.discard_stale_match_container

        def _spy_establish(ctx, config, opened_via):
            # 只计「真建了容器」(返回 True);幂等直过(False)不计——对应
            # 生产日志「match 状态容器已建立」条数。
            built = real_establish(ctx, config, opened_via)
            if built:
                seen['containers_built'] = seen.get('containers_built', 0) + 1
            return built

        def _spy_discard(ctx, reason):
            discarded = real_discard(ctx, reason)
            if discarded:
                seen['discards'] = seen.get('discards', 0) + 1
            return discarded

        monkeypatch.setattr(
            CwEntryStart, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            CwEntryStart, 'round_by_find_and_click_area', _fake_find_and_click)
        monkeypatch.setattr(CwEntryStart, 'round_by_ocr', _fake_ocr)
        monkeypatch.setattr(CwEntryStart, 'round_by_ocr_and_click', _fake_ocr)
        monkeypatch.setattr(
            cw_entry_start_module, 'get_match_screen_name', _fake_match)
        monkeypatch.setattr(
            cw_entry_start_module, 'CwScreenBriefing', _FakeCwScreenBriefing)
        monkeypatch.setattr(cw_observation_module, 'read_selected_difficulty',
                            lambda ctx, screen: 'A5')
        # 两探针都住在各自模块属性上:生产侧节点内惰性 import 读模块属性。
        monkeypatch.setattr(cw_strategy_manager_module, 'establish_new_match',
                            _spy_establish)
        monkeypatch.setattr(cw_strategy_module, 'discard_stale_match_container',
                            _spy_discard)

    @pytest.fixture
    def cw_run_env(self, test_context: SrTestContext,
                   monkeypatch: pytest.MonkeyPatch) -> SrTestContext:
        """遥测 run 态簇前后复位 + ctx 挂拆还原 + run_id 跨秒时钟。"""
        from sr_od.application.currency_war.telemetry import state as cw_state
        cw_state.reset_run_state()
        monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
        monkeypatch.setattr(test_context, 'cw_selected_difficulty', None,
                            raising=False)
        advancing_run_clock(monkeypatch)
        yield test_context
        cw_state.reset_run_state()

    def test_two_new_game_signals_keep_one_container_one_run(
        self,
        cw_run_env: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """判据三样一次核:建容器恰 1 次 / 实际弃置 0 次 / 两信号前后
        容器同一对象;流水全部行同一 run(= created_run_id)、v 自 1 连续、
        上局号零新行、含 selected_difficulty='A5' 写入行;assign_games 恰 1 局。"""
        from sr_od.application.currency_war.kernel import cw_state_journal
        from sr_od.application.currency_war.telemetry import state as cw_state
        from sr_od.application.currency_war.telemetry.journal_query import (
            read_journal_stats,
        )
        from sr_od.application.currency_war.telemetry.match_archive import (
            assign_games,
        )

        test_context = cw_run_env
        prev_run = cw_state.start_run()
        cw_state.close_run()   # 进程里已有一个收尾的上局 run(生产常态)

        state = {'screen': _LOBBY}
        seen: dict[str, object] = {}
        self._install_mocks(monkeypatch, state, seen)

        op = _WatchedCwEntryStart(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success and result.status == CwEntryStart.STATUS_AT_PREP, \
            f'应沿新局链到达备战,status={result.status}'
        match = test_context.cw_match
        assert match is not None and match.opened_via == 'new_game'
        # 判据 2:容器恰一次、无弃置、两信号前后同一对象。
        assert seen.get('containers_built') == 1, (
            f'新局路径应恰建容器 1 次,实际 {seen.get("containers_built")}')
        assert seen.get('discards', 0) == 0, (
            f'本链自建容器不得被当上局残留弃置,实际弃置 {seen.get("discards")} 次')
        assert match is seen.get('at_start_click'), \
            '简报屏信号不得替换难度确认屏建的容器'
        # 判据 1 + 3:流水全部行同号、版本自 1 连续、上局号零新行、职级行在。
        cw_state_journal.flush_pending()
        rows, _stats = read_journal_stats(tmp_path)
        assert rows, '状态流水应有行(种子 + 职级 + 简报三读数)'
        run_ids = {r.get('run_id') for r in rows}
        assert run_ids == {match.created_run_id}, (
            f'一局流水应全部挂在容器自己的 run 下,实际 {sorted(map(str, run_ids))}'
            f' vs created_run_id={match.created_run_id!r}')
        assert prev_run not in run_ids, '本局行不得挂进上局已收尾的 run'
        assert [r['v'] for r in rows] == list(range(1, len(rows) + 1)), \
            '同号内版本号应自 1 连续不重复(一容器一 run)'
        diff_rows = [r for r in rows
                     if r.get('field') == 'selected_difficulty']
        assert diff_rows and diff_rows[0].get('after') == 'A5', (
            '难度确认屏读到的职级应有写入行留在本局 run'
            + ('(实际 0 行)' if not diff_rows
               else f'(实际 after={diff_rows[0].get("after")!r})'))
        assert match.gs.selected_difficulty.value == 'A5'
        # 判据 3:装配恰一局。
        games = assign_games(tmp_path)
        assert len(games) == 1 and games[0]['segments'] == [match.created_run_id], (
            f'一次新局应装恰 1 局且段 = 本局 run,实际 {games}')
