"""茶歇奖励推进 op 剧本集(CwScreenTeaBreakReward;迭代 2026-11-20-cw-p0-chain
tasks 3.2,design §2.1 op2):

- 剧本 1 = 推进成功:点「开启」→ 双锚判效(回备战标志出现 ∧ 奖励标题
  消失)→ success 交回主循环;
- 剧本 2 = 落点失配:开启后画面不变(非备战落点形态,design §2.7 存疑 1
  的失配兜底)→ 双锚 until 超时 → fail 交回主循环(安全网语义,op 内
  零二次猜测);
- 分侧断言 = 无 report 形态(report 函数不在场,obs 构造即弃零保留)。

帧资产 = 归档帧进仓(奖励页 = 200623);备战帧 = 现役存档。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.operations.cw_screen.cw_screen_tea_break_reward import (
    CwScreenTeaBreakReward,
)

_REWARD: str = '货币战争-茶歇奖励'
_F_REWARD: tuple[str, str] = (_REWARD, 'default')
_F_PREP: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


def _require_frames(test_context: SrTestContext) -> None:
    for screen_name, state in (_F_REWARD, _F_PREP):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def test_open_click_advances_to_prep(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 1 推进成功:点「开启」→ 备战帧双锚过 → success。"""
    _require_frames(test_context)
    from test.harness.cw_fixture_controller import CwFixtureController
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_REWARD,
         'exit': ('on_click_in', _REWARD, '按钮-开启')},
        {'frame': _F_PREP},
    ])
    op = CwScreenTeaBreakReward(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, f'推进成功应 success,实际 {result.status!r}'
    assert ctrl.click_hit_area(_REWARD, '按钮-开启'), \
        f'应点击按钮-开启,实际点击 {ctrl.recorded_clicks}'


def test_open_click_landing_mismatch_fails_back_to_loop(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 落点失配:开启后画面不变(双锚恒不满足)→ until 超时
    fail 交回主循环(失配兜底语义;点击有界 = 节点预算)。"""
    _require_frames(test_context)
    from test.harness.cw_fixture_controller import CwFixtureController
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': _F_REWARD}])   # 无 exit:画面不变
    op = CwScreenTeaBreakReward(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert not result.success, \
        f'落点失配应 fail 交回主循环,实际 {result.status!r}'
    assert ctrl.click_hit_area(_REWARD, '按钮-开启'), \
        f'失配形态开启点击应已发出,实际点击 {ctrl.recorded_clicks}'


def test_no_report_form_report_function_absent() -> None:
    """分侧断言:推进型无 report 形态——report 函数不在场(obs 构造即弃
    零保留,design §2.5 申报;完备测试分侧 = 不在场)。"""
    from sr_od.application.currency_war.kernel.cw_screen_report import (
        tea_break_reward as mod,
    )
    assert not hasattr(mod, 'report_screen_tea_break_reward_obs'), \
        '推进型茶歇奖励不应有 report 函数(无 report 形态申报)'
