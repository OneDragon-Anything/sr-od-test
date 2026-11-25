"""CwScreenPrep._observe 写端级剧本测试(占席件「开件零写 + 选卡清槽」两拍契约
的阻断形态回归锁;被测单一源 = ``CwScreenPrep._observe`` heavy 帧的备战席
观察写端门——**真走生产写端门**,禁直 observe 绕门)。

锁的设计约定:
- 主场景(全空形态走通):GameState bench 仅槽 k=tome(observation 源)→
  open_tome 上报 → pick_star_tome 上报 → heavy 全空读 → bench 全 empty 且
  源 ∈ {logic, carried}(观察写端「全空读 = 失读保旧」——保的是选卡拍写下的
  logic empty)→ 第 2 步发出点 ``entry._consumable_open_action`` 零开件动作
  (第 3 步以后可达);
- 对照场景(门的 carry 语义与判别力):同前置不选卡 → heavy 全空读 →
  bench 仍 tome(carry 保旧 = 弹窗未处理时件仍在的正确行为)→ 发出点仍产
  开件动作——同 harness 不同前置得到不同结局,证明主场景断言对「清槽缺失」
  敏感。

harness = FixtureController 真建档帧 + ``observe_full`` 打桩回全空
``bench_view``(打桩先例 = test_prep_special_flow._stub_heavy_recognition;
``cw_shot``/``cw_shot_unique`` 同先例重定向 no-op——识别 MISS/异常采集会写
真实 .debug,测试零真实副作用);``CwScreenPrep(test_context)._observe(
heavy=True, screen=帧)`` 真跑写端门。
"""

from __future__ import annotations

import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel import cw_observe, cw_ore_reward
from sr_od.application.currency_war.kernel.cw_action_report.zero_writes import (
    report_action_open_tome_param,
    report_action_pick_star_tome_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenTomeParam,
    CwActionPickStarTomeParam,
)
from sr_od.application.currency_war.obs import cw_observe_full
from sr_od.application.currency_war.obs.cw_observation import (
    reset_phase_round_cache,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import entry

#: 常规备战帧存档(写端门只需一帧稳定画面;heavy 识别核 observe_full 已打桩)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_p1r9')
_OBS_SIG = ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战', mode='read')
_LOGIC_SIG = ChannelSig(family='logic_action', actor='test')

#: 典籍槽(0 基下标 = 物理槽 3;开件动作参数 slot = 下标 + 1)。
_K = 2


class _ObserveTestController(FixtureController):
    """补 ``park_cursor`` 触达面(基类缺 mouse_move → AttributeError 会被框架
    吞成异常重试,伪失败形态;先例 = test_prep_special_flow._PrepTestController)。"""

    def mouse_move(self, pos) -> None:
        pass


def _tome_only_view() -> BenchView:
    """典籍为备战栏唯一非空槽(全空形态的阻断前置)。"""
    return BenchView(slots=[BenchSlot(kind='empty')] * _K
                     + [BenchSlot(kind='tome')]
                     + [BenchSlot(kind='empty')] * (8 - _K), capacity=9)


def _stub_heavy_all_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """heavy 识别核打桩:observe_full 回执 = 全空 bench_view(deployed 失读
    None,其余键缺 = 各识别域按失读分支走);截图族重定向 no-op;晶矿简易
    装备池按先例补非空(report_spheres_observed 真实链可完成)。"""
    monkeypatch.setattr(
        cw_observe_full, 'observe_full',
        lambda *a, **k: {'bench_view': BenchView(
            slots=[BenchSlot(kind='empty')] * 9, capacity=9),
            'deployed_rows': None, 'read_receipt': None})
    monkeypatch.setattr(cw_observe, 'cw_shot', lambda image, name: None)
    monkeypatch.setattr(cw_observe, 'cw_shot_unique',
                        lambda image, label: None)
    monkeypatch.setattr(cw_ore_reward, '_SIMPLE_EQUIP_POOL', ('蓝钻', '红钻'))


@pytest.fixture
def prep_env(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch) -> SrTestContext:
    """写端门剧本夹具:假控制器换装 + heavy 识别核打桩(monkeypatch 自动
    还原,防污染 session 级共享 ctx)。"""
    if not test_context.has_screen(*_PREP_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_PREP_FRAME[0]}/{_PREP_FRAME[1]}.webp')
    ctrl = _ObserveTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    _stub_heavy_all_empty(monkeypatch)
    ctrl.set_phases([{'frame': _PREP_FRAME}])
    reset_phase_round_cache()   # 清位面轮次模块缓存(单调守卫跨测防串染)
    return test_context


def _attach_gs(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch) -> GameState:
    """挂假局(session 每测新建 = GameState 弱引用表新支,无跨测串染)。"""
    match = types.SimpleNamespace(session=types.SimpleNamespace())
    monkeypatch.setattr(test_context, 'cw_match', match)
    return game_state_of(match.session)


def _observe_heavy(test_context: SrTestContext) -> None:
    """真走生产写端门:CwScreenPrep._observe(heavy=True) 全空读。"""
    op = CwScreenPrep(test_context)
    frame = test_context.controller.current_frame
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            op._observe(heavy=True, screen=frame)
    finally:
        reset_running_state(test_context, op)


def test_pick_clears_then_all_empty_read_does_not_stall(
        prep_env: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """主场景(阻断形态回归锁):典籍唯一在席 → 开件 → 选卡清槽 → heavy
    全空读 → bench 全 empty(源 logic/carried)→ 第 2 步发出点零开件动作
    (第 3 步以后可达)。"""
    gs = _attach_gs(prep_env, monkeypatch)
    gs.observe(gs.bench, _tome_only_view(), sig=_OBS_SIG)
    report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=_K + 1), _LOGIC_SIG)
    report_action_pick_star_tome_param(
        gs, CwActionPickStarTomeParam(idx=0), _LOGIC_SIG)
    assert gs.bench.source == 'logic'

    _observe_heavy(prep_env)

    assert all(s.kind == 'empty' for s in gs.bench.value.slots)
    assert gs.bench.source in ('logic', 'carried')
    assert entry._consumable_open_action(gs) is None


def test_without_pick_all_empty_read_carries_tome(
        prep_env: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """对照场景(门的 carry 语义与判别力):开件后不选卡 → heavy 全空读 →
    bench 仍 tome(carry 保旧)→ 发出点仍产开件动作(同 harness 不同前置
    不同结局,证明主场景断言对「清槽缺失」敏感)。"""
    gs = _attach_gs(prep_env, monkeypatch)
    gs.observe(gs.bench, _tome_only_view(), sig=_OBS_SIG)
    report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=_K + 1), _LOGIC_SIG)

    _observe_heavy(prep_env)

    assert gs.bench.value.slots[_K].kind == 'tome'
    assert gs.bench.source == 'carried'
    emitted = entry._consumable_open_action(gs)
    assert emitted is not None and emitted.action.slot == _K + 1
