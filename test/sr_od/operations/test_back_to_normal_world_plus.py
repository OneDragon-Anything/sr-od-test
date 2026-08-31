"""BackToNormalWorldPlus 兜底分支防死循环测试。

背景(2026-08-24 实跑事故):框架 retry 语义中 WAIT 不消耗 ``node_max_retry_times``
且任何非 RETRY 结果会把 ``node_retry_times`` 清零(``operation.py`` 循环)。原兜底
分支(未知画面 → 点「菜单-右上角返回」后 ``round_wait``)在点击无法改变画面时
(如战斗结算画面)会**无限循环**——实跑卡约 2 小时拖垮整条一条龙。

修复:兜底分支改用 ``round_retry``,让兜底也计入 ``node_max_retry_times=20``,
20 次后节点 FAIL、op 报失败而非卡死。正常「连续退多级菜单」不受影响:每退一级
后画面变化命中其他分支返回 WAIT/SUCCESS,retry 计数被清零。

测试构造:所有画面识别(find 类)恒不命中 + 模拟宇宙状态恒 None + 列车补给恒
False → 每轮必然落入兜底分支。断言:

- op 以 FAIL 结束(而非永远 WAIT);
- 总轮次有界(≈ node_max_retry_times+1,看门狗未触发);
- 兜底点击次数 == 总轮次(每轮都点右上角)。
"""

from __future__ import annotations

import numpy as np
import pytest

import sr_od.operations.back_to_normal_world_plus as btnw_module
from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from one_dragon.utils.i18_utils import gt
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus
from sr_od.operations.interact.talk_interact import TalkInteract
from sr_od.operations.sr_operation import SrOperation
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
)


class _WatchedBackToNormal(WatchdogOperationMixin, BackToNormalWorldPlus):
    """带看门狗的 BackToNormalWorldPlus(防测试自身死循环)。"""

    watchdog_max_rounds: int = 50

    def __init__(self, ctx) -> None:
        """跳过游戏窗口前置节点(MockController 无 game_win,与本测试无关)。"""
        # BackToNormalWorldPlus.__init__ 不透传 need_check_game_win,这里直接走
        # SrOperation 构造(节点注册发生在 __init__,事后翻转属性无效)。
        SrOperation.__init__(
            self, ctx, op_name=gt('返回普通大世界'), need_check_game_win=False,
        )


@pytest.fixture()
def stuck_op(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_WatchedBackToNormal, dict[str, int]]:
    """构造「兜底点击无法改变画面」的假环境,返回 (op, 计数字典)。

    - find 类识别(``round_by_find_area`` / ``round_by_find_and_click_area``)恒返回
      未命中(结果仅被 ``is_success`` 检查后丢弃,用 WAIT 构造即可);
    - 兜底点击(``round_by_click_area``)恒「点击成功」并计数(模拟点击发出去了
      但画面不变——正是事故现场的语义);
    - 模拟宇宙状态 / 列车补给恒无。
    """
    counters: dict[str, int] = {'fallback_click': 0}

    def _fake_find_area(self, screen, screen_name, area_name, *args, **kwargs):
        return self.round_wait(status=f'未找到 {area_name}')

    def _fake_click_area(self, screen_name, area_name, *args, **kwargs):
        counters['fallback_click'] += 1
        return self.round_success(status=area_name)

    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_area
    )
    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _fake_click_area)
    monkeypatch.setattr(
        btnw_module.sim_uni_screen_state,
        'get_sim_uni_screen_state',
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        btnw_module.common_screen_state,
        'is_express_supply',
        lambda *args, **kwargs: False,
    )
    # 对话态守卫走真实 ctx.ocr(session 级真模型,对空白 mock 帧推理既慢又不定)
    # → 恒「无对话」:守卫返回 None,每轮照旧落兜底(本测试的构造语义不变)。
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'check_npc_dialog', lambda self, screen: None,
    )

    op = _WatchedBackToNormal(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    return op, counters


class TestBackToNormalWorldPlusFallback:

    def test_stuck_fallback_fails_bounded(
        self,
        test_context: SrTestContext,
        stuck_op: tuple[_WatchedBackToNormal, dict[str, int]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """兜底点击无法改变画面时:op 应 FAIL 且轮次有界(修复前永远 WAIT)。"""
        op, counters = stuck_op
        sleeps = _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 修复后:兜底计入 retry,超 node_max_retry_times=20 后节点 FAIL。
        assert not result.success, (
            f'兜底卡死场景不应 success:status={result.status}'
        )
        # 轮次有界:看门狗(50)未触发,总轮次 ≈ 20 次 retry + 1 次 FAIL 判定。
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert rounds <= 25, f'轮次超界({rounds}),疑似死循环未修复'
        assert rounds >= 20, f'轮次异常偏少({rounds}),应耗满 20 次 retry 才 FAIL'
        # 每轮兜底都真实点击了右上角(点击发出但画面不变)。
        assert counters['fallback_click'] == rounds, (
            f'兜底点击数({counters["fallback_click"]}) != 轮次({rounds})'
        )
        # 每轮 retry 都带 wait=1(防回归为无 wait 的异常风暴式快速重试)。
        assert len(sleeps) >= rounds, (
            f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        )

    def test_click_fail_fails_bounded(
        self,
        test_context: SrTestContext,
        stuck_op: tuple[_WatchedBackToNormal, dict[str, int]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """兜底点击本身失败(如窗口失焦)时:同样应 FAIL 有界且每轮有 wait。

        2026-08-24 实锤:两小时 WAIT 循环的结尾是 controller.click 失败后转入
        无 wait 的异常风暴(每 ~24ms 一轮刷屏)。修复后该路径每轮 retry 带
        wait=1,20 轮后有序 FAIL,不再提供风暴式无间隔重试。
        """
        op, counters = stuck_op
        sleeps = _patch_round_sleep(monkeypatch)

        # 兜底点击改为「点击失败」:round_by_click_area 失败分支返回 RETRY
        # 且自身 retry_wait=None(无 sleep),由外层包装的 wait=1 兜住节奏。
        def _fake_click_fail(self, screen_name, area_name, *args, **kwargs):
            counters['fallback_click'] += 1
            return self.round_retry(status=f'点击失败 {area_name}')

        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _fake_click_fail)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert not result.success, f'点击失败场景不应 success:status={result.status}'
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert 20 <= rounds <= 25, f'轮次异常({rounds}),应耗满 20 次 retry 才 FAIL'
        # 每轮都有 wait(≥ rounds 次 sleep),防无间隔风暴。
        assert len(sleeps) >= rounds, (
            f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds}),存在无 wait 重试轮'
        )


class TestNamelessHonorBranches:
    """无名勋礼退出链分支:推广页 / 等级加速弹窗 / 主面板。

    背景:2026-08-26 版本周期首进无名勋礼先落购买推广页(点「开启无名勋礼」
    不会付费,用户裁决),实证退出链(编排者 2026-08-27 live 四步全走通):
    推广页 → 开启 → 等级加速弹窗(点提示位关闭)→ 主面板 → 右上角关闭 → 菜单页。
    三支均「id_mark 命中 → area 点击 → round_retry 逐帧重识别」(大厅分支
    同构):点击可能不落地,RETRY 计入 node_max_retry_times=20 有界 FAIL;
    多跳中间态靠逐帧重识别天然容忍,无跨轮状态。
    """

    def test_nameless_honor_promo_branch(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """场景:无名勋礼购买推广页帧命中专属分支,不进对话态守卫与兜底。

        背景(2026-08-26 版本周期首进,编排者 2026-08-27 live 实证退出链):
        版本更新后第一次进无名勋礼先落整屏购买推广页,点「开启无名勋礼」是
        查看/继续语义(**不会付费**,用户裁决)→ 弹「等级加速」说明弹窗 →
        主面板 → 右上角关闭 → 菜单页(既有分支接管)。本分支逐帧重识别,
        多跳中间态天然容忍;round_retry 有界,点击不落地时 FAIL 不永动。
        """
        counters: dict[str, int] = {'fallback_click': 0}
        find_clicks: list[tuple[str, str]] = []

        def _fake_find_area(self, screen, screen_name, area_name, *args, **kwargs):
            if screen_name == '无名勋礼-购买推广页' and area_name == '按钮-开启无名勋礼':
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        def _fake_find_and_click(self, screen, screen_name, area_name, *args, **kwargs):
            if screen_name == '无名勋礼-购买推广页' and area_name == '按钮-开启无名勋礼':
                find_clicks.append((screen_name, area_name))
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        def _fake_click_area(self, screen_name, area_name, *args, **kwargs):
            counters['fallback_click'] += 1
            return self.round_success(status=area_name)

        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_and_click
        )
        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _fake_click_area)
        monkeypatch.setattr(
            btnw_module.sim_uni_screen_state,
            'get_sim_uni_screen_state',
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state,
            'is_express_supply',
            lambda *args, **kw: False,
        )
        # 守卫被触达即回归(会与推广页分支抢路径/误点对话隐藏按钮)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'check_npc_dialog',
            lambda self, screen: (_ for _ in ()).throw(
                AssertionError('推广页应被专属分支接管,不应进入对话态守卫')),
        )

        op = _WatchedBackToNormal(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        sleeps = _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 画面不变时 round_retry 有界:耗尽 20 次 retry 后 FAIL 而非 WAIT 永动。
        assert not result.success, f'画面不变时应有界 FAIL,status={result.status}'
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert 20 <= rounds <= 25, f'轮次异常({rounds}),应耗满 20 次 retry 才 FAIL'
        assert len(sleeps) >= rounds, f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        # 每轮点的都是推广页「按钮-开启无名勋礼」area;兜底右上角返回不得被触达。
        assert len(find_clicks) == rounds and counters['fallback_click'] == 0, (
            f'area 点击数({len(find_clicks)})应==轮次,兜底({counters["fallback_click"]})应为 0'
        )
        assert all(
            sn == '无名勋礼-购买推广页' and an == '按钮-开启无名勋礼'
            for sn, an in find_clicks
        ), f'点击 area 漂移:{find_clicks[:3]}'

    @pytest.mark.parametrize(
        'screen_name, mark_area, click_area',
        [
            ('无名勋礼-等级加速弹窗', '标识-等级加速', '按钮-点击空白处关闭'),
            ('无名勋礼', '标识-无名勋礼', '按钮-关闭'),
        ],
        ids=['levelup-popup', 'main-panel'],
    )
    def test_nameless_honor_intermediate_branches(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        screen_name: str,
        mark_area: str,
        click_area: str,
    ) -> None:
        """退出链中间态:弹窗帧点「点击空白处关闭」、主面板帧点「按钮-关闭」。

        推广页分支(上一测)不命中时逐帧重识别落到这两支:每支都是「id_mark 命中
        → area 点击 → round_retry」,多跳中间态靠逐帧重识别容忍。每支独立锁死
        点击 area,防分支间串扰或落兜底。
        """
        find_clicks: list[tuple[str, str]] = []

        def _fake_find_area(self, screen, s_name, area_name, *args, **kwargs):
            if s_name == screen_name and area_name == mark_area:
                return self.round_success(status=f'{s_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        def _fake_find_and_click(self, screen, s_name, area_name, *args, **kwargs):
            if s_name == screen_name and area_name == click_area:
                find_clicks.append((s_name, area_name))
                return self.round_success(status=f'{s_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_and_click
        )
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_click_area',
            lambda self, s_name, area_name, *a, **kw: self.round_success(status=area_name),
        )
        monkeypatch.setattr(
            btnw_module.sim_uni_screen_state,
            'get_sim_uni_screen_state',
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state,
            'is_express_supply',
            lambda *args, **kw: False,
        )
        monkeypatch.setattr(BackToNormalWorldPlus, 'check_npc_dialog', lambda self, s: None)

        op = _WatchedBackToNormal(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 帧恒停在中间态时应有界 FAIL(retry 语义),且每轮点的都是该态专属 area。
        assert not result.success
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert 20 <= rounds <= 25
        assert len(find_clicks) == rounds, (
            f'{screen_name}: area 点击数({len(find_clicks)})应==轮次({rounds})'
        )
        assert all(sn == screen_name and an == click_area for sn, an in find_clicks)


class TestVersionAnnouncementBranches:
    """版本公告轮播分支:第 1 页翻页 / 第 2 页关闭,真帧输入。

    背景:游戏级版本公告弹窗(「贪饕」侵蚀,2026-08-26 版本)待机自动弹出、
    盖在任意画面上;第 1 页无出口只有右箭头翻页,第 2 页底部中央出「关闭」钮
    (2026-08-27 实机实证;无此分支时 CW 独立 app 首跑 52s 失败)。
    分支结构(与上方大厅/无名勋礼分支同构):标题 id_mark(两页共享)正面识别 → 「按钮-关闭」
    可见与否区分子态 → area 点击 → round_retry 逐帧重识别。

    与上方 mock 分支测试不同,本类**不 mock 画面识别**(round_by_find_area 走
    session 级真 OCR / 真命中),只对点击层做记录——fixture 用测试仓归档的
    真实公告帧(贪饕侵蚀-第1页/第2页.webp),锁「真帧 → 分支路由 + 点击 area」
    全链,识别漂移(锚点失配 / 误吸他分支)会在此红。
    """

    SCREEN = '版本公告轮播'

    def _run_check_screen(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        state: str,
    ) -> tuple[OperationRoundResult, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
        return _run_real_frame_check_screen(
            test_context, monkeypatch, self.SCREEN, state,
        )

    def test_page1_flips_to_next(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """页 1 真帧:标题 id_mark 命中、无「关闭」→ 点右箭头翻页 area,不点关闭。"""
        result, finds, find_clicks, bare_clicks = self._run_check_screen(
            test_context, monkeypatch, '贪饕侵蚀-第1页',
        )

        # 分支路由:round_retry 等下一轮逐帧重识别(非 success / 兜底)
        assert not result.is_success, f'页 1 应 round_retry,status={result.status}'
        assert result.status == '版本公告轮播'
        # 识别事实(真 OCR):标题命中、关闭钮缺席(页 1 子态判据)
        assert (self.SCREEN, '标识-贪饕侵蚀') in finds
        assert (self.SCREEN, '按钮-关闭') not in finds
        # 动作:只裸点右箭头翻页 area;不得点「关闭」
        assert bare_clicks == [(self.SCREEN, '按钮-下一页')], f'裸点击漂移:{bare_clicks}'
        assert find_clicks == [], f'页 1 不应有 find+click:{find_clicks}'

    def test_page2_closes(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """页 2 真帧:「关闭」钮可见 → find+click 关闭 area,不再翻页。"""
        result, finds, find_clicks, bare_clicks = self._run_check_screen(
            test_context, monkeypatch, '贪饕侵蚀-第2页',
        )

        assert not result.is_success, f'页 2 应 round_retry,status={result.status}'
        assert result.status == '版本公告轮播'
        assert (self.SCREEN, '标识-贪饕侵蚀') in finds
        assert (self.SCREEN, '按钮-关闭') in finds
        assert find_clicks == [(self.SCREEN, '按钮-关闭')], (
            f'关闭点击漂移:{find_clicks}'
        )
        assert bare_clicks == [], f'页 2 不应再翻页:{bare_clicks}'


def _run_real_frame_check_screen(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
    screen_name: str,
    state: str,
) -> tuple[OperationRoundResult, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    """真帧驱动单轮 check_screen,返回 (结果, find记录, find+click记录, 裸click记录)。

    - ``op.last_screenshot`` 直接注入归档真帧(不经截图链路);
    - 三类 round_by_* 均为**包装真实方法**(识别照跑,只加记录);
    - 模拟宇宙状态 / 列车补给 / 对话守卫恒无(与本测试无关,防噪音)。
    """
    img = test_context.load_screen(screen_name, state)
    finds: list[tuple[str, str]] = []
    find_clicks: list[tuple[str, str]] = []
    bare_clicks: list[tuple[str, str]] = []

    real_find = BackToNormalWorldPlus.round_by_find_area
    real_find_click = BackToNormalWorldPlus.round_by_find_and_click_area
    real_click = BackToNormalWorldPlus.round_by_click_area

    def _spy_find(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            finds.append((s_name, a_name))
        return r

    def _spy_find_click(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find_click(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            find_clicks.append((s_name, a_name))
        return r

    def _spy_click(self, s_name: str, a_name: str, *a, **k):
        r = real_click(self, s_name, a_name, *a, **k)
        bare_clicks.append((s_name, a_name))
        return r

    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _spy_find)
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'round_by_find_and_click_area', _spy_find_click,
    )
    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _spy_click)
    monkeypatch.setattr(
        btnw_module.sim_uni_screen_state,
        'get_sim_uni_screen_state',
        lambda *args, **kw: None,
    )
    monkeypatch.setattr(
        btnw_module.common_screen_state,
        'is_express_supply',
        lambda *args, **kw: False,
    )
    monkeypatch.setattr(BackToNormalWorldPlus, 'check_npc_dialog', lambda self, s: None)

    op = _WatchedBackToNormal(test_context)
    op.last_screenshot = img  # 真帧注入:check_screen 每轮读它做识别
    monkeypatch.setattr(op, 'screenshot', lambda: img)

    enter_running_state(test_context)
    try:
        result = op.check_screen()
    finally:
        reset_running_state(test_context, op)
    return result, finds, find_clicks, bare_clicks


class TestCwLobbyResidualBranch:
    """CW 大厅残留态分支真帧输入锁:上局结束「回大厅」的死按钮残留态。

    背景(2026-08-27 run49 首跑 147s 失败根因,编排者 live 实证):上局结束
    「回大厅」后的大厅 UI 层是残留态——开始按钮不响应任何点击(app 重试循环
    与手动双击均无效),右上角「按钮-关闭」才是真退出(关 X 露出世界场景后
    世界入口接管一切正常)。该残留态与开局前大厅共用同一 screen_info 档
    (货币战争-大厅,创业指南 id_mark 锚 + 按钮-关闭 template),由既有
    大厅分支接管:标识命中 → find+click「按钮-关闭」→ round_retry
    逐帧重识别露世界 → 「角色图标」分支 SUCCESS。

    真帧锁:fixture = run49 真实失败帧(死按钮大厅态,含创业指南+开始钮+
    右上关闭钮,测试仓归档 ``大厅-残留态-run49.webp``)。不 mock 画面识别,
    锁「真帧 → 分支路由 + 点击 area」全链:锚点失配 / 模板漂移 / 误吸
    别分支(尤其对话守卫与兜底)会在此红。
    """

    SCREEN = '货币战争-大厅'
    STATE = '大厅-残留态-run49'

    def test_residual_lobby_closes(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run49 残留态真帧:命中大厅分支,find+click「按钮-关闭」,round_retry。"""
        result, finds, find_clicks, bare_clicks = _run_real_frame_check_screen(
            test_context, monkeypatch, self.SCREEN, self.STATE,
        )

        # 分支路由:round_retry 等下一轮逐帧重识别露世界(非 success / 兜底)
        assert not result.is_success, f'残留态应 round_retry,status={result.status}'
        assert result.status == self.SCREEN
        # 识别事实(真 OCR):创业指南 id_mark 锚命中(分支入口判据)。
        # 「按钮-关闭」是 template area,本分支仅经 round_by_find_and_click_area
        # 消费(记入 find_clicks,不入 finds)——命中与否由下方点击断言锁死。
        assert (self.SCREEN, '标识-创业指南') in finds, f'识别命中:{finds}'
        # 动作:只 find+click 关闭 area;不点开始钮、不落兜底裸点击
        assert find_clicks == [(self.SCREEN, '按钮-关闭')], (
            f'关闭点击漂移:{find_clicks}'
        )
        assert bare_clicks == [], f'不应有兜底/翻页类裸点击:{bare_clicks}'


class TestBattleFailScreenBranch:
    """大世界-战斗失败分支真帧输入锁:app 异常退出遗留的战败结算屏。

    背景(2026-08-30 实证,开拓力 FAIL 遗留现场):战败结算屏无右上角返回按钮,
    唯一交互是「点击空白区域继续」;起手兜底只会反复点右上角死循环至 FAIL,
    卡死下一个应用。分支 = id_mark「标题-战斗失败」正面识别 → find+click
    「点击空白区域继续」→ round_retry 逐帧重识别(点空白落到各副本战前画面,
    由既有分支/兜底继续)。

    真帧锁:fixture = 饰品提取战败真帧(标题-战斗失败 + 点击空白区域继续,
    conf 0.995+,见 docs/game/screens/大世界-战斗失败.md)。不 mock 画面识别,
    真 OCR/模板识别照跑——识别漂移时测试红,直接暴露建档漂移。
    """

    SCREEN = '大世界-战斗失败'
    STATE = '战斗失败'

    def test_battle_fail_clicks_blank(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """战败屏真帧:命中战败分支,find+click「点击空白区域继续」,round_retry。"""
        result, finds, find_clicks, bare_clicks = _run_real_frame_check_screen(
            test_context, monkeypatch, self.SCREEN, self.STATE,
        )

        # 分支路由:round_retry 等下一轮逐帧重识别(点空白落到战前画面)
        assert not result.is_success, f'战败屏应 round_retry,status={result.status}'
        assert result.status == self.SCREEN
        # 识别事实(真 OCR):标题 id_mark 锚命中(分支入口判据)
        assert (self.SCREEN, '标题-战斗失败') in finds, f'识别命中:{finds}'
        # 动作:只 find+click 点空白继续;不落兜底裸点击
        assert find_clicks == [(self.SCREEN, '点击空白区域继续')], (
            f'点击漂移:{find_clicks}'
        )
        assert bare_clicks == [], f'不应有兜底裸点击:{bare_clicks}'


class TestSimUniExitConfirmBranch:
    """模拟宇宙退出确认面板分支真帧输入锁。

    背景(2026-08-31 实证):上一 app 在模拟宇宙楼层内异常退出,本 op 起手点
    「右上角返回」→ 弹出「退出模拟宇宙?」确认面板 → 只认识右上角 X →
    关面板又见楼层退出按钮 → 无限循环 40 分钟。面板 area 早已建档
    (sim_uni.yml 菜单-暂离),纯分发表缺条目。

    真帧锁:fixture = 开拓力 FAIL 遗留现场真帧(暂离/结束并结算面板全开)。
    不 mock 画面识别,真 OCR 照跑。
    """

    SCREEN = '模拟宇宙'
    STATE = '退出模拟宇宙确认面板'

    def test_exit_confirm_clicks_leave(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """面板真帧:命中暂离,find+click「菜单-暂离」,round_retry。"""
        result, finds, find_clicks, bare_clicks = _run_real_frame_check_screen(
            test_context, monkeypatch, self.SCREEN, self.STATE,
        )

        assert not result.is_success, f'面板应 round_retry,status={result.status}'
        assert result.status == '模拟宇宙-退出确认面板'
        assert (self.SCREEN, '菜单-暂离') in finds, f'识别命中:{finds}'
        assert find_clicks == [(self.SCREEN, '菜单-暂离')], (
            f'点击漂移:{find_clicks}'
        )
        assert bare_clicks == [], f'不应有兜底裸点击:{bare_clicks}'


def _patch_round_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """打桩框架轮间 sleep 并记录调用,提速测试(20 轮 × 1s 真睡太慢)+ 断言 wait 生效。

    ``_after_round_wait`` 用模块级 ``time.sleep``(operation.py),monkeypatch 全局
    打桩测试结束自动还原,不影响 session 级 ``test_context``。
    """
    sleeps: list[float] = []
    monkeypatch.setattr('time.sleep', lambda s: sleeps.append(s))
    return sleeps


class _FakeMatchList:
    """够用的 MatchResultList 假件:只有 ``max``(守卫只消费 ``r.max.center``)。"""

    def __init__(self, x: int, y: int, w: int = 60, h: int = 30) -> None:
        self.max = MatchResult(1, x, y, w, h)


class TestNpcDialogGuard:
    """对话态守卫(check_npc_dialog)单元测试。

    背景(2026-08-26 实机事故):登录落点=活动摊位 NPC 对话态,对话 UI 遮蔽右上角
    图标,check_screen 所有既有分支不命中,兜底点「菜单-右上角返回」与对话的
    隐藏按钮重叠 → 一点把对话 UI 收掉 → 裸场景假象 + 键盘输入被吞。

    守卫语义(加严后,逐帧反应式):

    - 告别类选项命中 → 点选项退出对话(WAIT,同帧不落兜底);
    - 交互区无告别词(含只有未知文字)→ None,落回原兜底——「区域有字」是弱证据,
      不再单独构成对话态(2026-08-27 run 46:CW 大厅面板文字曾被误判成未知对话
      选项 → 点空白推进 → retry 永动;CW 大厅改由 check_screen 专属分支接管)。
    """

    BLANK = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def _make_op(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> tuple[_WatchedBackToNormal, list[Point], list[Point]]:
        """构造 op + 记录 mouse_move/click 序列;禁用守卫的采集截图钩子(不写 .debug)。"""
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'save_screenshot', lambda self, *a, **kw: None,
        )
        op = _WatchedBackToNormal(test_context)
        moves: list[Point] = []
        clicks: list = []

        def _record_move(pos, *args, **kwargs):
            moves.append(pos)
            return True

        def _record_click(pos=None, *args, **kwargs):
            clicks.append(pos)
            return True

        # MockController 无 mouse_move 属性(生产 controller 才有),raising=False 补桩
        monkeypatch.setattr(
            op.ctx.controller, 'mouse_move', _record_move, raising=False,
        )
        monkeypatch.setattr(
            op.ctx.controller, 'click', _record_click, raising=False,
        )
        return op, moves, clicks

    def test_farewell_clicked(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """告别选项命中:点选项中心(裁剪区坐标 + 交互区左上偏移),WAIT 不落兜底。"""
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        # 选项命中在交互区内相对坐标 (100, 80) → 绝对坐标 = +INTERACT_RECT.left_top
        monkeypatch.setattr(
            test_context.ocr, 'match_words',
            lambda image, words, **kw: {'告别': _FakeMatchList(100, 80)},
        )

        result = op.check_npc_dialog(self.BLANK)

        assert result is not None
        assert result.is_success is False  # round_wait 非成功、也非兜底点击
        assert '对话态-告别' in (result.status or '')
        # 与 TalkInteract 同款:先 mouse_move 停留再 click(pc_alt 语义在真机,测试只锁坐标)
        # 期望坐标 = 命中框中心(MatchResult(100,80,60,30) → (130,95)) + 交互区左上偏移
        assert len(moves) == 1
        assert int(moves[0].x) == 130 + TalkInteract.INTERACT_RECT.left_top.x
        assert int(moves[0].y) == 95 + TalkInteract.INTERACT_RECT.left_top.y
        # click 不带坐标(选项位置已由 mouse_move 定位),且只点了一次
        assert len(clicks) == 1 and clicks[0] is None

    def test_unknown_options_no_blind_click(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """只有未知文字、无告别词:不构成对话态证据 → None 落回兜底,零动作。

        加严(2026-08-27 run 46 实证):旧版把交互区未知文字当「未知对话
        选项」点空白推进 + RETRY——选项态下空白推进无效,形成 retry 永动,且
        空白点击落在任意未知画面上有误触风险。
        """
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        monkeypatch.setattr(
            test_context.ocr, 'match_words', lambda image, words, **kw: {},
        )
        monkeypatch.setattr(
            test_context.ocr, 'run_ocr',
            lambda image, *a, **kw: {'今天有什么好货': _FakeMatchList(50, 50)},
        )

        result = op.check_npc_dialog(self.BLANK)

        assert result is None, (
            f'未知文字不应构成对话态证据,status={getattr(result, "status", None)}'
        )
        assert clicks == [] and moves == [], '守卫不触发时不允许任何点击/移动'

    def test_no_dialog_returns_none(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """交互区无任何文字:守卫不触发返回 None,落回原兜底(修复前行为保留)。"""
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        monkeypatch.setattr(
            test_context.ocr, 'match_words', lambda image, words, **kw: {},
        )
        monkeypatch.setattr(
            test_context.ocr, 'run_ocr', lambda image, *a, **kw: {},
        )

        assert op.check_npc_dialog(self.BLANK) is None
        assert clicks == [] and moves == []

    def test_farewell_priority_over_unknown(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """告别词与未知选项同屏:优先告别(不进未知选项分支)。"""
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        monkeypatch.setattr(
            test_context.ocr, 'match_words',
            lambda image, words, **kw: {'告别': _FakeMatchList(100, 80)},
        )
        # run_ocr 若被触达说明走了未知选项分支 —— 让它显式炸出来
        def _boom(*args, **kwargs):
            raise AssertionError('告别命中时不应再走 run_ocr 未知选项分支')

        monkeypatch.setattr(test_context.ocr, 'run_ocr', _boom)

        result = op.check_npc_dialog(self.BLANK)
        assert result is not None
        assert '对话态-告别' in (result.status or '')

    def test_cw_lobby_panel_text_not_dialog(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """场景锁死:货币战争-大厅帧命中 check_screen 专属分支,不进对话态守卫。

        背景(2026-08-27 run 46 实机):大厅前序分支全不命中,守卫对 INTERACT_RECT
        OCR 把右侧面板文字(『数据银行』『预期收益』『√奖励已全领取』『83%』『75/91』)
        误判为未知对话选项 → 点空白推进 → retry 永动 → 一条龙重启再陷。
        修复=check_screen 补大厅分支(id_mark 命中 → 点右上角 X,round_retry 有界)。
        """
        counters: dict[str, int] = {'fallback_click': 0, 'x_click': 0}

        def _fake_find_area(self, screen, screen_name, area_name, *args, **kwargs):
            if screen_name == '货币战争-大厅' and area_name == '标识-创业指南':
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        def _fake_click_area(self, screen_name, area_name, *args, **kwargs):
            counters['fallback_click'] += 1
            return self.round_success(status=area_name)

        # 大厅关闭按钮的 area 点击(实机验证过的「按钮-关闭」,点 X 回大世界);
        # 其余 find_and_click 一律未命中(逐光捡金/战斗退出等分支不得误吸)。
        area_clicks: list[tuple[str, str]] = []

        def _fake_find_and_click(self, screen, screen_name, area_name, *args, **kwargs):
            if screen_name == '货币战争-大厅' and area_name == '按钮-关闭':
                area_clicks.append((screen_name, area_name))
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_and_click
        )
        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _fake_click_area)
        monkeypatch.setattr(
            btnw_module.sim_uni_screen_state,
            'get_sim_uni_screen_state',
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state,
            'is_express_supply',
            lambda *args, **kw: False,
        )
        # 守卫被触达即回归(run 46 死循环路径)——显式炸出来
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'check_npc_dialog',
            lambda self, screen: (_ for _ in ()).throw(
                AssertionError('CW 大厅应被专属分支接管,不应进入对话态守卫')),
        )

        op = _WatchedBackToNormal(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        sleeps = _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 分支每轮走「按钮-关闭」area 点击(实机验证的退出手势,点 X 回大世界),
        # round_retry 有界:耗尽 20 次 retry 后 FAIL,而非守卫时代的 retry 永动。
        assert not result.success, f'画面不变时应有界 FAIL,status={result.status}'
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert 20 <= rounds <= 25, f'轮次异常({rounds}),应耗满 20 次 retry 才 FAIL'
        assert len(sleeps) >= rounds, f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        # 每轮点的都是大厅「按钮-关闭」area(而非守卫的空白推进位/兜底的右上角返回 area)
        assert len(area_clicks) == rounds and counters['fallback_click'] == 0, (
            f'area 点击数({len(area_clicks)})应==轮次,兜底({counters["fallback_click"]})应为 0'
        )
        assert all(sn == '货币战争-大厅' and an == '按钮-关闭' for sn, an in area_clicks), (
            f'点击 area 漂移:{area_clicks[:3]}'
        )
