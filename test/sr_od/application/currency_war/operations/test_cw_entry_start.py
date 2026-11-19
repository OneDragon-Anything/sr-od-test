"""CwEntryStart 挂起对局处置分支测试(重入旗标短路)。

被测行为:点开始后落在挂起对局入口两屏(模式选择-进行中/结束结算确认)
→ 委托退出 op 结算挂起局回大厅 → 重入旗标短路:处置回的新鲜大厅直接点
「按钮-开始货币战争」重开,不走「残留大厅」分支的关X+F重进逃逸弯路
——这是本分支最容易回归的错位(两种大厅同帧异态:新鲜大厅开始按钮可点,
死按钮残留态必须关X逃逸)。

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

import sr_od.application.currency_war.operations.cw_entry.cw_entry_exit as cw_entry_exit_module
import sr_od.application.currency_war.operations.cw_entry.cw_entry_start as cw_entry_start_module
from sr_od.application.currency_war.operations.cw_entry.cw_entry_start import (
    CwEntryStart,
)
from sr_od.operations.sr_operation import SrOperation

_LOBBY = '货币战争-大厅'
_ONGOING = '货币战争-模式选择-进行中'
_CONFIRM = '货币战争-模式选择-结束结算确认'
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
