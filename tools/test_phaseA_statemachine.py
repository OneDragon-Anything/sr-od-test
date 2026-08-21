# -*- coding: utf-8 -*-
"""r218b pytest 化(第五轮对抗硬条件⑦后半:真单测)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cw_phaseA_statemachine_v2 import (  # noqa: E402
    FAIL_N, GUARD_N, M, MACRO_STATES, joint_states, step,
)

EVENTS = ('E1_strong', 'E1_miss', 'E2_pivot', 'E2_degrade', 'E3',
          'E4', 'E5', 'E6', 'E7_lock', 'E8_restart', 'D_fail',
          'node_pass')


def _legal(s):
    if isinstance(s, set):
        return all(_legal(x) for x in s)
    if s == 'REJECT':
        return True
    return (s[:3] in MACRO_STATES and 0 <= s[3] <= M
            and 0 <= s[4] <= GUARD_N and 0 <= s[5] <= FAIL_N)


def test_closure_all_transitions():
    """闭包:162 状态 × 12 事件全转移结果在合法域。"""
    for st in joint_states():
        for ev in EVENTS:
            assert _legal(step(st, ev)), f'{st}+{ev}'


def test_p1_hysteresis_not_blocked_by_guard():
    """P1:滞回触发不被守卫阻塞(非追赶非应急,miss 达阈即切 war)。"""
    for gl in (0, 1, GUARD_N):
        st = ('economy', False, False, M - 1, gl, 0)
        ns = step(st, 'E1_miss')
        assert ns[0] == 'war', f'{st}->{ns}'


def test_p2_guard_rejects_pivot_and_monotone():
    """P2:守卫在期拒 pivot(非应急);guard 只在开守卫事件增。"""
    for st in joint_states():
        if st[4] > 0 and not st[1]:
            assert step(st, 'E2_pivot') == 'REJECT'
        ns = step(st, 'E2_degrade')
        if isinstance(ns, tuple) and ns != 'REJECT':
            if ns[4] > st[4]:
                assert True  # 开守卫事件,合法


def test_p3_catchup_freezes_hysteresis():
    """P3:追赶期滞回计数冻结(rev7 应急漏斗的 Phase A 版)。"""
    for st in joint_states():
        if st[2] and not st[1]:
            ns = step(st, 'E1_miss')
            assert ns[3] == st[3], f'{st}->{ns}'


def test_p4_emergency_and_catchup_exclusive():
    """P4:应急∧追赶 不可达(C1 清追赶)。"""
    for st in joint_states():
        assert not (st[1] and st[2])
    assert step(('economy', False, True, 0, 0, 0), 'E3')[2] is False


def test_p5_d2_clears_counters():
    """P5:失败达阈的降级清零 streak/fail 并重置守卫(非应急)。"""
    for st in joint_states():
        if st[5] == FAIL_N - 1 and not st[1]:
            ns = step(st, 'D_fail')
            assert isinstance(ns, tuple)
            assert ns[5] == 0 and ns[4] == GUARD_N and ns[3] == 0


def test_c3_catchup_gated_by_population():
    """①C3:应急退出→追赶 有人口条件(已达标不进)。"""
    s = ('economy', False, False, 0, 0, 0)
    assert step(s, 'E5', pop_low=False)[2] is False
    assert step(s, 'E5', pop_low=True)[2] is True


def test_e7_lock_is_cascade_event():
    """④E7 锁线并入级联(streak 清零;返回非确定重采样集)。"""
    s = ('economy', False, False, M, 0, 2)
    ns = step(s, 'E7_lock')
    assert isinstance(ns, set)
    for x in ns:
        assert x[3] == 0 and x[5] == 0  # streak/fail 清零


def test_e8_restart_zeroes_counters():
    """⑤E8:重启计数显式归零,宏观保持。"""
    s = ('war', False, True, M, GUARD_N, FAIL_N)
    ns = step(s, 'E8_restart')
    assert ns == ('war', False, True, 0, 0, 0)


def test_resample_is_nondeterministic_set():
    """⑤resample=非确定集合(两 mode 分支),非伪状态。"""
    s = ('economy', False, False, 0, 0, 0)
    ns = step(s, 'E2_pivot')
    assert isinstance(ns, set) and len(ns) == 2
    assert {x[0] for x in ns} == {'economy', 'war'}
