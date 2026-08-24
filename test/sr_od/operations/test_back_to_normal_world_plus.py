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

import pytest
from one_dragon.utils.i18_utils import gt

import sr_od.operations.back_to_normal_world_plus as btnw_module
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus
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


def _patch_round_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """打桩框架轮间 sleep 并记录调用,提速测试(20 轮 × 1s 真睡太慢)+ 断言 wait 生效。

    ``_after_round_wait`` 用模块级 ``time.sleep``(operation.py),monkeypatch 全局
    打桩测试结束自动还原,不影响 session 级 ``test_context``。
    """
    sleeps: list[float] = []
    monkeypatch.setattr('time.sleep', lambda s: sleeps.append(s))
    return sleeps
