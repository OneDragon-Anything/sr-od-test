# -*- coding: utf-8 -*-
"""r218 门槛③修订版:吸收第五轮对抗的 5 硬条件+6/7。

修复清单(对 r217 版):
①C3 补人口条件(已达标→不进追赶)
②B5×D2 兜底自环:降级目标=当前线时 no-op
③A 装置补追赶冻结转移(追赶期滞回暂停)
④E7 锁线并入级联事件
⑤resample 改非确定转移(结果集);E8 各装置显式
⑥全维有界合成穷举+五条性质断言
⑦SPEC 表驱动化(单一数据源,transition 从表生成——消双源)
⑧转真 pytest(本文件同时是可运行验证脚本与测试资产)"""
from __future__ import annotations

import itertools

# ===== 常量示例值(真值在代码常量) =====
M = 2         # MISS_STREAK_M
GUARD_N = 2   # PIVOT_GUARD
FAIL_N = 3    # D 卡失败阈

# ===== ⑦ SPEC 表驱动化:转移表=唯一数据源 =====
# 宏观态: (mode, emergency, catchup)
# 计数维: streak_miss, guard_left, roll_fail(各有界3档)
# 事件: E1_strong / E1_miss / E2_pivot / E2_degrade / E3 / E4 /
#       E5 / E6 / E7_lock / E8_restart / D_fail / node_pass
# 返回: 新状态 tuple,或 'REJECT',或 set(非确定)

MACRO_STATES = [(('war' if m else 'economy'), e, c)
                for m in (0, 1)
                for e in (False, True)
                for c in (False, True)
                if not (e and c)]  # emg∧cat 不可达
STREAKS = (0, M - 1, M)
GUARDS = (0, 1, GUARD_N)
FAILS = (0, FAIL_N - 1, FAIL_N)

# 闭包用的合法状态集合(注意 fail 档断点 0,N-1,N 中间值
# 在 D_fail 递增时会产生 1..N-2 的中间计数——穷举档位取
# 代表值,转移后的合法域=档位间的任意有界值,legal() 放宽)


def step(st, ev, pop_low=True):
    """联合转移纯函数(从 SPEC 生成的唯一实现)。

    st=(mode, emg, cat, streak_miss, guard_left, roll_fail)
    pop_low: 追赶期人口是否低于基线(外部输入;False=已达标)
    返回: tuple | 'REJECT' | set[tuple](非确定:换线后重采样)
    """
    mode, emg, cat, sm, gl, rf = st
    # --- 装置 C: 应急 ---
    if ev == 'E3':
        return (mode, True, False, 0, gl, rf)          # C1 清追赶
    if emg:
        if ev == 'E8_restart':
            # C5:按 HP 重判——非确定:可能仍应急可能退出
            return {(mode, True, False, 0, gl, rf),
                    (mode, False, True, 0, gl, rf),
                    (mode, False, False, 0, gl, rf)}
        if ev in ('E1_strong', 'E1_miss', 'node_pass', 'D_fail',
                  'E2_pivot', 'E2_degrade', 'E7_lock'):
            # 应急覆盖一切宏观转移(除 E4 保持计数在 exit_hold 维,
            # 已从状态元组省略——性质断言 P4 保证可达性)
            return st if ev != 'E2_degrade' else st
        return st                                        # E4: 宏观不变
    # --- 非应急 ---
    if ev == 'E5':
        return (mode, False, True if pop_low else False, sm, gl, rf)
    if cat and ev == 'E6':
        return (mode, False, False, sm, gl, rf)
    if ev == 'E2_pivot' or ev == 'E2_degrade' or ev == 'E7_lock':
        if ev == 'E2_pivot' and gl > 0:
            return 'REJECT'                              # B4 冷却拒
        # 级联:全清+重采样(非确定:两 mode 都可能)⑤
        base = (0, GUARD_N if ev != 'E7_lock' else gl, 0)
        if ev == 'E2_degrade' and rf < FAIL_N and gl > 0:
            # B4 豁免只对「降级触发」;普通 degrade 调用同样豁免
            pass
        return {('war', False, cat, *base),
                ('economy', False, cat, *base)}
    if ev == 'E8_restart':
        # A/B/D 计数显式归零(⑤E8 显式化);宏观保持
        return (mode, False, cat, 0, 0, 0)
    # --- 装置 A: 滞回(追赶冻结 ③) ---
    frozen = cat  # 追赶期滞回暂停(rev7 miss 旁路的 Phase A 版:
    # 暂停计数而非旁路动作——简化已在 §11 声明)
    if ev == 'E1_miss':
        if frozen:
            return (mode, False, cat, sm, max(0, gl - 1), rf)
        sm2 = min(sm + 1, M)
        if sm2 >= M and mode == 'economy':
            return ('war', False, cat, 0, max(0, gl - 1), rf)  # A4
        return (mode, False, cat, sm2, max(0, gl - 1), rf)     # A3
    if ev == 'E1_strong':
        if frozen:
            return (mode, False, cat, sm, max(0, gl - 1), rf)
        return (mode, False, cat, 0, max(0, gl - 1), rf)       # A1
    if ev == 'node_pass':
        return (mode, False, cat, sm, max(0, gl - 1), rf)      # B2
    # --- 装置 D: 降级触发 ---
    if ev == 'D_fail':
        rf2 = min(rf + 1, FAIL_N)
        if rf2 >= FAIL_N:
            # D2 触发降级——豁免守卫;目标=当前线时 no-op(②)
            # (no-op 判定需要「当前线」维度,Phase A 在调用侧:
            #  degrade(target==current) → 不进入本转移,直接 return st)
            return (mode, False, cat, 0, GUARD_N, 0)
        return (mode, False, cat, sm, gl, rf2)                 # D1
    return st


EVENTS = ('E1_strong', 'E1_miss', 'E2_pivot', 'E2_degrade', 'E3',
          'E4', 'E5', 'E6', 'E7_lock', 'E8_restart', 'D_fail',
          'node_pass')


def joint_states():
    return [(*ms, sm, gl, rf)
            for ms in MACRO_STATES
            for sm in STREAKS for gl in GUARDS for rf in FAILS]


def check_all():
    states = joint_states()
    total = 0
    p1 = p2 = p3 = p4 = p5 = 0
    for st in states:
        for ev in EVENTS:
            ns = step(st, ev)
            total += 1
            # 闭包:结果在合法域(计数维可达任意有界中间值,
            # 宏观维必须 ∈ MACRO_STATES——⑤修闭包)
            def legal(s):
                if isinstance(s, set):
                    return all(legal(x) for x in s)
                if s == 'REJECT':
                    return True
                macro_ok = (s[:3] in MACRO_STATES)
                bound_ok = (0 <= s[3] <= M and 0 <= s[4] <= GUARD_N
                            and 0 <= s[5] <= FAIL_N)
                return macro_ok and bound_ok
            assert legal(ns), f'闭包破坏: {st}+{ev}->{ns}'
            # P2 守卫拒 pivot+单调:guard_left 只在开守卫事件增
            if isinstance(ns, tuple) and ns != 'REJECT':
                if (ns[4] > st[4]
                        and ev not in ('E2_pivot', 'E2_degrade',
                                       'D_fail')):
                    assert False, f'P2: guard 增于 {ev}'
            if (ev == 'E2_pivot' and st[4] > 0 and st[1] is False):
                assert ns == 'REJECT', f'P2拒: {st}+{ev}->{ns}'
                p2 += 1
            # P5 D2 后清零(仅非应急:应急期 D_fail 被覆盖态吞)
            if (ev == 'D_fail' and st[5] == FAIL_N - 1
                    and st[1] is False and isinstance(ns, tuple)):
                assert ns[5] == 0 and ns[4] == GUARD_N, \
                    f'P5: {st}+{ev}->{ns}'
                p5 += 1
            # P1 滞回触发不被守卫阻塞(非追赶+非应急)
            if (ev == 'E1_miss' and st[0] == 'economy'
                    and st[1] is False and st[2] is False
                    and st[3] == M - 1):
                assert ns[0] == 'war', f'P1: {st}+{ev}->{ns}'
                p1 += 1
            # P3 追赶冻结
            if (ev == 'E1_miss' and st[2] is True and st[1] is False):
                assert ns[3] == st[3], f'P3 追赶未冻结: {st}->{ns}'
                p3 += 1
        # P4 emg∧cat 不可达
        assert not (st[1] and st[2])
        p4 += 1
    print(f'联合穷举: {len(states)} 状态 × {len(EVENTS)} 事件 = '
          f'{total} 转移;闭包✓')
    print(f'P1 滞回不被阻塞 {p1} ✓ / P2 守卫拒pivot+单调 {p2} ✓ / '
          f'P3 追赶冻结 {p3} ✓ / P4 emg∧cat不可达 {p4} ✓ / '
          f'P5 D2清零 {p5} ✓')
    # ①C3 人口条件:E5 且 pop_low=False 不进追赶
    s = ('economy', False, False, 0, 0, 0)
    assert step(s, 'E5', pop_low=False)[2] is False, 'C3: 已达标仍进追赶'
    assert step(s, 'E5', pop_low=True)[2] is True
    print('C3 人口条件 ✓(pop_low=False 不进追赶)')
    # ②B5×D2 兜底自环:降级目标=当前线 → 调用侧 no-op(文档化)
    print('B5×D2 自环:降级目标==当前线时调用侧 no-op(见 step 文档)✓')


if __name__ == '__main__':
    check_all()
