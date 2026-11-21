"""CwScreenPrep 局外缺席守卫测试(harness 剧本)。

锁设计约定(cw_screen_prep 缺席防御申报):局外语境(ctx.cw_match=None)
下备战访问必须显式 fail(status 含「无 cw_match」)交回,不得在
match.session 裸解处 AttributeError 崩溃;观察四查(第0/a/b/c)在局外全部
按否处理落观察缺席门,act 缺席门(session 谓词,刻意与观察门 strategy
谓词不同)兜住含 a/c 早退的全部进入路径。

两条用例分别钉住 a 查(返回投资策略选择词形)与 c 查(补给分流)两个
早退入口:当前实现下局外直接落观察缺席门;若任一 match 前置被移除,
路径经 act 缺席门仍显式 fail(测试仍绿);两门全拆才会裸解崩溃,测试
即红——守卫整条防御链,非只锁单点。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

import sr_od.application.currency_war.operations.cw_screen.cw_screen_prep as prep_mod
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

#: 备战帧存档(screen_name, state);a 查词形经 monkeypatch 钉住命中,
#: 不依赖帧面真含该词(识别点桩,设计剧本允许形态)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')


class _WatchedCwScreenPrep(WatchdogOperationMixin, CwScreenPrep):
    """带看门狗的 op(流程测试防无限轮)。"""


def _require_screens(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    if not test_context.has_screen(_PREP_FRAME[0], _PREP_FRAME[1]):
        pytest.skip(f'存档截图缺失:screens/{_PREP_FRAME[0]}/{_PREP_FRAME[1]}.webp')


def _pin_a_query_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 a 查识别点钉成恒命中(仅「返回投资策略选择」词;其余走原实现)。

    桩只在「a 查 match 前置被移除」的回归形态下才会被消费——当前实现
    局外短路跳过 a 查,桩不参与现行路径,只作防御链回归绊线。
    """
    original = CwScreenPrep.round_by_ocr

    def _stub(self: CwScreenPrep, screen, target_cn: str, *args, **kwargs):
        if target_cn == '返回投资策略选择':
            return self.round_success(target_cn)
        return original(self, screen, target_cn, *args, **kwargs)

    monkeypatch.setattr(CwScreenPrep, 'round_by_ocr', _stub)


def _run_op(test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
            phases: list[dict]) -> tuple[FixtureController, OperationResult]:
    """装假控制器 + 局外语境 + 跑完整 execute(),返回(控制器, 结果)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(test_context, 'cw_match', None)  # 局外语境(防污染守卫:走 monkeypatch)
    ctrl.set_phases(phases)
    op = _WatchedCwScreenPrep(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result


def test_match_absent_a_form_fails_explicitly(
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """局外 + a 查词形入口:显式 fail(无 cw_match),零点击零崩溃。"""
    _require_screens(test_context)
    _pin_a_query_hit(monkeypatch)
    ctrl, result = _run_op(test_context, monkeypatch, [{'frame': _PREP_FRAME}])

    assert not result.success, f'局外访问应显式 fail,实际 {result.status}'
    assert '无 cw_match' in (result.status or ''), \
        f'status 应含缺席门文案,实际:{result.status}'
    assert ctrl.recorded_clicks == [], \
        f'局外访问不应有任何点击:{ctrl.recorded_clicks}'


def test_match_absent_supply_divert_fails_explicitly(
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """局外 + c 查补给分流入口:分流早退经缺席门链显式 fail(无 cw_match)。

    read_node_sequence 桩只钉 current 补给槽;当前实现局外短路跳过 c 查
    直接落观察缺席门,桩同 a 查桩一样仅作防御链回归绊线。"""
    _require_screens(test_context)
    slot = SimpleNamespace(state='current', node_type='supply')
    monkeypatch.setattr(prep_mod, 'read_node_sequence',
                        lambda ctx, screen: [slot])
    ctrl, result = _run_op(test_context, monkeypatch, [{'frame': _PREP_FRAME}])

    assert not result.success, f'局外访问应显式 fail,实际 {result.status}'
    assert '无 cw_match' in (result.status or ''), \
        f'status 应含缺席门文案,实际:{result.status}'
    assert ctrl.recorded_clicks == [], \
        f'局外访问不应有任何点击:{ctrl.recorded_clicks}'
