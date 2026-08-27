"""行为锁:位面情报采集「非clean帧等待门」。

背景(2026-08-27 两触发点同签名,run 22:05:23 / 22:10:16):位面转换/加载
动画窗内备战节点条是残影,``CollectPlaneIntel`` 入口分支短窗连读(~2.5s 3 帧)
全部「节点条未读出(非clean帧)」→ op 失败。治本 = 「等到 clean 为止 +
宽上限兜底」:

1. 短窗内非clean**不弃**——只重读,不失败(动画窗远长于旧 3 连读窗);
2. 每次重读有间隔(给转换/加载动画时间),不是忙连读;
3. 超宽上限(:data:`_NODE_BAR_WAIT_CAP_S` = 90s,覆盖最慢加载)才真失败。

clean 判定语义不变(read_node_sequence 读出 = clean);测试用替身时钟
(monkeypatch 模块级 ``time``)驱动,零实机、零真实等待。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation_base import OperationResult
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_PREP = '货币战争-备战'


def _make_op(test_context: SrTestContext, monkeypatch, phases: list[dict],
             watchdog_max_rounds: int = 300):
    """构造被测 op(fixture 控制器注入 + 看门狗),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        CollectPlaneIntel,
    )

    class _Watched(WatchdogOperationMixin, CollectPlaneIntel):
        pass

    op = _Watched(test_context)
    op.watchdog_max_rounds = watchdog_max_rounds
    fc = FixtureController(test_context)
    fc.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', fc)
    return op, fc


class _FakeClock:
    """cpi 模块级 ``time`` 替身:sleep 记录并推近 fake 墙钟(monotonic)。"""

    def __init__(self, advance_per_sleep: float = 10.0):
        self.t: float = 0.0
        self.sleeps: list[float] = []
        self.advance_per_sleep: float = advance_per_sleep

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += self.advance_per_sleep


def _patch_node_reader(monkeypatch, outcomes: list) -> list[int]:
    """替身 read_node_sequence:按 ``outcomes`` 逐次返回(耗尽后恒 None)。

    返回调用计数列表(经闭包记录,断言「第几次读才点击」用)。
    """
    from sr_od.application.currency_war import cw_observation as cwo

    calls: list[int] = []

    def _fake_read(ctx, screen):
        calls.append(len(calls) + 1)
        if len(calls) <= len(outcomes):
            return outcomes[len(calls) - 1]
        return None

    monkeypatch.setattr(cwo, 'read_node_sequence', _fake_read)
    return calls


def _exec(op) -> OperationResult:
    with fast_sleep():
        return op.execute()


# --------------------------------------------------------------------------- #
# 锁①:短窗内非clean不弃 + 间隔重读 + 超上限才失败
# --------------------------------------------------------------------------- #


def test_nonclean_waits_until_cap_then_fails(test_context: SrTestContext,
                                             monkeypatch) -> None:
    """锁①:备战节点条持续非clean → 不在短窗失败;间隔重读;超宽上限才 round_fail。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    # 恒非clean(read_node_sequence 恒 None),fake 墙钟每次 sleep 推进 10s
    _patch_node_reader(monkeypatch, [])
    clock = _FakeClock(advance_per_sleep=10.0)
    monkeypatch.setattr(cpi_mod, 'time', clock)

    op, fc = _make_op(test_context, monkeypatch,
                      [{'frame': (_PREP, 'shop_closed')}])
    enter_running_state(test_context)
    try:
        res = _exec(op)
    finally:
        reset_running_state(test_context, op)

    assert not res.success, f'持续非clean终应失败,得 {res.status!r}'
    assert '放弃采集' in str(res.status) and '超' in str(res.status), (
        f'失败应声明「非clean持续超上限放弃」,得 {res.status!r}')
    # 间隔重读:每次重读前有 sleep(间隔值),且至少覆盖旧 3 连读窗(短窗内不弃)
    assert len(clock.sleeps) >= 3, f'短窗内不应放弃(应 ≥3 次重读),得 {len(clock.sleeps)}'
    assert all(s == cpi_mod._NODE_BAR_READ_INTERVAL_S for s in clock.sleeps), (
        f'重读间隔应恒为 {cpi_mod._NODE_BAR_READ_INTERVAL_S}s,得 {clock.sleeps}')
    # 宽上限兜底:墙钟计时超 _NODE_BAR_WAIT_CAP_S 才失败(sleep 推进时钟 ≥ 上限)
    assert clock.t >= cpi_mod._NODE_BAR_WAIT_CAP_S, (
        f'应在超上限({cpi_mod._NODE_BAR_WAIT_CAP_S}s)后才失败,得墙钟 {clock.t}s')
    # 等待期零点击(非clean帧点了也白点,交互无效)
    assert fc.recorded_clicks == [], '非clean等待期不应产生点击'


# --------------------------------------------------------------------------- #
# 锁②:动画窗过后读到 clean → 恢复采集(点击节点图标开详情)
# --------------------------------------------------------------------------- #


def test_recovers_after_clean_frame(test_context: SrTestContext,
                                    monkeypatch) -> None:
    """锁②:前 3 次非clean → 第 4 次读出 clean → 立即恢复:点节点条内图标,不失败。"""
    from sr_od.application.currency_war.operations.handlers import (
        collect_plane_intel as cpi_mod,
    )

    clean_slot = SimpleNamespace(state='current', cx=100, cy=100)
    calls = _patch_node_reader(monkeypatch, [None, None, None, [clean_slot]])
    clock = _FakeClock(advance_per_sleep=10.0)
    monkeypatch.setattr(cpi_mod, 'time', clock)

    # click 落「区域-节点条」内 → 剧本推进到下一帧(同备战帧;之后恒非clean,
    # 由看门狗收口——本锁只验证「clean 后恢复点击」)
    op, fc = _make_op(
        test_context, monkeypatch,
        [{'frame': (_PREP, 'shop_closed'),
          'exit': ('on_click_in', _PREP, '区域-节点条')},
         {'frame': (_PREP, 'shop_closed')}],
        watchdog_max_rounds=25)
    enter_running_state(test_context)
    try:
        _exec(op)
    finally:
        reset_running_state(test_context, op)

    # 前 3 次非clean未点击(短窗内不弃也不乱点),第 4 次 clean 才点击恢复
    assert fc.recorded_clicks, 'clean 帧后应点击节点图标开位面详情'
    assert len(calls) >= 4, f'点击前应经历 3 次非clean重读,得读数次数 {calls}'
    # 等待期走的是间隔重读(sleep 间隔;clean 后点击的 1.5s 开屏等待也走此时钟)
    assert clock.sleeps.count(cpi_mod._NODE_BAR_READ_INTERVAL_S) >= 3, (
        f'非clean重读应有 ≥3 次间隔 sleep({cpi_mod._NODE_BAR_READ_INTERVAL_S}s),得 {clock.sleeps}')
    assert all(s in (cpi_mod._NODE_BAR_READ_INTERVAL_S, 1.5) for s in clock.sleeps), (
        f'不应出现忙连读(只允许重读间隔与点击后等待),得 {clock.sleeps}')
