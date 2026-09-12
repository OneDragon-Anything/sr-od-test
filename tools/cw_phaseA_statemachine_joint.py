# -*- coding: utf-8 -*-
"""r217b 门槛③补充:维度交互穷举(装置A计数×装置B守卫×装置D失败的
联合状态机——第五轮对抗预防性补强:宏观/计数分离切分下的交互 bug 温床)。

联合状态:(mode, streak_miss, guard_left, roll_fail) 离散化:
  streak_miss ∈ {0, M-1, M}(3档:零/临界/达阈)
  guard_left ∈ {0, 1, N}(3档)
  roll_fail ∈ {0, FAIL_N-1, FAIL_N}(3档)
mode ∈ {economy, war} → 2×3×3×3 = 54 联合状态 × 事件集
目标:验证三条交互不变量:
  I1: streak_miss 达 M 且 economy → 必转 war(滞回触发不被守卫阻塞)
  I2: guard_left>0 时 E2_pivot 被拒,但降级照走且重置一切
  I3: roll_fail 达 FAIL_N 的降级不因 guard 在期而丢失(豁免)"""
import itertools

M = 2        # MISS_STREAK_M 示例值
GUARD_N = 2  # PIVOT_GUARD 示例值
FAIL_N = 3   # D 卡失败示例值

STREAKS = (0, M - 1, M)
GUARDS = (0, 1, GUARD_N)
FAILS = (0, FAIL_N - 1, FAIL_N)


def step(st, ev):
    """联合转移(纯函数);返回新状态或 'REJECT'。"""
    mode, sm, gl, rf = st
    if ev == 'E1_miss':
        sm = min(sm + 1, M)
        if sm >= M and mode == 'economy':
            mode = 'war'
            sm = 0  # A4 双清(近似:pass 维省略)
        return (mode, sm, max(0, gl - 1), rf)
    if ev == 'E1_strong':
        return (mode, 0, max(0, gl - 1), rf)
    if ev == 'E2_pivot':
        if gl > 0:
            return 'REJECT'   # B4 冷却拒绝
        return (mode, 0, GUARD_N, 0)  # B1 守卫开启+A6 清
    if ev == 'E2_degrade':
        # B4 豁免:降级合法,重置守卫(A6/B1)
        return (mode, 0, GUARD_N, 0)  # D2 roll_fail 清零
    if ev == 'D_fail':
        rf = min(rf + 1, FAIL_N)
        if rf >= FAIL_N:
            # 触发降级(D2)——豁免守卫
            return (mode, 0, GUARD_N, 0)
        return (mode, sm, gl, rf)
    if ev == 'node_pass':     # 战斗节点过(守卫递减)
        return (mode, sm, max(0, gl - 1), rf)
    return st


def check_invariants():
    states = list(itertools.product(('economy', 'war'),
                                    STREAKS, GUARDS, FAILS))
    events = ('E1_miss', 'E1_strong', 'E2_pivot', 'E2_degrade',
              'D_fail', 'node_pass')
    total = 0
    i1 = i2 = i3 = 0
    for st in states:
        for ev in events:
            ns = step(st, ev)
            assert ns != 'REJECT' or ev == 'E2_pivot', \
                f'非法 REJECT: {st}+{ev}'
            total += 1
            # I1: 滞回触发不被守卫阻塞
            if (ev == 'E1_miss' and st[1] == M - 1
                    and st[0] == 'economy'):
                assert ns[0] == 'war', f'I1 破坏: {st}+{ev}->{ns}'
                i1 += 1
            # I2: 守卫在期 pivot 拒
            if (ev == 'E2_pivot' and st[2] > 0):
                assert ns == 'REJECT', f'I2 破坏: {st}+{ev}->{ns}'
                i2 += 1
            # I3: 失败达阈的降级不被守卫吞
            if ev == 'D_fail' and st[3] == FAIL_N - 1:
                assert ns != 'REJECT' and ns[3] == 0 and ns[2] == GUARD_N, \
                    f'I3 破坏: {st}+{ev}->{ns}'
                i3 += 1
    print(f'联合穷举: {len(states)} 状态 × {len(events)} 事件 = '
          f'{total} 转移 ✓')
    print(f'不变量验证: I1 滞回不被守卫阻塞 {i1} 次 ✓ / '
          f'I2 守卫拒 pivot {i2} 次 ✓ / '
          f'I3 失败降级不被吞 {i3} 次 ✓')


if __name__ == '__main__':
    check_invariants()
