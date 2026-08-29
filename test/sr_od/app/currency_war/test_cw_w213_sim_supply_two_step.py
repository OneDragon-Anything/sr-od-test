# -*- coding: utf-8 -*-
"""W213(ADR-0394):sim 补给两步语义行为锁。

锁的是 sim 调 decide_supply 的**行为形态**(与生产 RunSupplyNode 同构),
不锁分布数值——修复前 sim 恒单调 refresh_used=False 且丢弃 refresh 标志
(「恒 idx0」伪影),评分分支(refresh_used=True)在 sim 从未执行。

锁法:monkeypatch cw_events.decide_supply 捕获调用参数 → 跑一小窗
simulate_p1(fallback 池)→ 断言
① 评分分支可达:存在 refresh_used=True 的调用(修复前恒 False);
② 两步链形态:存在「首调 refresh=True(触发重掷)→ 同局内随后出现
   refresh_used=True 调用」的先后序(修复前无第二步);
③ session 级一次:每局首调带 refresh=True 的次数 ≤ 1(生产只刷一次,
   run_supply_node:68 同语义);
④ key 命中度量管道:p1_key_hit_hits ≤ p1_key_hit_total(口径见
   SimResult 字段注释)。

变异探针证据:A/B before 臂(仿真旧「丢弃 refresh 标志」形态,n=300)
里 refresh_used=True 调用恒零——本锁 ① 在旧形态下必红。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_events
from sr_od.application.currency_war.sim.cw_sim import simulate_p1


def test_sim_supply_two_step_scoring_branch_reachable(
        monkeypatch) -> None:
    """① 评分分支(refresh_used=True)在 sim 可达——修复前恒 False。"""
    calls: list[dict] = []
    orig = cw_events.decide_supply

    def spy(options, state, target_comp, config, refresh_used=False):
        calls.append({'refresh_used': refresh_used,
                      'n_opts': len(options)})
        return orig(options, state, target_comp, config, refresh_used)

    monkeypatch.setattr(cw_events, 'decide_supply', spy)
    for seed in range(12):
        simulate_p1(seed, planes=2, pool='fallback')
        if any(c['refresh_used'] for c in calls):
            break
    assert any(c['refresh_used'] for c in calls), (
        'decide_supply 评分分支(refresh_used=True)在 sim 从未执行'
        '——「恒 idx0」伪影回归(ADR-0394)')


def test_sim_supply_reroll_chain_and_once_per_game(monkeypatch) -> None:
    """②③ 两步链形态 + session 级只刷一次。"""
    # 每局的调用轨迹(seed → refresh_used 序列)
    traces: list[list[bool]] = []
    cur: list[bool] = []
    orig = cw_events.decide_supply

    def spy(options, state, target_comp, config, refresh_used=False):
        pick = orig(options, state, target_comp, config, refresh_used)
        cur.append(refresh_used)
        return pick

    monkeypatch.setattr(cw_events, 'decide_supply', spy)
    for seed in range(12):
        cur = []
        simulate_p1(seed, planes=2, pool='fallback')
        if cur:
            traces.append(cur)
        # 存在两步链即够(其余局只验 ③)
    assert traces, '全窗无 supply 节点(环境异常)'
    # ② 两步链:某局出现 False…True 序列(首调触发刷新 → 重掷后评分)
    assert any(
        any(not t[i] and t[i + 1] for i in range(len(t) - 1))
        for t in traces), (
        f'无「首掷→重掷评分」两步链(修复前形态): {traces}')
    # ③ session 级一次:refresh_used=True 的调用只出现在轨迹尾部连续段
    #    (首掷 False 若干次 + 至多一段末尾 True)——更严的等价判据:
    #    True 出现后不再出现 False(标志置位后单调)
    for t in traces:
        seen_true = False
        for flag in t:
            if flag:
                seen_true = True
            assert not (seen_true and not flag), (
                f'refresh_used 标志回退(session 级一次被破坏): {t}')


def test_sim_p1_key_hit_metric_pipe() -> None:
    """④ key 命中度量管道:hits ≤ total,同 seed 可复现。"""
    a = simulate_p1(3, planes=2, pool='fallback')
    b = simulate_p1(3, planes=2, pool='fallback')
    assert 0 <= a.p1_key_hit_hits <= a.p1_key_hit_total
    assert (a.p1_key_hit_hits, a.p1_key_hit_total) == (
        b.p1_key_hit_hits, b.p1_key_hit_total), '同 seed 度量不可复现'
