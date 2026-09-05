"""投资策略屏入口锚「动画帧复探」容忍语义锁(20/21 局同型失败治本批)。

故障机制:投资策略节点首访时,派发帧 → op 首帧落在「备战 → 金币过场动画 →
overlay 淡入」过渡段,首帧采样 miss「标识-请选择投资策略」;旧实现单探测
miss 即 ``round_fail('非投资策略屏')``(round_fail 不吃 node_max_retry_times,
直接炸出整 op),外层重试才自愈但每次触发哨兵报警+退出(2026-09-06
01:41:30 / 02:22:28 两局实证)。修法与 cw_loop._invest_overlay_dispatch 同族:
首探 miss → 短窗后新截图复探;窗口内命中 = 不报失败;持续 miss(超窗)
= 仍报失败(防无限等)。

本文件锁容忍语义本体(三测):
1. 首帧 miss → 复探命中 → 判定通过(不报失败);
2. 持续 miss → 恰好复探 ENTRY_REPROBE_TIMES 次后判 False(有界,防无限等;
   复探间隔 = ENTRY_REPROBE_WAIT_S,不烧无谓轮询);
3. 首帧命中(常态)→ 零复探等待/零新截图(成本门控,同 cw_loop 三审 C2)。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy import (
    CwScreenInvestStrategy,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController

SCREEN = '货币战争-投资策略'


class _NoMoveFixtureController(FixtureController):
    """补 safe_click 触达的 ``mouse_move`` stub(safe_click bug#1 缓解调用)。

    on_polls 推进改「先推进后取帧」:基类先取帧后计数,触发推进的那次调用
    仍返回旧帧(滞后一拍),复探窗只有 4 拍,滞后一拍即吃掉最后一次复探 →
    稳定帧永远探不到。本类保证第 N 次 on_polls 到点的那次截图就返回新帧。
    """

    def mouse_move(self, game_pos) -> None:  # noqa: ANN001 - 对齐控制器签名
        pass

    def _advance_polls_then_frame(self):
        self._maybe_advance_on_polls()
        self._poll_count += 1
        return self.current_frame

    def screenshot(self, independent: bool = False):
        frame = self._advance_polls_then_frame()
        self.mock_screenshot = frame
        import time as _time
        return _time.time(), frame

    def get_screenshot(self, independent: bool = False):
        return self._advance_polls_then_frame()


def _make_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
             reprobe_frames: list, sleeps: list[float]) -> CwScreenInvestStrategy:
    """构造被测 op:首帧用 备战 idle fixture(miss 锚),复探帧按序返回 reprobe_frames;
    sleep 记账不真实等待。"""
    op = CwScreenInvestStrategy(test_context)
    op.last_screenshot = test_context.load_screen('货币战争-备战', 'r1_idle_stop')
    calls = {'n': 0}

    def _fake_screenshot() -> object:
        idx = min(calls['n'], len(reprobe_frames) - 1)
        calls['n'] += 1
        return reprobe_frames[idx]

    monkeypatch.setattr(op, 'screenshot', _fake_screenshot)

    import sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy as m

    monkeypatch.setattr(m.time, 'sleep', sleeps.append)
    return op


def _fixture_missing(test_context: SrTestContext) -> bool:
    return (not test_context.has_screen('货币战争-备战', 'r1_idle_stop')
            or not test_context.has_screen(SCREEN, 'default'))


def test_invest_entry_first_frame_miss_reprobe_hits_not_fail(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁①:首帧 miss(过渡帧)→ 复探命中 = 判定通过,不报失败。

    fixture 语义:首帧用 备战(过渡帧代理,无投资策略锚);复探帧用
    投资策略 default(overlay 淡入完成后的稳定帧)。
    """
    if _fixture_missing(test_context):
        pytest.skip('fixture 缺:货币战争-备战/default 或 投资策略/default')
    sleeps: list[float] = []
    op = _make_op(test_context, monkeypatch,
                  [test_context.load_screen(SCREEN, 'default')], sleeps)
    assert op._ensure_entry_screen() is True, (
        '首帧 miss + 复探命中应判定通过(动画帧容忍),不得报非投资策略屏')
    assert sleeps, '首帧 miss 后应有短窗等待再复探'


def test_invest_entry_persistent_miss_bounded_window_still_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁②:持续 miss → 恰好复探 ENTRY_REPROBE_TIMES 次后判 False(有界)。

    防无限等语义:窗口 = ENTRY_REPROBE_TIMES 次 × ENTRY_REPROBE_WAIT_S;
    每次复探间隔 = WAIT_S(不多不少,超窗立即放行失败,不烧无谓轮询)。
    """
    if _fixture_missing(test_context):
        pytest.skip('fixture 缺:货币战争-备战/default 或 投资策略/default')
    prep = test_context.load_screen('货币战争-备战', 'r1_idle_stop')
    sleeps: list[float] = []
    op = _make_op(test_context, monkeypatch, [prep], sleeps)
    assert op._ensure_entry_screen() is False, '持续 miss(超窗)应仍判失败'
    assert len(sleeps) == CwScreenInvestStrategy.ENTRY_REPROBE_TIMES, (
        f'复探次数应有界 = ENTRY_REPROBE_TIMES({CwScreenInvestStrategy.ENTRY_REPROBE_TIMES}),'
        f'实际 {len(sleeps)}')
    assert sleeps == [CwScreenInvestStrategy.ENTRY_REPROBE_WAIT_S] * len(sleeps), (
        f'复探间隔应为 ENTRY_REPROBE_WAIT_S({CwScreenInvestStrategy.ENTRY_REPROBE_WAIT_S})')


def test_invest_entry_first_frame_hit_zero_reprobe(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁③:首帧命中(常态)→ 零复探等待/零新截图(成本门控)。"""
    if not test_context.has_screen(SCREEN, 'default'):
        pytest.skip('fixture 缺:投资策略/default')
    op = CwScreenInvestStrategy(test_context)
    op.last_screenshot = test_context.load_screen(SCREEN, 'default')
    shots: list[int] = []

    def _no_screenshot() -> object:
        shots.append(1)
        raise AssertionError('首帧命中不应再截图复探')

    monkeypatch.setattr(op, 'screenshot', _no_screenshot)
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy as m
    monkeypatch.setattr(m.time, 'sleep', lambda s: shots.append(s))
    assert op._ensure_entry_screen() is True
    assert not shots, '首帧命中应零复探等待/零新截图'


def test_invest_entry_full_flow_transition_to_stable_succeeds(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """集成锁(生产路径):过渡帧起手 → 复探进稳定帧 → 走完选卡+确认,不报失败。

    剧本:备战(过渡帧,复探窗内流转到投资策略)→ 投资策略 default(选卡)
    → card1_selected(确认)→ 大厅(overlay 已关,terminal)。
    本锁钉住 round_fail 不再在首帧 miss 时立即炸出整 op。
    """
    if _fixture_missing(test_context):
        pytest.skip('fixture 缺')
    if (not test_context.has_screen(SCREEN, 'card1_selected')
            or not test_context.has_screen('货币战争-大厅', 'lobby')):
        pytest.skip('fixture 缺:投资策略/card1_selected 或 大厅/lobby')

    phases = [
        {  # 过渡帧:无投资策略锚,第 3 次截图起流转到投资策略稳定帧
            'frame': ('货币战争-备战', 'r1_idle_stop'),
            'exit': ('on_polls', 3),
        },
        {  # 投资策略稳定帧:选卡点击 (460,474) → 推进
            'frame': (SCREEN, 'default'),
            'exit': ('on_click_in', [400, 450, 520, 500]),
        },
        {  # 已选卡:确认点击(area 中心) → 推进
            'frame': (SCREEN, 'card1_selected'),
            'exit': ('on_click_in', SCREEN, '按钮-确认'),
        },
        {  # 大厅:terminal(overlay 已关,验关通过)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    ctrl = _NoMoveFixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    ctrl.set_phases(phases)
    monkeypatch.setattr(test_context, 'controller', ctrl)

    op = CwScreenInvestStrategy(test_context)
    # 选项 OCR 桩:本锁只验入口容忍语义,选项读取/打分归既有锁(单一源)。
    monkeypatch.setattr(op, '_read_options',
                        lambda screen: [('过渡帧策略甲', 460, 490)])
    # 等待记账不真实等待(入口复探窗 3.2s + 确认等待,fast_sleep 只覆盖
    # operation.py 模块 time,本 op 与 _overlay_confirm 各自 import time)。
    sleeps: list[float] = []
    import sr_od.application.currency_war.operations.cw_screen._overlay_confirm as oc
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_invest_strategy as m
    monkeypatch.setattr(m.time, 'sleep', sleeps.append)
    monkeypatch.setattr(oc.time, 'sleep', lambda s: None)

    from test.harness.fixture_controller import (
        enter_running_state,
        reset_running_state,
    )

    enter_running_state(test_context)
    try:
        result = op.execute()
    finally:
        reset_running_state(test_context, op)
    assert result.success, (
        f'过渡帧起手应经复探走完整流程成功,不得报非投资策略屏:status={result.status}')
    assert not any('非投资策略屏' in (result.status or '') for _ in [0])
    # 走完选卡+确认(点击序 = 卡名选中 + 确认)
    assert any(abs(p.x - 460) <= 20 and abs(p.y - 480) <= 20 for p in ctrl.recorded_clicks), (
        f'应点击卡名选中,实际点击={ctrl.recorded_clicks}')
    assert any(abs(p.x - 978) <= 20 and abs(p.y - 983) <= 20 for p in ctrl.recorded_clicks), (
        f'应点击确认按钮,实际点击={ctrl.recorded_clicks}')
    assert ctrl.phase_idx == len(phases) - 1, f'应推进到 terminal phase,实际 {ctrl.phase_idx}'
