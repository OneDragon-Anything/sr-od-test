# -*- coding: utf-8 -*-
"""r220b pytest v4(终版;七性质全覆盖+T1 三专项)。

r226 起改为**消费生产位** `src/.../cw_phase_machine.py`
(迁移后单一源;本测试防生产版与对抗收敛版漂移)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / 'src'))

from sr_od.application.currency_war.cw_phase_machine import (  # noqa: E402
    EVENTS, LINE_BITS, MODE_ECONOMY, MODE_WAR, MISS_STREAK_M,
    PASS_STREAK_M, PIVOT_GUARD_N, ROLL_FAIL_N,
    initial_state, step,
)

M = MISS_STREAK_M
GUARD_N = PIVOT_GUARD_N
FAIL_N = ROLL_FAIL_N
MACRO_STATES = [(m, e, c) for m in (MODE_ECONOMY, MODE_WAR)
                for e in (False, True) for c in (False, True)
                if not (e and c)]
STREAKS_M = (0, M - 1, M)
STREAKS_P = (0, PASS_STREAK_M - 1, PASS_STREAK_M)
GUARDS = (0, 1, GUARD_N)
FAILS = (0, FAIL_N - 1, FAIL_N)
VISITEDS = (0, 0b011, 0b111)


def joint_states():
    return [(*ms, sm, sp, gl, rf, v)
            for ms in MACRO_STATES
            for sm in STREAKS_M for sp in STREAKS_P
            for gl in GUARDS for rf in FAILS
            for v in VISITEDS]


def is_legal(s):
    if isinstance(s, set):
        return all(is_legal(x) for x in s)
    if s == 'REJECT':
        return True
    return (s[:3] in MACRO_STATES and 0 <= s[3] <= M
            and 0 <= s[4] <= PASS_STREAK_M and 0 <= s[5] <= GUARD_N
            and 0 <= s[6] <= FAIL_N and 0 <= s[7] <= 0b111)


def test_closure_all():
    for st in joint_states():
        for ev in EVENTS:
            for tb in (0, 1, 2):
                assert is_legal(step(st, ev, target_bit=tb))


def test_p1_both_directions():
    for gl in (0, GUARD_N):
        assert step((MODE_ECONOMY, False, False, M - 1, 0, gl, 0, 0),
                    'E1_miss')[0] == MODE_WAR
        assert step((MODE_WAR, False, False, 0, PASS_STREAK_M - 1,
                     gl, 0, 0), 'node_pass')[0] == MODE_ECONOMY


def test_p2_guard_reject():
    for st in joint_states():
        if st[5] > 0 and not st[1]:
            assert step(st, 'E2_pivot') == 'REJECT'


def test_p3_freeze():
    """r246 修订:追赶期冻结 pass streak(人口专注)但**不冻结
    miss streak**(P2 三连败实锤——战力不足与人口落后独立;
    全冻结让 cat 态连败永不切 war)。原 P3=全冻结已推翻。"""
    for st in joint_states():
        if st[2] and not st[1]:
            # miss 仍攒(模式可切 war)
            ns = step(st, 'E1_miss')
            assert ns[3] == min(st[3] + 1, MISS_STREAK_M) or ns[0] == MODE_WAR
            # pass 仍冻结(streak_pass 不涨)
            ps = step(st, 'node_pass')
            assert ps[4] == st[4]


def test_p4_exclusive():
    assert all(not (s[1] and s[2]) for s in joint_states())


def test_p5_d2():
    for st in joint_states():
        if st[6] == FAIL_N - 1 and not st[1]:
            ns = step(st, 'D_fail')
            assert ns[6] == 0 and ns[5] == GUARD_N


def test_p6_emergency():
    for st in joint_states():
        if st[1]:
            for ev in EVENTS:
                if ev not in ('E3', 'E8_restart'):
                    assert step(st, ev) == st


def test_p7_visited_monotone_and_no_return():
    for st in joint_states():
        for ev in EVENTS:
            for tb in (0, 1, 2):
                ns = step(st, ev, target_bit=tb)
                if ev != 'E8_restart':
                    if isinstance(ns, tuple):
                        assert ns[7] >= st[7]
                    elif isinstance(ns, set):
                        assert all(x[7] >= st[7] for x in ns)
                if (ev == 'E2_pivot' and (st[7] >> tb) & 1
                        and not st[1]):
                    assert ns == 'REJECT'


def test_t1b_exhausted_space():
    s = ('economy', False, False, 0, 0, 0, 0, 0b111)
    for tb in (0, 1, 2):
        assert step(s, 'E2_pivot', target_bit=tb) == 'REJECT'


def test_t1c_restart_clears_visited():
    s = ('war', False, False, 0, 0, 1, 2, 0b111)
    assert step(s, 'E8_restart')[7] == 0


def test_f2_e8_idempotent():
    s = ('war', True, False, 0, 0, 1, 2, 0)
    assert {x[2] for x in step(s, 'E8_restart', pop_low=False)} == {False}
