"""CwEntryExit 退局调度器测试(挂起对局处置链 + battle_x 静态页哨)。

两块被测行为:

1. 挂起对局处置链:白名单两屏(模式选择-进行中/结束结算确认弹窗)经 route
   ④b 显式点名接入,处置链下半段(挑战失败→详情→战报→大厅)复用既有节点。
   mock 分发锁形态:识别层按画面状态机应答,点击动作驱动状态转移,锁
   「状态 → route 精确分派 → 点击 area 序列」全链路由。

2. battle_x 静态页哨:「按钮-右上X」是纯定位区,对无 X 控件的页面恒点击
   恒成功、until 永不命中(WAIT 不计 retry 且清零计数,唯一硬边界 = 节点
   180s 超时)。哨 = 节点顶部连续 BATTLE_X_DEAD_CLICK_LIMIT 轮截图逐像素
   不变即提前 round_fail,把此类失效从 3 分钟压到 ~12s(基线帧 1 拍 +
   计数 3 拍,每拍 until 等待 ~3s)。直调节点函数 = 一次节点重入
   (until 不命中时框架重入整个节点函数,直调等价)。
"""

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
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    BATTLE_X_DEAD_CLICK_LIMIT,
    CwEntryExit,
)
from sr_od.operations.sr_operation import SrOperation

#: 全链剧本的状态转移表:(当前画面, 点击 area) → 下一画面
_CHAIN_TRANSITIONS: dict[tuple[str, str], str] = {
    ('货币战争-模式选择-进行中', '按钮-结束并结算'): '货币战争-模式选择-结束结算确认',
    ('货币战争-模式选择-结束结算确认', '按钮-放弃并结算'): '货币战争-挑战失败',
    ('货币战争-挑战失败', '按钮-下一步'): '货币战争-结算-对局详情',
    ('货币战争-结算-对局详情', '按钮-下一页'): '货币战争-结算-战报',
    ('货币战争-结算-战报', '按钮-返回货币战争'): '货币战争-大厅',
}

#: 挂起处置链的预期点击序列(进行中形态 → 确认弹窗 → 结算尾段既有节点)
_EXPECTED_CLICKS: list[tuple[str, str]] = list(_CHAIN_TRANSITIONS.keys())

#: 对局中名单屏(走 get_in_match_screen_name 识别的画面)
_IN_MATCH_SCREENS: frozenset[str] = frozenset({
    '货币战争-挑战失败', '货币战争-结算-对局详情', '货币战争-结算-战报',
})


class _WatchedCwEntryExit(WatchdogOperationMixin, CwEntryExit):
    """带看门狗的 CwEntryExit(防测试自身死循环),跳过游戏窗口前置。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx) -> None:
        SrOperation.__init__(
            self, ctx, op_name='退出货币战争对局', need_check_game_win=False,
        )
        # 直构绕过 CwEntryExit.__init__(need_check_game_win 不透传),
        # 哨状态属性按生产构造形态手动补齐。
        self._battle_x_prev_frame = None
        self._battle_x_static_rounds = 0


class TestPendingGiveupChain:
    """挂起对局处置全链剧本:route ④b 分派 + 星形尾段零复制。"""

    def test_full_chain_routes_and_clicks(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """进行中形态起跑:两新屏被 route ④b 分派,点击序列走完全链回大厅。"""
        state = {'screen': '货币战争-模式选择-进行中'}
        clicks: list[tuple[str, str]] = []

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            key = (s_name, a_name)
            if state['screen'] == s_name and key in _CHAIN_TRANSITIONS:
                clicks.append(key)
                state['screen'] = _CHAIN_TRANSITIONS[key]
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_in_match(ctx, screen):
            s = state['screen']
            return s if s in _IN_MATCH_SCREENS else None

        def _fake_match(ctx, screen, screen_name_list=None):
            s = state['screen']
            names = screen_name_list or []
            return s if s in names else None

        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name', _fake_in_match)
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name', _fake_match)
        monkeypatch.setattr(
            CwEntryExit, 'round_by_find_and_click_area', _fake_find_and_click)

        op = _WatchedCwEntryExit(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, f'全链应 success(终点=大厅确认),status={result.status}'
        assert result.status == CwEntryExit.STATUS_AT_LOBBY
        assert clicks == _EXPECTED_CLICKS, f'点击序列漂移:{clicks}'

    def test_pending_screens_not_dispatched_via_route_table(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """route ④b 显式点名,不经 ROUTE_BY_SCREEN(该表只收对局中屏)。"""
        assert '货币战争-模式选择-进行中' not in CwEntryExit.ROUTE_BY_SCREEN
        assert '货币战争-模式选择-结束结算确认' not in CwEntryExit.ROUTE_BY_SCREEN


class TestRouteDefaultDelegateOnly:
    """route ⑤ 纯委托契约:敌人信息浮层零特判,与全部表外画面同一去处。

    退出链内联特判已清偿(跨迭代挂账「敌人信息浮层建画面 op」条):浮层
    处理职责移入独立画面 op CwScreenEnemyInfo,经委托的 CwLoop 阶段一
    身份分发派发——本测试锁两端接线:分发清单登记(loop 侧承接的前提)+
    route ⑤ 对该屏与任意已建档对局中画面同样只发委托状态(零特判)。
    """

    def test_enemy_info_routes_to_delegate(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from sr_od.application.currency_war.kernel.cw_dispatch_tables import (
            CW_DISPATCH_SCREENS,
        )

        assert '货币战争-敌人信息浮层' in CW_DISPATCH_SCREENS, (
            '敌人信息浮层未登记分发清单:退出链委托后 loop 无承接分支')

        def _fake_in_match(ctx, screen):
            return '货币战争-敌人信息浮层'

        def _fake_match(ctx, screen, screen_name_list=None):
            return None

        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name', _fake_in_match)
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name', _fake_match)
        op = _WatchedCwEntryExit(test_context)
        op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = op.route()

        assert result.is_success, f'route 应 success 携委托状态,status={result.status}'
        assert result.status == cw_entry_exit_module.ST_DELEGATE, (
            f'敌人信息浮层应走默认委托(零特判),实际 status={result.status}')


class TestBattleXDeadClickSentinel:
    """battle_x 静态页哨:连续同帧提前失败 / 动画帧永不触发 / 损坏帧清零。"""

    @staticmethod
    def _make_op(test_context: SrTestContext,
                 monkeypatch: pytest.MonkeyPatch) -> CwEntryExit:
        """桩点击段返回 WAIT(模拟 until 永不命中的无 X 页面),直调节点函数。"""

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            return self.round_wait(status=f'{s_name}-{a_name}(until 未命中)')

        monkeypatch.setattr(
            CwEntryExit, 'round_by_find_and_click_area', _fake_find_and_click)
        op = _WatchedCwEntryExit(test_context)
        return op

    def test_static_frame_fails_fast(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """同帧连喂:基线帧 1 拍 + 计数 3 拍,第 4 次重入提前 round_fail。

        对照面:原路径唯一硬边界是节点 180s 超时(WAIT 不计 retry,retry 网
        在此路径从不生效),哨把它压到 4 次节点重入 ≈ 12s。
        """
        op = self._make_op(test_context, monkeypatch)
        frame = np.full((1080, 1920, 3), 7, dtype=np.uint8)

        results = []
        for _ in range(BATTLE_X_DEAD_CLICK_LIMIT + 1):
            op.last_screenshot = frame
            results.append(op.battle_x())

        earlier = results[:BATTLE_X_DEAD_CLICK_LIMIT]
        assert all(not r.is_success for r in earlier), (
            f'计数未满前不应失败:{[r.status for r in earlier]}')
        final = results[BATTLE_X_DEAD_CLICK_LIMIT]
        assert not final.is_success, f'哨应提前 round_fail,status={final.status}'
        assert '画面无变化' in (final.status or ''), (
            f'失败状态应含哨语义:{final.status}')

    def test_animated_frames_never_trigger(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """两帧交替(画面在变):哨永不触发,节点保持 WAIT 等待 until。"""
        op = self._make_op(test_context, monkeypatch)
        frame_a = np.full((1080, 1920, 3), 7, dtype=np.uint8)
        frame_b = np.full((1080, 1920, 3), 200, dtype=np.uint8)

        for i in range(BATTLE_X_DEAD_CLICK_LIMIT * 3):
            op.last_screenshot = frame_a if i % 2 == 0 else frame_b
            r = op.battle_x()
            assert not r.is_success, f'动画帧不应触发哨:{r.status}'
            assert '画面无变化' not in (r.status or '')

    def test_corrupt_frame_resets_counter(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """shape 不符帧按「帧变化」清零计数,不中断节点。

        序列:帧A×2(计数1) → 异常shape帧(清零) → 帧A×3(计数1→2→3 fail)。
        若损坏帧未清零,异常帧后只需 2 次同帧即 fail——fail 时机后移即清零生效。
        """
        op = self._make_op(test_context, monkeypatch)
        frame = np.full((1080, 1920, 3), 7, dtype=np.uint8)
        corrupt = np.zeros((10, 10, 3), dtype=np.uint8)

        op.last_screenshot = frame
        op.battle_x()
        op.last_screenshot = frame
        op.battle_x()
        op.last_screenshot = corrupt
        r = op.battle_x()
        assert not r.is_success and '画面无变化' not in (r.status or ''), (
            f'损坏帧应按帧变化处理:{r.status}')

        post_fail_rounds = 0
        for _ in range(BATTLE_X_DEAD_CLICK_LIMIT):
            op.last_screenshot = frame
            r = op.battle_x()
            post_fail_rounds += 1
            if '画面无变化' in (r.status or ''):
                break
        assert post_fail_rounds == BATTLE_X_DEAD_CLICK_LIMIT, (
            f'损坏帧后计数应清零重计(实际第 {post_fail_rounds} 拍即 fail)')
