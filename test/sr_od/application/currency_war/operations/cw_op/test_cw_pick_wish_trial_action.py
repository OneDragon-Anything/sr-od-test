"""祈愿试炼确认链动作 op 测试(CwActionPickWishTrialOp;族契约 =
docs/develop/sr_od/application/currency_war/screens/wish_trial.md §4 动作面,
坐标单一真相源 = screens/op-layer.md §1.1「选择坐标观察上报」条款)。

锁的故障形态(机械链 = 点卡选中 → 「按钮-确认选择」确认 → 自上报):
- 落点错位:点击点必须 = 状态容器坐标域 ``wish_trial_opts_xy[param.idx]``
  (观察上报)。现组装坐标 / 回退 env.target / idx 偏移 = 点到别的卡——
  坐标域经真实 report 函数种入非默认点(≠ ``CwScreenWishTrial.CARD_XS`` ×
  ``CARD_Y``)且取 idx=2,三种错法都可分辨。
- 写槽未消费仍盲点:坐标域缺席(观察上报欠供)/ 下标越界 → 守卫断言,
  mouse_move / click / 确认点击 / 声明喂入全零。
- 确认链脱靶:选卡后确认未点到「按钮-确认选择」= overlay 不关(模块头
  「bot 卡此 overlay 68min」)——归档帧上确认点击须落在该 area 内,且
  自上报的后果声明恰喂入一次。
- 写端错位:``chosen_wish`` 写端留在画面 op 落地复查出口(未落地不记账),
  动作 op 发完机械链后 ``chosen_wish`` 仍 None。

演法 = 直调 ``run()``(harness 剧本供给归档帧,``fast_sleep`` 跳过框架等待
与选中动画固定等待);controller 用记录型 stub 记 mouse_move / click 顺序。
"""

from __future__ import annotations

import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_screen_report.wish_trial import (
    CwScreenWishTrialObs,
    report_screen_wish_trial_obs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickWishTrialParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_op.cw_overlay_pick_env import (
    OverlayPickExecEnv,
)
from sr_od.application.currency_war.operations.cw_op.cw_pick_wish_trial_action import (
    CwActionPickWishTrialOp,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_wish_trial import (
    CwScreenWishTrial,
)
from sr_od.application.currency_war.sim import cw_sim_ports

_SCREEN: str = '货币战争-祈愿试炼'
_CONFIRM_AREA: str = '按钮-确认选择'
#: 测试坐标点(刻意 ≠ ``CwScreenWishTrial.CARD_XS`` × ``CARD_Y``:动作 op
#: 若现组装坐标即可分辨)。
_PTS: list[tuple[int, int]] = [(111, 222), (333, 444), (555, 666)]
_OPTS: list[str] = ['累计刷新10次', '获得20金币', '进行一场难度3+遭遇节点战斗']


class _RecordingController(FixtureController):
    """补动作 op 触达面的记录 stub:mouse_move 记录 + mouse_move/click
    相对顺序记录(防吞点击口径:mouse_move 先于 click)。"""

    def __init__(self, ctx) -> None:
        FixtureController.__init__(self, ctx)
        self.events: list[tuple[str, tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        self.events.append(('mouse_move', (int(pos.x), int(pos.y))))

    def click(self, pos=None, press_time: float = 0, pc_alt: bool = False,
              gamepad_key: str | None = None) -> bool:
        if pos is not None:
            self.events.append(('click', (int(pos.x), int(pos.y))))
        return FixtureController.click(self, pos, press_time=press_time,
                                       pc_alt=pc_alt,
                                       gamepad_key=gamepad_key)


def _attach(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
            pts: list[tuple[int, int]] | None,
            ) -> tuple[_RecordingController, object, list[WorldDecl], CwScreenWishTrial]:
    """挂假局 + 祈愿试炼归档帧剧本;``pts`` 非 None 时坐标域经真实 report
    函数种入(与生产观察上报同一写入口)。返回 (controller, gs, 声明喂入
    记录, 宿主画面 op)。"""
    controller = _RecordingController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    controller.set_phases([{'frame': (_SCREEN, '祈愿试炼')}])
    session = types.SimpleNamespace()
    gs = game_state_of(session)
    # 与生产 CurrencyWarMatch 同形:gs = game_state_of(session) 同一对象
    monkeypatch.setattr(test_context, 'cw_match',
                        types.SimpleNamespace(session=session, gs=gs),
                        raising=False)
    if pts is not None:
        report_screen_wish_trial_obs(gs, CwScreenWishTrialObs(
            on_screen=True, options=list(_OPTS), option_points=list(pts)))
    fed: list[WorldDecl] = []
    monkeypatch.setattr(cw_sim_ports, 'declare_world', fed.append)
    host = CwScreenWishTrial(test_context)
    return controller, gs, fed, host


def _make_op(test_context: SrTestContext, host: CwScreenWishTrial, idx: int,
             ) -> tuple[CwActionPickWishTrialOp, OverlayPickExecEnv]:
    env = OverlayPickExecEnv(op=host)
    op = CwActionPickWishTrialOp(test_context, CwActionPickWishTrialParam(idx=idx), env)
    return op, env


def test_click_point_from_state_container_then_confirm(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """落点 = 坐标域[idx](mouse_move 先于 click,同点)→ 确认点击落在
    「按钮-确认选择」area 内(全程恰 2 次点击)→ 自上报后果声明恰喂入一次
    且 = round data;``chosen_wish`` 不在动作 op 写。"""
    controller, gs, fed, host = _attach(test_context, monkeypatch, pts=_PTS)
    op, env = _make_op(test_context, host, idx=2)

    with fast_sleep(op):
        result = op.run()

    assert controller.events[:2] == [('mouse_move', _PTS[2]), ('click', _PTS[2])], \
        f'选卡点击应落在坐标域[2](mouse_move 先于 click),实际 {controller.events!r}'
    assert len(controller.recorded_clicks) == 2, \
        f'应恰点卡 + 确认两次,实际 {controller.recorded_clicks!r}'
    assert controller.click_hit_area(_SCREEN, _CONFIRM_AREA), \
        f'确认点击应落在 {_CONFIRM_AREA} 内,实际 {controller.recorded_clicks!r}'
    assert env.round_result is not None and env.round_result.is_success, \
        f'确认链轮次结果应成功,实际 {env.round_result!r}'
    assert result.is_success, f'动作 op 自身轮次应成功,实际 {result.status!r}'
    assert isinstance(result.data, WorldDecl)
    assert fed == [result.data], f'后果声明应恰喂入一次且 = round data,实际 {fed!r}'
    assert gs.chosen_wish.value is None, 'chosen_wish 写端留在画面 op 落地复查出口'


@pytest.mark.parametrize(
    ('idx', 'pts'),
    [(0, None), (3, _PTS), (-1, _PTS)],
    ids=['坐标域缺席', 'idx越上界', 'idx负值'])
def test_missing_or_out_of_range_points_assert_zero_click(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        idx: int, pts: list[tuple[int, int]] | None) -> None:
    """坐标域缺席(观察上报欠供)/ 下标越界 → AssertionError;mouse_move /
    click / 确认点击 / 声明喂入全零。"""
    controller, _gs, fed, host = _attach(test_context, monkeypatch, pts=pts)
    op, env = _make_op(test_context, host, idx=idx)

    with fast_sleep(op), pytest.raises(AssertionError, match='坐标域缺席/下标越界'):
        op.run()

    assert controller.events == [], f'守卫应在任何点击前,实际 {controller.events!r}'
    assert controller.recorded_clicks == []
    assert fed == [], f'守卫拦截后不应上报,实际喂入 {fed!r}'
    assert env.round_result is None
