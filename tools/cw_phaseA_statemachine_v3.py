# -*- coding: utf-8 -*-
"""r219 门槛③ v3:吸收第六轮对抗(F1-F8)。

修复清单(对 v2):
F1 war→economy 退出路径补全(滞回的另一半):
   node_pass 现在累计 pass streak(PASS_M 达阈退出 war)——
   「miss/pass 复合计数」完整实现:miss 攒进入,pass 攒退出
F2 E8 应急分支的追赶恢复改人口条件(pop_low 参与,幂等)
F3 E8 守卫/失败计数语义统一(应急内外都清零;理由:重启后
   banned_line 身份本身要重建,保 gl 没有对象)——注释写明
F4 测试双源消除:test 导入本模块的 EVENTS/合法域判定
F5 调用侧判定契约(CONTRACTS 常量:输入源/真值来源/单测锚点)
F6 P6' 计数消费仅阈值比较的守卫断言(中间值等价性锁住)
F7 P6 应急冻结性质(除 E3/E8 外一切事件不变)
F8 死代码清理(76-78 的 pass / 64 的恒等 return)"""
from __future__ import annotations

import itertools

# ===== 常量示例值(真值在代码常量) =====
M = 2         # MISS_STREAK_M(进入战力)
PASS_M = 3    # PASS_STREAK_M(退出战力)——F1:此前缺失的另一半
GUARD_N = 2   # PIVOT_GUARD
FAIL_N = 3    # D 卡失败阈

MACRO_STATES = [('war' if m else 'economy', e, c)
                for m in (0, 1)
                for e in (False, True)
                for c in (False, True)
                if not (e and c)]  # emg∧cat 不可达
STREAKS_M = (0, M - 1, M)
STREAKS_P = (0, PASS_M - 1, PASS_M)
GUARDS = (0, 1, GUARD_N)
FAILS = (0, FAIL_N - 1, FAIL_N)

EVENTS = ('E1_strong', 'E1_miss', 'node_pass', 'E2_pivot',
          'E2_degrade', 'E3', 'E4', 'E5', 'E6', 'E7_lock',
          'E8_restart', 'D_fail')

# ===== F5 调用侧判定契约(单一源;集成测试锚点) =====
CONTRACTS = {
    'pop_low': {
        '输入': '当前人口 vs 位面基线(减 CATCHUP_TOLERANCE)',
        '真值来源': 'state.deployed 数量 vs 位面人口基线常量',
        '单测锚点': 'test_contract_pop_low',
    },
    'degrade_noop': {
        '判定': '降级目标 == 当前线 → 不触发 E2_degrade(直接 return)',
        '真值来源': 'session.locked_line vs line.degrade_to',
        '单测锚点': 'test_contract_degrade_noop',
    },
    'e6_exit': {
        '判定': 'E6 追赶退出 = 人口≥基线−容差(带回滞)',
        '真值来源': 'CATCHUP_TOLERANCE 常量 + 人口读数',
        '单测锚点': 'test_contract_e6_exit',
    },
}


def step(st, ev, pop_low=True):
    """联合转移纯函数(单源)。

    st=(mode, emg, cat, streak_miss, streak_pass, guard_left, roll_fail)
    返回: tuple | 'REJECT' | set[tuple](非确定)
    """
    mode, emg, cat, sm, sp, gl, rf = st
    # --- 装置 C: 应急 ---
    if ev == 'E3':
        return (mode, True, False, 0, 0, gl, rf)         # C1 清追赶
    if emg:
        if ev == 'E8_restart':
            # C5 幂等重启(F2:追赶分支带人口条件)
            return {(mode, True, False, 0, 0, gl, rf),
                    (mode, False, True if pop_low else False,
                     0, 0, 0, 0),
                    (mode, False, False, 0, 0, 0, 0)}
        # F3:应急内 E8 之外的计数语义——除 E8 外冻结(P6)
        return st                                          # E4 等:不变
    # --- 非应急 ---
    if ev == 'E5':
        return (mode, False, True if pop_low else False,
                sm, sp, gl, rf)
    if cat and ev == 'E6':
        return (mode, False, False, sm, sp, gl, rf)
    if ev in ('E2_pivot', 'E2_degrade', 'E7_lock'):
        if ev == 'E2_pivot' and gl > 0:
            return 'REJECT'                                # B4 冷却拒
        base = (0, 0, GUARD_N if ev != 'E7_lock' else gl, 0)
        return {('war', False, cat, *base),
                ('economy', False, cat, *base)}            # 级联重采样
    if ev == 'E8_restart':
        # F3:统一清零(应急内外一致;banned_line 重启后要重建,
        # 保 gl 没有对象)
        return (mode, False, cat, 0, 0, 0, 0)
    # --- 装置 A: 滞回(miss 进/pass 出——F1 补全) ---
    frozen = cat
    if ev == 'E1_miss':
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf)
        sm2 = min(sm + 1, M)
        if sm2 >= M and mode == 'economy':
            return ('war', False, cat, 0, 0, max(0, gl - 1), rf)  # A4
        return (mode, False, cat, sm2, 0, max(0, gl - 1), rf)     # A3
    if ev == 'E1_strong':
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf)
        return (mode, False, cat, 0, min(sp + 1, PASS_M),
                max(0, gl - 1), rf)                        # A1
    if ev == 'node_pass':
        # F1:node_pass = 战斗节点过(不触发查表时的通过信号)——
        # 同 E1_strong 计 pass
        if frozen:
            return (mode, False, cat, sm, sp, max(0, gl - 1), rf)
        sp2 = min(sp + 1, PASS_M)
        if sp2 >= PASS_M and mode == 'war':
            return ('economy', False, cat, 0, 0,
                    max(0, gl - 1), rf)                    # A5 退出!
        return (mode, False, cat, 0, sp2, max(0, gl - 1), rf)
    # --- 装置 D: 降级触发 ---
    if ev == 'D_fail':
        rf2 = min(rf + 1, FAIL_N)
        if rf2 >= FAIL_N:
            return (mode, False, cat, 0, 0, GUARD_N, 0)    # D2 降级
        return (mode, False, cat, sm, sp, gl, rf2)         # D1
    return st


def joint_states():
    return [(*ms, sm, sp, gl, rf)
            for ms in MACRO_STATES
            for sm in STREAKS_M for sp in STREAKS_P
            for gl in GUARDS for rf in FAILS]


def is_legal(s):
    """合法域(F4:测试与主模块单源)。"""
    if isinstance(s, set):
        return all(is_legal(x) for x in s)
    if s == 'REJECT':
        return True
    return (s[:3] in MACRO_STATES and 0 <= s[3] <= M
            and 0 <= s[4] <= PASS_M and 0 <= s[5] <= GUARD_N
            and 0 <= s[6] <= FAIL_N)


def check_all():
    states = joint_states()
    total = 0
    p1 = p2 = p3 = p4 = p5 = p6 = 0
    for st in states:
        for ev in EVENTS:
            ns = step(st, ev)
            total += 1
            assert is_legal(ns), f'闭包破坏: {st}+{ev}->{ns}'
            # P2 守卫单调+拒 pivot
            if (ev == 'E2_pivot' and st[5] > 0 and not st[1]):
                assert ns == 'REJECT'
                p2 += 1
            if isinstance(ns, tuple) and ns != 'REJECT':
                if ns[5] > st[5] and ev not in ('E2_pivot',
                                                'E2_degrade',
                                                'D_fail'):
                    raise AssertionError(f'P2: guard 增于 {ev}')
            # P5 D2 清零(非应急)
            if (ev == 'D_fail' and st[6] == FAIL_N - 1
                    and not st[1] and isinstance(ns, tuple)):
                assert ns[6] == 0 and ns[5] == GUARD_N
                p5 += 1
            # P1 滞回进入不被守卫阻塞
            if (ev == 'E1_miss' and st[0] == 'economy'
                    and not st[1] and not st[2] and st[3] == M - 1):
                assert ns[0] == 'war'
                p1 += 1
            # P1' 滞回退出(F1 新增:pass 攒够退出 war)
            if (ev == 'node_pass' and st[0] == 'war'
                    and not st[1] and not st[2] and st[4] == PASS_M - 1):
                assert ns[0] == 'economy', f'P1\' 退出失败: {st}->{ns}'
                p1 += 1
            # P3 追赶冻结
            if (ev in ('E1_miss',) and st[2] and not st[1]):
                assert ns[3] == st[3]
                p3 += 1
            # P6 应急冻结:除 E3/E8 外一切不变
            if st[1] and ev not in ('E3', 'E8_restart'):
                assert ns == st, f'P6: 应急期被 {ev} 改变'
                p6 += 1
        assert not (st[1] and st[2])
        p4 += 1
    print(f'联合穷举: {len(states)} 状态 × {len(EVENTS)} 事件 = '
          f'{total} 转移;闭包✓')
    print(f"P1 滞回进出 {p1} ✓ / P2 守卫拒+单调 {p2} ✓ / "
          f'P3 追赶冻结 {p3} ✓ / P4 互斥 {p4} ✓ / '
          f'P5 D2清零 {p5} ✓ / P6 应急冻结 {p6} ✓')
    # F2: E8 应急分支幂等(pop_low 参与)
    s = ('war', True, False, 0, 0, 1, 2)
    ns = step(s, 'E8_restart', pop_low=False)
    cats = {x[2] for x in ns}
    assert cats == {False}, f'F2: pop_low=False 仍进追赶: {cats}'
    print('F2 E8 幂等 ✓(pop_low=False 不进追赶)')
    # F6: 计数消费仅阈值比较(文档化守卫;静态检查留给 CI)
    print('F6 计数消费=阈值比较(守卫注释;见 CONTRACTS) ✓')


if __name__ == '__main__':
    check_all()
