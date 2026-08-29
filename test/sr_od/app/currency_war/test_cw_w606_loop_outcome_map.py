"""W606 批③·LoopOutcome → SrOperation 轮次语义映射锁(设计 §6)。

映射锚 = 现役 prep_director 对应出口的 round 语义(BATTLE=round_success
wait=3 / BAIL=round_success wait=1 / BRAKE=已停止[hook] / 强战成功
success wait=3、失败 fail 等)。用轻量桩 self 调未绑定方法,不拉 SrContext。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.decision.decision_v2.director_v2 import (
    LoopOutcome,
    LoopOutcomeKind,
)

from sr_od.application.currency_war.prep_director import PrepDirector


def _fake_self():
    calls = []

    def round_success(status: str, wait: int = 0):
        calls.append(('success', status, wait))
        return ('success', status, wait)

    def round_fail(status: str):
        calls.append(('fail', status))
        return ('fail', status)

    return SimpleNamespace(round_success=round_success, round_fail=round_fail), calls


def _map(kind: LoopOutcomeKind, reason: str = '', forced_ok: bool = False):
    fs, calls = _fake_self()
    result = PrepDirector._v2_outcome_to_round(
        fs, LoopOutcome(kind, reason), forced_ok)
    return calls[-1], result


def test_battle_maps_to_round_success_wait3():
    call, _ = _map(LoopOutcomeKind.BATTLE)
    assert call[0] == 'success' and '出战' in call[1] and call[2] == 3


def test_battle_forced_success_and_failure_branch():
    call, _ = _map(LoopOutcomeKind.BATTLE_FORCED, '步数预算耗尽', forced_ok=True)
    assert call[0] == 'success' and '强制出战' in call[1] and call[2] == 3
    call, _ = _map(LoopOutcomeKind.BATTLE_FORCED, '步数预算耗尽', forced_ok=False)
    assert call[0] == 'fail' and '强制出战失败' in call[1]


def test_bail_maps_to_round_success_wait1():
    call, _ = _map(LoopOutcomeKind.BAIL, '事件overlay:盛会之星')
    assert call[0] == 'success' and 'BailToOuter' in call[1] and call[2] == 1


def test_pingpong_stop_maps_to_round_fail():
    call, _ = _map(LoopOutcomeKind.PINGPONG_STOP, '同因 bail ×3(x) 停机待建档')
    assert call[0] == 'fail' and '停机待建档' in call[1]


def test_brake_stop_maps_to_legacy_hook_status():
    call, _ = _map(LoopOutcomeKind.BRAKE_STOPPED, '停机标志已设')
    assert call == ('fail', '已停止[hook]')   # 现役 W209j 出口原语义


def test_evidence_stop_and_fail_map_to_round_fail_with_reason():
    call, _ = _map(LoopOutcomeKind.EVIDENCE_STOP, '分类不confident×4')
    assert call[0] == 'fail' and '分类不confident' in call[1]
    call, _ = _map(LoopOutcomeKind.FAIL, '策略决策异常: boom')
    assert call[0] == 'fail' and '策略决策异常' in call[1]
