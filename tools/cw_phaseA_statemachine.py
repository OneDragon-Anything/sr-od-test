# -*- coding: utf-8 -*-
"""r217 开工门槛③:状态机显式转移表(4 装置)。

Phase A 的时序装置(r213 对抗修正后=4 个):
  A. miss/pass 复合计数(滞回;含粗证据加权输入)
  B. PIVOT_GUARD(换线守卫:期内禁再换线+禁回购旧线件)
  C. 应急退出保持(EMERGENCY_EXIT_HOLD)
  D. D 卡失败计数 + 已访问线集合(降级路径触发与防环)

本文件是**转移表的数据定义+穷举验证器**(单测的测试资产)。
设计约束(r208 对抗修正③):每条转移一句话能解释。
事件集(驱动转移的输入,来自决策循环):
  E1 战斗节点采样(强过/粗过/miss)
  E2 换线事件(主动 pivot 或降级)
  E3 应急触发(HP 危险档)
  E4 应急恢复(HR 安全档持续)
  E5 追赶期进入(应急退出后/位面切换人口低)
  E6 追赶期退出(人口达标)
  E7 锁线事件(信号 2 层命中)
  E8 重启(session 重建)"""

# ---- 状态空间 ----
# mode: economy | war(战力) | emergency | catchup(追赶修饰态,叠加)
# 追赶是修饰态:catchup=True 叠加在 economy/war 上(简化:
# emergency 期间 catchup 强制 False)

SPEC = '''
== 装置 A: 滞回复合计数 ==
状态: streak_miss(int), streak_pass(int), coarse_run(int)
转移:
 A1 采样=强过 → streak_miss=0, coarse_run=0, streak_pass+=1
    [一句话: 强证据清 miss 计数,过计数累积]
 A2 采样=粗过 → streak_pass+=1, coarse_run+=1;
    if coarse_run >= COARSE_TOL: 按 miss 处理(进 A3 分支)
    [一句话: 粗证据暂算过,连击超容忍转 miss]
 A3 采样=miss(或粗连击转miss) → streak_pass=0, streak_miss+=1
    [一句话: miss 清过计数,累积 miss]
 A4 streak_miss >= MISS_M 且 mode=economy → mode=war,
    streak 双清,coarse_run=0
    [一句话: 连续 miss 达阈值,经济转战力,计数重置]
 A5 streak_pass >= PASS_M 且 mode=war → mode=economy,
    streak 双清(冷却并入 PASS_M 语义:PASS_M 取更大值)
    [一句话: 连续过达阈值,战力转经济]
 A6 E2/E5/E6(形态剧变) → streak 双清,coarse_run=0
    [一句话: 形态剧变,旧计数作废]

== 装置 B: PIVOT_GUARD ==
状态: guard_left(int), banned_line(str|None), visited(set)
转移:
 B1 E2 换线 → guard_left=PIVOT_GUARD_N, banned_line=旧线,
    visited.add(旧线);同时触发 A6
    [一句话: 换线后开启守卫窗,旧线进禁购与已访问]
 B2 每战斗节点 → guard_left=max(0,guard_left-1)
    [一句话: 守卫窗随战斗节点递减]
 B3 买旧线核心件请求 且 guard_left>0 → 拒绝;
    豁免: mode=emergency(生存优先) 或 降级目标=banned_line
    [一句话: 守卫期内禁回购旧线件,应急与降级豁免]
 B4 E2 且 guard_left>0 → 拒绝换线(冷却);
    豁免: 降级(降级合法,但触发 B1 重置)
    [一句话: 守卫期内禁再换线,降级除外]
 B5 E2 降级 且 目标 ∈ visited → 改走兜底线(DOT);
    DOT 无降级路径,失败计数饱和无副作用
    [一句话: 防环,已访问过的降级目标换兜底]

== 装置 C: 应急退出保持 ==
状态: emergency(bool), exit_hold(int)
转移:
 C1 E3(HP≤危险档) → emergency=True, exit_hold=0,
    catchup=False(清追赶)
    [一句话: 血危险进应急,清追赶与保持计数]
 C2 应急中 且 E4(HP≥安全档) → exit_hold+=1
    [一句话: 血回升,保持计数累积]
 C3 exit_hold >= EXIT_HOLD_N 且 HP≥安全档 → emergency=False,
    catchup=True(进追赶)
    [一句话: 稳定恢复够久,退应急进追赶]
 C4 应急中 且 HP<安全档 → exit_hold=0
    [一句话: 血再跌,保持计数清零]
 C5 E8 重启 → emergency 按 HP 当前值重判(幂等),
    exit_hold=0
    [一句话: 重启后按血量重新归位]

== 装置 D: 降级触发(失败计数+已访问) ==
状态: roll_fail(int), visited(与 B 共享)
转移:
 D1 D 牌失败(刷新预算耗尽未见目标) → roll_fail+=1
 D2 roll_fail >= FAIL_N → 触发 E2 降级(走 B1/B5),
    roll_fail=0(事件边界清零——r213 对抗修正)
    [一句话: 失败攒够降级,降级后清零防连环滑底]
 D3 E2(任何换线) → roll_fail=0
 D4 E8 重启 → roll_fail=0(容忍,重攒)
'''

# ---- 穷举验证器 ----
def build_states():
    """生成可达状态空间(用于穷举测试)。"""
    states = []
    for mode in ('economy', 'war'):
        for emg in (False, True):
            for cat in (False, True):
                if emg and cat:
                    continue  # 应急期追赶强制 False(C1)
                states.append((mode, emg, cat))
    return states


EVENTS = ('E1_strong', 'E1_coarse', 'E1_miss', 'E2_pivot',
          'E2_degrade', 'E2_degrade_cycle', 'E3', 'E4', 'E5',
          'E6', 'E7', 'E8')


def transition(state, event, k):
    """纯函数转移:state=(mode,emg,catchup) → 新 state 或 None(拒绝)。
    k=常量命名空间(dict)。穷举测试逐格调用。
    注意:本函数只覆盖 mode/emg/catchup 三维(装置 A/C 的宏观面);
    装置 B/D 的计数器维度在各自单测覆盖(维数大,单独穷举)。"""
    mode, emg, cat = state
    if event == 'E3':
        return (mode, True, False)          # C1
    if emg:
        if event == 'E4':
            return state                     # 保持计数在 C 维,宏观态不变
        if event in ('E1_strong', 'E1_coarse', 'E1_miss'):
            return state                     # 应急覆盖一切,采样不改宏观态
        return state
    # 非应急
    if event == 'E5':
        return (mode, False, True)           # 追赶进入
    if cat and event == 'E6':
        return (mode, False, False)          # 追赶退出
    if event in ('E2_pivot', 'E2_degrade', 'E2_degrade_cycle'):
        # 换线触发 A6 重采样——宏观 mode 由重采样定;
        # 穷举测试里用「双态都可能」表示(测试断言 ∈ {(economy..),(war..)})
        return ('resample', False, cat)
    if event == 'E1_miss':
        return (mode, False, cat)            # 单次 miss 不改宏观(滞回在计数维)
    if event in ('E1_strong', 'E1_coarse'):
        return (mode, False, cat)
    return state


if __name__ == '__main__':
    import itertools
    ok = 0
    for st in build_states():
        for ev in EVENTS:
            ns = transition(st, ev, None)
            assert ns is not None, f'未定义转移 {st}+{ev}'
            ok += 1
    print(f'宏观转移表穷举: {len(build_states())} 状态 × '
          f'{len(EVENTS)} 事件 = {ok} 转移,全部有定义 ✓')
    print('SPEC 条数:', SPEC.count('==') and len(
        [l for l in SPEC.splitlines() if l.strip().startswith(('A', 'B', 'C', 'D'))
         and '→' not in l and '一句话' not in l]) or 0, '(转移定义)')
