"""BackToNormalWorldPlus.check_screen 测试——mock 分发锁:画面识别全桩,只锁「帧态 → 命中锚 →
点击动作」路由事实与有界 retry 语义。真帧输入锁在同目录 test_check_screen_real_frame.py,
对话态守卫(check_npc_dialog)在 test_check_npc_dialog.py;三文件共用装置在 harness.py。

BackToNormalWorldPlus 兜底分支防死循环测试。

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

from types import SimpleNamespace

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.operations.back_to_normal_world_plus.harness import _WatchedBackToNormal

import sr_od.operations.back_to_normal_world_plus as btnw_module
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus


@pytest.fixture()
def stuck_op(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_WatchedBackToNormal, dict[str, int], list[bool]]:
    """构造「兜底点击无法改变画面」的假环境,返回 (op, 计数字典, pc_alt 记录)。

    - find 类识别(``round_by_find_area`` / ``round_by_find_and_click_area``)恒返回
      未命中(结果仅被 ``is_success`` 检查后丢弃,用 WAIT 构造即可);
    - 兜底点击 = controller.click 直点(锁光标恢复态加固后兜底不再走
      ``round_by_click_area``),记录每次点击并恒成功(模拟点击发出去了
      但画面不变——正是事故现场的语义);
    - 模拟宇宙状态 / 列车补给恒无。
    """
    counters: dict[str, int] = {'fallback_click': 0}
    click_alts: list[bool] = []

    def _fake_find_area(self, screen, screen_name, area_name, *args, **kwargs):
        return self.round_wait(status=f'未找到 {area_name}')

    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_area
    )
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
    # CW 对局中画面判定:真实实现走 session 级真 OCR 画面匹配(对空白 mock 帧
    # 既慢又不定),恒 None=判定失败退兜底,保既有「必落兜底」构造语义不变。
    monkeypatch.setattr(
        btnw_module.cw_screen_state,
        'get_in_match_screen_name',
        lambda *args, **kwargs: None,
    )
    # CW 挂起入口两屏屏级点名:真实实现走真 OCR 画面匹配,恒 None=判定不
    # 命中,保既有「必落兜底」构造语义不变(命中路径由挂起分支测试单独锁)。
    monkeypatch.setattr(
        btnw_module,
        'get_match_screen_name',
        lambda *args, **kwargs: None,
    )
    # 对话态守卫走真实 ctx.ocr(session 级真模型,对空白 mock 帧推理既慢又不定)
    # → 恒「无对话」:守卫返回 None,每轮照旧落兜底(本测试的构造语义不变)。
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'check_npc_dialog', lambda self, screen: None,
    )

    op = _WatchedBackToNormal(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    def _record_click(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
        counters['fallback_click'] += 1
        click_alts.append(bool(pc_alt))
        return True

    monkeypatch.setattr(op.ctx.controller, 'click', _record_click, raising=False)
    return op, counters, click_alts


class TestBackToNormalWorldPlusFallback:

    @pytest.mark.parametrize('click_fails', [False, True], ids=['click-no-effect', 'click-fails'])
    def test_stuck_fallback_fails_bounded(
        self,
        test_context: SrTestContext,
        stuck_op: tuple[_WatchedBackToNormal, dict[str, int], list[bool]],
        monkeypatch: pytest.MonkeyPatch,
        click_fails: bool,
    ) -> None:
        """兜底点击无法改变画面 / 点击本身失败:op 应 FAIL 且轮次有界(修复前永远 WAIT)。

        2026-08-24 实锤:两小时 WAIT 循环,结尾是点击失败后转入无 wait 的异常
        风暴(每 ~24ms 一轮刷屏)。修复后兜底计入 retry,每轮 retry 带 wait=1,
        耗尽 node_max_retry_times=20 后节点 FAIL。
        """
        op, counters, click_alts = stuck_op
        sleeps = _patch_round_sleep(monkeypatch)
        if click_fails:
            def _fake_click_fail(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
                counters['fallback_click'] += 1
                return False

            monkeypatch.setattr(op.ctx.controller, 'click', _fake_click_fail, raising=False)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert not result.success, (
            f'兜底卡死场景不应 success:status={result.status}'
        )
        # 轮次有界:看门狗(50)未触发,总轮次 ≈ 20 次 retry + 1 次 FAIL 判定。
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert rounds <= 25, f'轮次超界({rounds}),疑似死循环未修复'
        assert rounds >= 20, f'轮次异常偏少({rounds}),应耗满 20 次 retry 才 FAIL'
        if not click_fails:
            # 每轮兜底都真实点击了右上角(点击发出但画面不变)。
            assert counters['fallback_click'] == rounds, (
                f'兜底点击数({counters["fallback_click"]}) != 轮次({rounds})'
            )
            # 锁光标恢复态加固锁:兜底每次点击都带 pc_alt=True(2026-09-02 恢复链
            # 事故根修——锁光标下不带 Alt 的点击全部落空,兜底是最后出口必须按
            # 最坏光标态点)。
            assert len(click_alts) == rounds and all(click_alts), (
                f'兜底点击未全部带 pc_alt=True:{click_alts}'
            )
        # 每轮 retry 都带 wait=1(防回归为无 wait 的异常风暴式快速重试)。
        assert len(sleeps) >= rounds, (
            f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        )


class TestNamelessHonorBranches:
    """无名勋礼退出链分支:推广页 / 等级加速弹窗 / 主面板(mock 分发锁)。

    背景:2026-08-26 版本周期首进无名勋礼先落购买推广页(点「开启无名勋礼」
    不会付费,用户裁决),实证退出链(实机四步全走通):推广页 → 开启 → 等级
    加速弹窗(点提示位关闭)→ 主面板 → 右上角关闭 → 菜单页。三支均
    「id_mark 命中 → area 点击 → round_retry 逐帧重识别」;点击可能不落地,
    RETRY 计入 node_max_retry_times=20 有界 FAIL。画面识别层由 test_id_mark
    集中锁定,此处只锁分发(命中专属 area + 不落兜底 + 不触守卫 + 有界)。
    """

    @pytest.mark.parametrize(
        'screen_name, mark_area, click_area',
        [
            ('无名勋礼-购买推广页', '按钮-开启无名勋礼', '按钮-开启无名勋礼'),
            ('无名勋礼-等级加速弹窗', '标识-等级加速', '按钮-点击空白处关闭'),
            ('无名勋礼', '标识-无名勋礼', '按钮-关闭'),
        ],
        ids=['promo', 'levelup-popup', 'main-panel'],
    )
    def test_nameless_honor_branches(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        screen_name: str,
        mark_area: str,
        click_area: str,
    ) -> None:
        """该态帧命中专属分支:只 find+click 本态 area,有界 FAIL 不落兜底不触守卫。"""
        counters: dict[str, int] = {'fallback_click': 0}
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

        def _fake_click_area(self, s_name, area_name, *args, **kwargs):
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
        # CW 挂起入口两屏屏级点名恒 None(真实实现走真 OCR 画面匹配,
        # 对 mock 帧既慢又不定;命中路径由挂起分支测试单独锁)。
        monkeypatch.setattr(
            btnw_module,
            'get_match_screen_name',
            lambda *args, **kw: None,
        )
        # 守卫被触达即回归(守卫位于所有具名分支之后;触达 = 分发串扰/分支缺失)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'check_npc_dialog',
            lambda self, screen: (_ for _ in ()).throw(
                AssertionError('该画面应被专属分支接管,不应进入对话态守卫')),
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
        # 每轮点的都是本态专属 area;兜底右上角返回不得被触达。
        assert len(find_clicks) == rounds and counters['fallback_click'] == 0, (
            f'area 点击数({len(find_clicks)})应==轮次,兜底({counters["fallback_click"]})应为 0'
        )
        assert all(
            sn == screen_name and an == click_area
            for sn, an in find_clicks
        ), f'点击 area 漂移:{find_clicks[:3]}'


class TestBranchRoutingMock:
    """退出链其余分支的分发锁(mock 识别,零识别成本)。

    真帧测试保留两处代表覆盖两类动作区风险(战斗失败=OCR 文本动作区、
    CW 大厅=模板动作区+pc_alt 直点);画面识别层由 test_id_mark 集中锁定。
    本类锁其余分支的「帧态 → 命中锚 → 点击动作」路由事实:

    - 退出确认面板(2026-08-31 实证 40 分钟循环):命中「菜单-暂离」→ find+click;
    - 版本公告轮播(2026-08-26 版本,无分支时兜底空转):标题命中后按
      「按钮-关闭」可见与否区分子态——可见 find+click 关闭,缺席裸点右箭头翻页。
    """

    @pytest.mark.parametrize(
        'hit_finds, hit_clicks, expect_status, expect_find_clicks, expect_bare',
        [
            # 退出确认面板:识别标志命中 → 点「菜单-暂离」→ round_retry
            (
                {('模拟宇宙', '菜单-暂离')},
                {('模拟宇宙', '菜单-暂离')},
                '模拟宇宙-退出确认面板',
                [('模拟宇宙', '菜单-暂离')],
                [],
            ),
            # 公告页 1:标题命中、「关闭」缺席 → 只裸点右箭头翻页
            (
                {('版本公告轮播', '标识-贪饕侵蚀')},
                set(),
                '版本公告轮播',
                [],
                [('版本公告轮播', '按钮-下一页')],
            ),
            # 公告页 2:「关闭」可见 → find+click 关闭,不再翻页
            (
                {('版本公告轮播', '标识-贪饕侵蚀'), ('版本公告轮播', '按钮-关闭')},
                {('版本公告轮播', '按钮-关闭')},
                '版本公告轮播',
                [('版本公告轮播', '按钮-关闭')],
                [],
            ),
        ],
        ids=['sim-uni-exit-confirm', 'announcement-page1-flip', 'announcement-page2-close'],
    )
    def test_branch_routing(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
        hit_finds: set[tuple[str, str]],
        hit_clicks: set[tuple[str, str]],
        expect_status: str,
        expect_find_clicks: list[tuple[str, str]],
        expect_bare: list[tuple[str, str]],
    ) -> None:
        """给定命中集,check_screen 单轮路由到本分支并做且只做预期动作。"""
        find_clicks: list[tuple[str, str]] = []
        bare_clicks: list[tuple[str, str]] = []

        def _fake_find_area(self, screen, s_name, a_name, *a, **kw):
            if (s_name, a_name) in hit_finds:
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_find_and_click(self, screen, s_name, a_name, *a, **kw):
            if (s_name, a_name) in hit_clicks:
                find_clicks.append((s_name, a_name))
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')

        def _fake_click_area(self, s_name, a_name, *a, **kw):
            bare_clicks.append((s_name, a_name))
            return self.round_success(status=a_name)

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
        monkeypatch.setattr(
            btnw_module.cw_screen_state,
            'get_in_match_screen_name',
            lambda *args, **kw: None,
        )
        # CW 挂起入口两屏屏级点名恒 None(真实实现走真 OCR 画面匹配,
        # 对 mock 帧既慢又不定;命中路径由挂起分支测试单独锁)。
        monkeypatch.setattr(
            btnw_module,
            'get_match_screen_name',
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(BackToNormalWorldPlus, 'check_npc_dialog', lambda self, s: None)

        op = _WatchedBackToNormal(test_context)
        op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # 命中分支的 round_retry(wait=1~2) 会真睡,直调 check_screen 也包 fast_sleep
        with fast_sleep():
            result = op.check_screen()

        # 分支路由:round_retry 等下一轮逐帧重识别(非 success / 兜底)
        assert not result.is_success, f'应 round_retry,status={result.status}'
        assert result.status == expect_status, f'分支状态漂移:{result.status}'
        assert find_clicks == expect_find_clicks, f'find+click 漂移:{find_clicks}'
        assert bare_clicks == expect_bare, f'裸点击漂移:{bare_clicks}'


def _patch_round_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """打桩框架轮间 sleep 并记录调用,提速测试(20 轮 × 1s 真睡太慢)+ 断言 wait 生效。

    ``_after_round_wait`` 用模块级 ``time.sleep``(operation.py),monkeypatch 全局
    打桩测试结束自动还原,不影响 session 级 ``test_context``。
    """
    sleeps: list[float] = []
    monkeypatch.setattr('time.sleep', lambda s: sleeps.append(s))
    return sleeps


class _RecordingFakeCwExit:
    """记录构造/执行的 CwEntryExit 假类(不触真实 op 节点图)。

    ``fail_after`` 之前每次 ``execute`` 返回成功(=已回大厅),之后返回失败
    (模拟对局画面点不动)——让「成功一轮 round_wait + 失败重试有界」两条
    路径都能在画面不变的 mock 环境里走到。
    """

    constructed: int = 0
    executed: int = 0
    fail_after: int = 0

    def __init__(self, ctx) -> None:
        type(self).constructed += 1

    def execute(self):
        # 真 Operation.execute() 返回 OperationResult(.success),非 round 结果;
        # 假类只承诺 cw_exit 消费的 .success 契约。
        type(self).executed += 1
        ok = type(self).executed <= type(self).fail_after
        return SimpleNamespace(success=ok, status='已返回货币战争大厅' if ok else '退出失败')


class TestCwInMatchDelegationBranch:
    """CW 对局中画面 → 委托 CwEntryExit 分支锁(2026-09-01 孤儿对局事故)。

    背景:上一 CW app 被 stop 后残留对局画面(如备战),本 op 既有分支全不
    认识 → 落兜底点「菜单-右上角返回」(CW 画面无此控件)→ 9 个一条龙应用
    逐一 round_retry×20 速挂。修复:判定单一源 = cw_screen_state(与
    CurrencyWarApp._in_match 第①层同源)命中即委托退出对局 op;成功回大厅
    后下一轮由「货币战争-大厅」分支(点右上角关闭 X)接管。
    """

    def test_in_match_screen_delegates_to_cw_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """判定命中:每轮委托假类并 execute;零兜底点击;守卫不被触达。"""
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
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state,
            'is_express_supply',
            lambda *args, **kw: False,
        )
        # 判定桩:恒命中备战画面(真实画面匹配层由 cw 侧测试单独锁定)。
        monkeypatch.setattr(
            btnw_module.cw_screen_state,
            'get_in_match_screen_name',
            lambda *args, **kw: '货币战争-备战',
        )
        # CW 挂起入口两屏屏级点名恒 None(与被测对局中委托分支互斥;
        # 命中路径由挂起分支测试单独锁)。
        monkeypatch.setattr(
            btnw_module,
            'get_match_screen_name',
            lambda *args, **kw: None,
        )
        fake = _RecordingFakeCwExit
        fake.constructed = 0
        fake.executed = 0
        fake.fail_after = 1  # 首轮成功(WAIT 路径),之后失败(RETRY 有界路径)
        monkeypatch.setattr(btnw_module, 'CwEntryExit', fake)
        # 守卫被触达即回归(兜底路径被对话隐藏按钮误触的事故形状)。
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'check_npc_dialog',
            lambda self, screen: (_ for _ in ()).throw(
                AssertionError('对局中画面应被 cw 退出分支接管,不应进入对话态守卫')),
        )

        op = _WatchedBackToNormal(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        sleeps = _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 委托发生:每轮都构造并 execute 了退出对局假类(成功 1 轮 + 失败重试轮)。
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert fake.constructed == rounds and fake.executed == rounds, (
            f'委托数(构造 {fake.constructed}/执行 {fake.executed})应==轮次({rounds})'
        )
        # 兜底零点击:右上角返回控件在 CW 画面不存在,一次都不许点。
        assert counters['fallback_click'] == 0, (
            f'兜底被触达 {counters["fallback_click"]} 次,应恒 0'
        )
        # 有界结束:耗尽 20 次 retry 后 FAIL,而非 WAIT 永动。
        assert not result.success, f'画面不变时应有界 FAIL,status={result.status}'
        assert 20 <= rounds <= 25, f'轮次异常({rounds}),应耗满 20 次 retry 才 FAIL'
        # 每轮 round_wait / round_retry 都带 wait=1(防无间隔风暴)。
        assert len(sleeps) >= rounds, (
            f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        )


class TestCwPendingEntryDelegationBranch:
    """CW 挂起对局入口两屏 → 委托 CwEntryExit 分支锁。

    背景:上一 app 中途死在挂起对局入口画面(模式选择-进行中/结束结算确认
    弹窗)时,本 op 既有分支全不认识 → 烧兜底预算。两屏在 cw_screen_state
    大厅态白名单内(非对局中画面),对局中委托分支的判定对它们不可见,须
    屏级显式点名(与退出链路由、CW 入口链挂起分支同一防线);命中即委托
    退出 op(挂起局一律放弃结算,语义见 CwEntryExit docstring)。
    """

    def test_pending_screen_delegates_to_cw_exit(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """挂起入口画面帧:每轮委托假类;零兜底点击;有界 FAIL(画面不变路径)。"""
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
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state,
            'is_express_supply',
            lambda *args, **kw: False,
        )
        # 对局中委托分支判定恒 None(与挂起分支互斥:白名单屏对它不可见)。
        monkeypatch.setattr(
            btnw_module.cw_screen_state,
            'get_in_match_screen_name',
            lambda *args, **kw: None,
        )
        # 挂起入口两屏屏级点名:恒命中「模式选择-进行中」(判定单一源 =
        # get_match_screen_name,画面匹配层由 test_id_mark 单独锁定)。
        monkeypatch.setattr(
            btnw_module,
            'get_match_screen_name',
            lambda ctx, screen, screen_name_list=None: (
                btnw_module.MODE_ONGOING_SCREEN
                if screen_name_list and btnw_module.MODE_ONGOING_SCREEN in screen_name_list
                else None
            ),
        )
        fake = _RecordingFakeCwExit
        fake.constructed = 0
        fake.executed = 0
        fake.fail_after = 1  # 首轮成功(WAIT 路径),之后失败(RETRY 有界路径)
        monkeypatch.setattr(btnw_module, 'CwEntryExit', fake)
        # 守卫被触达即回归(挂起画面应被专属分支接管,不落对话守卫/兜底)。
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'check_npc_dialog',
            lambda self, screen: (_ for _ in ()).throw(
                AssertionError('挂起入口画面应被 cw 挂起分支接管,不应进入对话态守卫')),
        )

        op = _WatchedBackToNormal(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]
        sleeps = _patch_round_sleep(monkeypatch)

        enter_running_state(test_context)
        try:
            result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 委托发生:每轮都构造并执行了退出对局假类(成功 1 轮 + 失败重试轮)。
        rounds: int = op._watchdog_round_count  # type: ignore[attr-defined]
        assert fake.constructed == rounds and fake.executed == rounds, (
            f'委托数(构造 {fake.constructed}/执行 {fake.executed})应==轮次({rounds})'
        )
        # 兜底零点击:右上角返回控件在 CW 画面不存在,一次都不许点。
        assert counters['fallback_click'] == 0, (
            f'兜底被触达 {counters["fallback_click"]} 次,应恒 0'
        )
        # 有界结束:耗尽 20 次 retry 后 FAIL,而非 WAIT 永动。
        assert not result.success, f'画面不变时应有界 FAIL,status={result.status}'
        assert 20 <= rounds <= 25, f'轮次异常({rounds}),应耗满 20 次 retry 才 FAIL'
        assert len(sleeps) >= rounds, (
            f'带 wait 的轮次({len(sleeps)}) < 总轮次({rounds})'
        )
