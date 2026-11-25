"""CwEntryExit 退局调度器测试(挂起对局处置链 + battle_x 静态页哨 + 认画面回头路)。

三块被测行为:

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

3. battle_x 认画面回头路:误入点 X 节点后,每轮点击前先认「路由有去处的画面」
   (对局中画面名单 + 大厅),认出且非战斗自家画面就不点、回路由重识别;连续
   2 次认出同一画面判失败(路由↔点 X 互踢硬边界)。

4. 合成确认浮层在场的备战帧不走「备战退局发起」:浮层是全局模态,点门形图标会被
   它吞掉——路由③要求浮层不在场,这种帧落⑤委托(用真样本帧走真识别)。
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
from sr_od.application.currency_war.cw_screen_state import (
    PREP_DIRECT_EXIT_SCREENS,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    BATTLE_STREAK_ENTER,
    BATTLE_X_DEAD_CLICK_LIMIT,
    ST_SCREEN_RECOGNIZED,
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

#: 误入回头路剧本的转移表 = 备战退局两步 + 结算尾段(不并入 _CHAIN_TRANSITIONS:
#: 它的键是既有全链测试的期望点击序列)。
_PREP_EXIT_TRANSITIONS: dict[tuple[str, str], str] = {
    ('货币战争-备战', '按钮-退出对局'): '货币战争-中断挑战弹窗',
    ('货币战争-中断挑战弹窗', '按钮-放弃并结算'): '货币战争-挑战失败',
}
_PREP_EXIT_TRANSITIONS.update({
    k: v for k, v in _CHAIN_TRANSITIONS.items()
    if k[0] != '货币战争-模式选择-进行中'
    and k[0] != '货币战争-模式选择-结束结算确认'
})

#: 误入回头路剧本里对局中名单识别能认出的画面(备战与中断挑战弹窗不在
#: _IN_MATCH_SCREENS 内,本剧本自建集)。
_RECOGNIZABLE_IN_MATCH: frozenset[str] = _IN_MATCH_SCREENS | frozenset({
    '货币战争-备战', '货币战争-中断挑战弹窗',
})


class _WatchedCwEntryExit(WatchdogOperationMixin, CwEntryExit):
    """带看门狗的 CwEntryExit(防测试自身死循环),跳过游戏窗口前置。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx) -> None:
        SrOperation.__init__(
            self, ctx, op_name='退出货币战争对局', need_check_game_win=False,
        )
        # 直构绕过 CwEntryExit.__init__(need_check_game_win 不透传),
        # 节点状态属性按生产构造形态手动补齐(route 的未识别计数、battle_x 的
        # 哨状态与重复认出计数)。
        self._miss_streak = 0
        self._battle_x_prev_frame = None
        self._battle_x_static_rounds = 0
        self._battle_x_recognized_name = None
        self._battle_x_recognized_times = 0


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

        # 画面识别桩恒认不出:本类只测哨,不走真的建档识别。
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name',
            lambda ctx, screen: None)
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name',
            lambda ctx, screen, screen_name_list=None: None)
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


class _RecordingCwEntryExit(_WatchedCwEntryExit):
    """按轮记录当前节点名(相邻重入去重),供断言节点顺序。"""

    def __init__(self, ctx, node_trace: list[str]) -> None:
        _WatchedCwEntryExit.__init__(self, ctx)
        self._node_trace = node_trace

    def _execute_one_round(self):  # type: ignore[override]
        name = self._current_node.cn
        if not self._node_trace or self._node_trace[-1] != name:
            self._node_trace.append(name)
        return _WatchedCwEntryExit._execute_one_round(self)


class TestBattleXRecognizeScreen:
    """battle_x 认画面回头路:误入后认出备战回路由 / 战斗自家画面不回头 / 互踢硬边界。"""

    @staticmethod
    def _make_op(test_context: SrTestContext) -> CwEntryExit:
        op = _WatchedCwEntryExit(test_context)
        op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)
        return op

    @pytest.mark.parametrize('entry', ['已是备战', '点X后到备战'])
    def test_recognized_prep_returns_to_route(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        entry: str,
    ) -> None:
        """路由连续认不出判「战斗中」误入点 X 节点后,认出备战回路由走完退局链。

        entry=已是备战:第 1 轮就认出,点 X 0 次;entry=点X后到备战:初值画面
        认不出,点 1 次 X 把画面切到备战,第 2 轮认出。对局中名单识别桩前
        BATTLE_STREAK_ENTER + 1 次(全部来自路由)一律认不出,之后按状态机应答。
        """
        unrecognized_screen = '货币战争-认不出的过渡画面'
        state = {
            'screen': '货币战争-备战' if entry == '已是备战' else unrecognized_screen,
        }
        calls = {'in_match': 0, 'in_match_at_prep_exit': None}
        clicks: list[tuple[str, str]] = []
        node_trace: list[str] = []

        def _fake_in_match(ctx, screen):
            calls['in_match'] += 1
            if calls['in_match'] <= BATTLE_STREAK_ENTER + 1:
                return None
            s = state['screen']
            return s if s in _RECOGNIZABLE_IN_MATCH else None

        def _fake_match(ctx, screen, screen_name_list=None):
            s = state['screen']
            names = screen_name_list or []
            return s if s in names else None

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            key = (s_name, a_name)
            if key == ('货币战争-备战', '按钮-退出对局') \
                    and calls['in_match_at_prep_exit'] is None:
                calls['in_match_at_prep_exit'] = calls['in_match']
            if state['screen'] == unrecognized_screen \
                    and key == ('货币战争-战斗', '按钮-右上X'):
                clicks.append(key)
                state['screen'] = '货币战争-备战'
                return self.round_wait(status=f'{a_name}(until 未命中)')
            if state['screen'] == s_name and key in _PREP_EXIT_TRANSITIONS:
                clicks.append(key)
                state['screen'] = _PREP_EXIT_TRANSITIONS[key]
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name', _fake_in_match)
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name', _fake_match)
        # 路由③的「可安全交还」判定在本用例按屏名应答:本用例演的是认出备战之后的
        # 节点链,画面是状态机假件;「浮层在场就不走退局发起」那一条由
        # TestSynthesisOverlayFrameNotDirectExit 用真样本帧走真识别来锁。
        monkeypatch.setattr(
            cw_entry_exit_module, 'is_exit_safe_prep_frame',
            lambda ctx, screen, screen_name=None: (
                screen_name in PREP_DIRECT_EXIT_SCREENS))
        monkeypatch.setattr(
            CwEntryExit, 'round_by_find_and_click_area', _fake_find_and_click)

        op = _RecordingCwEntryExit(test_context, node_trace)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        x_key = ('货币战争-战斗', '按钮-右上X')
        expected_x = 0 if entry == '已是备战' else 1
        tail = [
            ('货币战争-备战', '按钮-退出对局'),
            ('货币战争-中断挑战弹窗', '按钮-放弃并结算'),
            ('货币战争-挑战失败', '按钮-下一步'),
            ('货币战争-结算-对局详情', '按钮-下一页'),
            ('货币战争-结算-战报', '按钮-返回货币战争'),
        ]
        assert result.success, f'应 success(终点=大厅确认),status={result.status}'
        assert result.status == CwEntryExit.STATUS_AT_LOBBY
        assert clicks.count(x_key) == expected_x, f'右上X 点击次数漂移:{clicks}'
        assert [c for c in clicks if c != x_key] == tail, f'点击序列漂移:{clicks}'
        # 首次点退出对局之前的识别桩调用数 = 路由 5 + 点 X 节点(1 或 2)+ 路由 1
        expected_calls = BATTLE_STREAK_ENTER + (3 if entry == '已是备战' else 4)
        assert calls['in_match_at_prep_exit'] == expected_calls, (
            f'点 X 节点跑的轮数不对:首次点退出对局前识别桩调用 '
            f'{calls["in_match_at_prep_exit"]} 次,期望 {expected_calls} 次')
        i = node_trace.index('战斗中点右上X')
        assert node_trace[i - 1:i + 3] == [
            '画面路由', '战斗中点右上X', '画面路由', '备战退局发起'], (
            f'节点顺序漂移:{node_trace}')

    @pytest.mark.parametrize('own_screen', ['货币战争-战斗', '货币战争-战斗暂停'])
    def test_own_screens_never_return(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        own_screen: str,
    ) -> None:
        """战斗自家画面连续认出 3 轮:每轮照点 X、不回头、不因重复认出判失败。"""
        clicks: list[tuple[str, str]] = []

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            clicks.append((s_name, a_name))
            return self.round_success(status=a_name)

        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name',
            lambda ctx, screen: own_screen)
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name',
            lambda ctx, screen, screen_name_list=None: None)
        monkeypatch.setattr(
            CwEntryExit, 'round_by_find_and_click_area', _fake_find_and_click)
        op = self._make_op(test_context)

        for _ in range(3):
            r = op.battle_x()
            assert ('货币战争-战斗', '按钮-右上X') in clicks
            assert r.status != ST_SCREEN_RECOGNIZED, f'战斗自家画面不应回头:{r.status}'
            assert r.is_success, f'不应因重复认出判失败:{r.status}'

    @pytest.mark.parametrize(
        'sequence',
        [
            ['货币战争-结算-战报', None, '货币战争-结算-战报'],
            ['货币战争-结算-战报', '货币战争-结算-战报'],
        ],
        ids=['中间认不出则计数清零', '连续同名即失败'],
    )
    def test_repeat_recognized_limit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        sequence: list,
    ) -> None:
        """连续 2 次认出同一画面判失败;中间出现认不出的一轮则计数清零。"""
        answers = iter(sequence)
        clicks: list[tuple[str, str]] = []

        def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
            clicks.append((s_name, a_name))
            return self.round_wait(status=f'{a_name}(until 未命中)')

        monkeypatch.setattr(
            cw_entry_exit_module, 'get_in_match_screen_name',
            lambda ctx, screen: next(answers, None))
        monkeypatch.setattr(
            cw_entry_exit_module, 'get_match_screen_name',
            lambda ctx, screen, screen_name_list=None: None)
        monkeypatch.setattr(
            CwEntryExit, 'round_by_find_and_click_area', _fake_find_and_click)
        op = self._make_op(test_context)

        results = [op.battle_x() for _ in sequence]

        if sequence[1] is None:
            r1, _, r3 = results
            assert r1.is_success and r1.status == ST_SCREEN_RECOGNIZED
            assert len(clicks) == 1, f'认出的轮不点击、认不出的轮点一次:{clicks}'
            assert r3.is_success and r3.status == ST_SCREEN_RECOGNIZED, (
                f'中间认不出后计数应清零,再次认出仍成功:{r3.status}')
        else:
            r1, r2 = results
            assert r1.is_success and r1.status == ST_SCREEN_RECOGNIZED
            assert clicks == [], f'认出的轮不点击:{clicks}'
            assert not r2.is_success and '认出同一画面' in (r2.status or ''), (
                f'连续同名认出应判失败:{r2.status}')


class TestSynthesisOverlayFrameNotDirectExit:
    """合成确认浮层在场的备战帧不走「备战退局发起」。

    浮层在场时备战画面的识别标志照样全中、屏名仍在 A 类名单里,只看屏名会把它当成
    可交还态去点门形图标——那一下会被浮层吞掉,退局必败。路由③因此多一个条件
    「浮层不在场」:不满足的帧落⑤默认委托,由对局循环派备战画面 op 先处置浮层。
    用真样本帧走真识别(画面识别与浮层识别都是真的)。
    """

    @pytest.mark.parametrize(
        ('frame', 'expected_status'),
        [
            (('货币战争-备战', 'deployed_2star'), cw_entry_exit_module.ST_PREP),
            (('货币战争-备战', 'rail_badge_absent_r2'),
             cw_entry_exit_module.ST_DELEGATE),
        ],
        ids=['干净备战帧→备战退局发起', '合成确认浮层在场→委托对局循环'],
    )
    def test_route_needs_overlay_absent(self, test_context: SrTestContext,
                                        frame: tuple[str, str],
                                        expected_status: str) -> None:
        op = _WatchedCwEntryExit(test_context)
        op.last_screenshot = test_context.load_screen(*frame)

        result = op.route()

        assert result.is_success, f'route 应 success,status={result.status}'
        assert result.status == expected_status
