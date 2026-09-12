# -*- coding: utf-8 -*-
"""r220 门槛③ v4(终版):吸收第七轮对抗 T1(防环装置进穷举模型)。

修复:
T1a 状态加 visited(3 bit 子集;Phase A 线=3 条,DOT 兜底
    不进 visited——与 §5 环风险论证对齐:兜底是终结线)
T1b E2_pivot 目标已访问 → REJECT(线空间耗尽态的出口=
    pivot 恒拒,D 装置的降级接管,兜底不可降级)
T1c E8_restart 清空 visited(与 §5 一致)
T1d P7 性质:非 E8 下 visited 单调不减;无可达转移回到
    已访问线"""
from __future__ import annotations

M = 2
PASS_M = 3
GUARD_N = 2
FAIL_N = 3

MACRO_STATES = [('war' if m else 'economy', e, c)
                for m in (0, 1)
                for e in (False, True)
                for c in (False, True)
                if not (e and c)]
STREAKS_M = (0, M - 1, M)
STREAKS_P = (0, PASS_M - 1, PASS_M)
GUARDS = (0, 1, GUARD_N)
FAILS = (0, FAIL_N - 1, FAIL_N)
# T1a:Phase A 线 3 条(L1/L2/L3);visited 用 3bit(0-7)
VISITEDS = (0, 0b011, 0b111)   # 空/部分/耗尽 三代表档

EVENTS = ('E1_strong', 'E1_miss', 'node_pass', 'E2_pivot',
          'E2_degrade', 'E3', 'E4', 'E5', 'E6', 'E7_lock',
          'E8_restart', 'D_fail')


def step(st, ev, pop_low=True, target_bit=0):
    """st=(mode,emg,cat,sm,sp,gl,rf,visited)。
    target_bit:E2_pivot 的目标线 bit(0-2)。"""
    mode, emg, cat, sm, sp, gl, rf, vis = st
    if ev == 'E3':
        return (mode, True, False, 0, 0, gl, rf, vis)
    if emg:
        if ev == 'E8_restart':
            return {(mode, True, False, 0, 0, gl, rf, 0),
                    (mode, False, True if pop_low else False,
                     0, 0, 0, 0, 0),
                    (mode, False, False, 0, 0, 0, 0, 0)}   # T1c 清空
        return st
    if ev == 'E5':
        return (mode, False, True if pop_low else False,
                sm, sp, gl, rf, vis)
    if cat and ev == 'E6':
        return (mode, False, False, sm, sp, gl, rf, vis)
    if ev == 'E2_pivot':
        if gl > 0:
            return 'REJECT'
        if vis & (1 << target_bit):
            return 'REJECT'          # T1b:目标已访问(耗尽态出口)
        nv = vis | (1 << target_bit)
        return {('war', False, cat, 0, 0, GUARD_N, 0, nv),
                ('economy', False, cat, 0, 0, GUARD_N, 0, nv)}
    if ev == 'E2_degrade':
        # 降级不受守卫拒;visited 语义:降级目标也进 visited
        # (调用侧:目标==当前线→no-op;目标=兜底→不进,bit 无兜底)
        nv = vis | (1 << target_bit) if target_bit < 3 else vis
        return {('war', False, cat, 0, 0, GUARD_N, 0, nv),
                ('economy', False, cat, 0, 0, GUARD_N, 0, nv)}
    if ev == 'E7_lock':
        base = (0, 0, gl, 0, vis)
        return {('war', False, cat, *base),
                ('economy', False, cat, *base)}
    if ev == 'E8_restart':
        return (mode, False, cat, 0, 0, 0, 0, 0)           # T1c
    frozen = cat
    if ev == 'E1_miss':
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf, vis)
        sm2 = min(sm + 1, M)
        if sm2 >= M and mode == 'economy':
            return ('war', False, cat, 0, 0, max(0, gl - 1), rf, vis)
        return (mode, False, cat, sm2, 0, max(0, gl - 1), rf, vis)
    if ev == 'E1_strong':
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf, vis)
        return (mode, False, cat, 0, min(sp + 1, PASS_M),
                max(0, gl - 1), rf, vis)
    if ev == 'node_pass':
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf, vis)
        sp2 = min(sp + 1, PASS_M)
        if sp2 >= PASS_M and mode == 'war':
            return ('economy', False, cat, 0, 0, max(0, gl - 1),
                    rf, vis)
        return (mode, False, cat, 0, sp2, max(0, gl - 1), rf, vis)
    if ev == 'D_fail':
        rf2 = min(rf + 1, FAIL_N)
        if rf2 >= FAIL_N:
            return (mode, False, cat, 0, 0, GUARD_N, 0, vis)
        return (mode, False, cat, sm, sp, gl, rf2, vis)
    return st


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
            and 0 <= s[4] <= PASS_M and 0 <= s[5] <= GUARD_N
            and 0 <= s[6] <= FAIL_N and 0 <= s[7] <= 0b111)


def check_all():
    states = joint_states()
    total = 0
    counts = {k: 0 for k in ('p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7')}
    for st in states:
        for ev in EVENTS:
            for tb in (0, 1, 2):
                ns = step(st, ev, target_bit=tb)
                total += 1
                assert is_legal(ns), f'闭包:{st}+{ev}+t{tb}->{ns}'
                # P7: 非 E8 下 visited 单调不减;pivot 已访问目标必拒
                if ev not in ('E8_restart',):
                    if isinstance(ns, tuple):
                        assert ns[7] >= st[7], \
                            f'P7 单调: {st}+{ev}->{ns}'
                    elif isinstance(ns, set):
                        for x in ns:
                            assert x[7] >= st[7]
                if (ev == 'E2_pivot' and (st[7] >> tb) & 1
                        and not st[1]):
                    assert ns == 'REJECT', \
                        f'P7 已访问仍可 pivot: {st}+t{tb}'
                    counts['p7'] += 1
                if (ev == 'E2_pivot' and st[5] > 0 and not st[1]):
                    assert ns == 'REJECT'
                    counts['p2'] += 1
                if (ev == 'E1_miss' and st[0] == 'economy'
                        and not st[1] and not st[2] and st[3] == M - 1):
                    assert ns[0] == 'war'
                    counts['p1'] += 1
                if (ev == 'node_pass' and st[0] == 'war'
                        and not st[1] and not st[2]
                        and st[4] == PASS_M - 1):
                    assert ns[0] == 'economy'
                    counts['p1'] += 1
                if (ev == 'E1_miss' and st[2] and not st[1]):
                    assert ns[3] == st[3]
                    counts['p3'] += 1
                if (ev == 'D_fail' and st[6] == FAIL_N - 1
                        and not st[1] and isinstance(ns, tuple)):
                    assert ns[6] == 0 and ns[5] == GUARD_N
                    counts['p5'] += 1
                if st[1] and ev not in ('E3', 'E8_restart'):
                    assert ns == st
                    counts['p6'] += 1
        assert not (st[1] and st[2])
        counts['p4'] += 1
    print(f'联合穷举: {len(states)} 状态 × {len(EVENTS)} 事件 × '
          f'3 目标 = {total} 转移;闭包✓')
    print(f"P1 进出 {counts['p1']} / P2 守卫 {counts['p2']} / "
          f"P3 冻结 {counts['p3']} / P4 互斥 {counts['p4']} / "
          f"P5 D2 {counts['p5']} / P6 应急 {counts['p6']} / "
          f"P7 防环 {counts['p7']}")
    # 耗尽态语义(T1b):visited=0b111 时任何 pivot 恒拒
    s = ('economy', False, False, 0, 0, 0, 0, 0b111)
    for tb in (0, 1, 2):
        assert step(s, 'E2_pivot', target_bit=tb) == 'REJECT'
    print('T1b 耗尽态:pivot 恒拒,降级接管(D 装置),兜底不可降级 ✓')


if __name__ == '__main__':
    check_all()
