"""CwActionSynthesisCancelOp 执行体测试(harness 剧本)。

锁的设计约定(出处 = 开发 skill flow/action-op.md §1「执行规范」+ 玩家 skill
screens/货币战争-备战.md「合成确认浮层」节;与确认合成动作 op 同构,等待更短):
- 机械执行:坐标守卫通过后,移到 ✕ 中心、点一次、把光标移到装备栏外、再等浮层收起
  (光标必须先移开再等——✕ 中心也对着装备栏右列下一行的格子,悬停会弹出框架接不住的
  装备详情浮窗);
- 零写:上报不改状态容器的浮层字段;round data 携「动作后仍在备战画面」的后果声明;
- 回执恰一条:经执行器分派 = 执行器写、op 不写;直接调用且有对局上下文 = op 自己写;
  没有对局上下文的直接调用 = 不写;
- 坐标越界 = 守卫断言,零点击;终结动作;sim 装配下机械分支静默跳过。
"""

from __future__ import annotations

import types

import pytest
from test.harness.fixture_controller import FixtureController, fast_sleep

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionSynthesisCancelParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.operations.cw_op import (
    cw_synthesis_cancel_action as mod,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.operations.sr_operation import SrOperation

_PREP_SCREEN = '货币战争-备战'
_OBS = ChannelSig(family='obs', actor='test')
#: 停光标点(框架操作基类的中立区,在装备栏外)。
_PARK_POINT = (SrOperation.PARK_POINT.x, SrOperation.PARK_POINT.y)
_POINT = (1707, 325)
_OVERLAY_READING = {
    'ok_xy': (1821, 325), 'cancel_xy': _POINT,
    'panel_rect': [1597, 222, 1872, 359],
    'inputs': [
        {'name': '轮滑鞋', 'conf': 0.914, 'cx': 1632, 'cy': 251},
        {'name': '光能电池', 'conf': 0.878, 'cx': 1731, 'cy': 251},
    ],
    'product': {'name': None, 'conf': 0.301, 'cx': 1838, 'cy': 248},
}


class _ClickParkController(FixtureController):
    """记录 op 触达面的顺序:移鼠标 / 点击 / 停光标(等待由 _run 一并记入)。"""

    def __init__(self, ctx) -> None:
        FixtureController.__init__(self, ctx)
        self.events: list[tuple[str, object]] = []

    def mouse_move(self, pos) -> None:
        self.events.append(('mouse_move', (int(pos.x), int(pos.y))))

    def click(self, pos=None, press_time: float = 0, pc_alt: bool = False,
              gamepad_key: str | None = None) -> bool:
        if pos is not None:
            self.events.append(('click', (int(pos.x), int(pos.y))))
        return FixtureController.click(self, pos, press_time=press_time,
                                       pc_alt=pc_alt, gamepad_key=gamepad_key)

    def park_cursor(self, game_pos, before_wait: float = 0.0,
                    after_wait: float = 0.2) -> None:
        self.events.append(('park', (int(game_pos.x), int(game_pos.y))))


@pytest.fixture
def cancel_ctx(test_context, monkeypatch):
    """共享 ctx 的夹具:controller 换装记录型 stub(monkeypatch 自动还原)。"""
    controller = _ClickParkController(test_context)
    monkeypatch.setattr(test_context, 'controller', controller)
    return test_context


def _attach_match(cancel_ctx, monkeypatch):
    """挂假局并种下浮层在场的读数(与观察链同写入口 gs.observe)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(cancel_ctx, 'cw_match', match)
    gs = game_state_of(match.session)
    gs.observe(gs.synthesis_overlay, _OVERLAY_READING, sig=_OBS)
    return gs


def _run(cancel_ctx, monkeypatch, env, point):
    """跑一次 op;返回 (结果, 被跳过的等待时长, 事件序列)。等待也记进事件序列,
    用来断言「光标移开」发生在「等收起」之前。"""
    op = mod.CwActionSynthesisCancelOp(cancel_ctx,
                                       CwActionSynthesisCancelParam(*point), env)
    controller = cancel_ctx.controller
    with fast_sleep(op) as skipped:
        real_sleep = mod.time.sleep

        def _sleep(seconds: float) -> None:
            controller.events.append(('sleep', seconds))
            real_sleep(seconds)

        monkeypatch.setattr(mod.time, 'sleep', _sleep)
        result = op.run()
    return result, skipped, controller.events


def test_clicks_once_parks_cursor_then_waits(cancel_ctx, monkeypatch) -> None:
    """直接调用、有对局上下文:点一次落在传入坐标,光标先移到装备栏外再等收起
    (op 内等待 = 模块常量);上报不改浮层字段;后果声明 = 仍在备战画面;回执恰一条。"""
    gs = _attach_match(cancel_ctx, monkeypatch)
    result, skipped, events = _run(cancel_ctx, monkeypatch, None, _POINT)

    assert events == [('mouse_move', _POINT), ('click', _POINT),
                      ('park', _PARK_POINT), ('sleep', mod.COLLAPSE_WAIT_S)]
    assert skipped == [mod.COLLAPSE_WAIT_S]
    assert result.is_success
    assert mod.CwActionSynthesisCancelOp.terminal is True
    assert isinstance(result.data, WorldDecl)
    assert result.data.next_screen == _PREP_SCREEN
    assert result.data.trigger == ''
    # 零写:浮层字段保持上一帧的读数(「浮层已处理」只由下一帧观察写)
    assert gs.synthesis_overlay.value == _OVERLAY_READING
    receipts = list(gs.receipts.value or [])
    assert [(r['op'], r['reason'], r['screen']) for r in receipts] == [
        ('CwActionSynthesisCancelOp', '', _PREP_SCREEN)]


@pytest.mark.parametrize(
    ('env', 'with_match', 'expected_receipts'),
    [
        (types.SimpleNamespace(executor=object()), True, 0),   # 经执行器分派:执行器写
        (None, True, 1),                                        # 直接调用、有对局上下文
        (None, False, 0),                                       # 没有对局上下文
    ],
    ids=['经执行器分派', '直接调用有对局', '直接调用无对局'],
)
def test_receipt_written_exactly_once_per_dispatch(cancel_ctx, monkeypatch, env,
                                                   with_match, expected_receipts) -> None:
    """每个动作 op 恰一条回执:经执行器分派时 op 内不写(执行器已写);直接调用且
    备有对局上下文时 op 写一条;没有对局上下文时不写。点击在三种情形下都照发。"""
    gs = _attach_match(cancel_ctx, monkeypatch) if with_match else None
    result, _skipped, events = _run(cancel_ctx, monkeypatch, env, _POINT)

    assert events[:2] == [('mouse_move', _POINT), ('click', _POINT)]
    assert result.is_success
    if gs is None:
        assert result.data is None   # 无处记账:零上报零声明
        return
    assert isinstance(result.data, WorldDecl)
    assert len(list(gs.receipts.value or [])) == expected_receipts


@pytest.mark.parametrize('point', [(-1, 325), (1707, -1), (1920, 325), (1707, 1080)])
def test_out_of_screen_point_rejects_before_clicking(cancel_ctx, point) -> None:
    """坐标越界(负值或超出 1080p 画面)= 守卫断言,零点击。"""
    op = mod.CwActionSynthesisCancelOp(cancel_ctx,
                                       CwActionSynthesisCancelParam(*point))
    with pytest.raises(AssertionError, match='坐标越界'), fast_sleep(op):
        op.run()
    assert cancel_ctx.controller.events == []


def test_sim_skips_mechanical(cancel_ctx, monkeypatch) -> None:
    """sim 装配下机械分支静默跳过(不移鼠标、不点击、不等),自上报照走。"""
    monkeypatch.setattr(cw_sim_ports, 'mechanical_io_allowed', lambda: False)
    _attach_match(cancel_ctx, monkeypatch)
    result, skipped, events = _run(cancel_ctx, monkeypatch, None, _POINT)

    assert events == []
    assert skipped == []
    assert result.is_success
    assert isinstance(result.data, WorldDecl)
