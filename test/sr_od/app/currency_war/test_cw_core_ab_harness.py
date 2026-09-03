"""test_cw_core_ab_harness 主题锁:换核 A/B harness(simulate_core_ab)。

锁的语义 = sim/runner.simulate_core_ab 的两条公平性不变式:
1. **零漂移门**:现役核经 harness 注入(工厂构造)vs simulate_p1 默认
   构造,同 seed 同池配对 → SimResult.ledger 逐位相等、全字段恒等
   (先例 = engine_p1.simulate_p1 docstring 的 planes=1 回归门
   「同 seed 同池 diff={}」;红了 = 注入路径引入额外 rng 消耗或
   调用时点漂移,换核 A/B 前必须先修 harness)。
2. **自配对恒等**:双臂同工厂 → SimResult 全字段恒等(锁 harness
   自身不引入臂间不对称)。

边界:n 取断言成立的最小值(README 测试纪律 12——两条锁都是恒等
断言,更小 n 与更大 n 等价;统计 A/B 属 sim 日常工作流,不由单测
承担);池用 'fallback'(显式旧模型,结果打标,不依赖 snapshot
快照内容,单跑免池解析开销)。不落盘(simulate_core_ab 纯内存)。
"""
from __future__ import annotations

from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.sim.engine_p1 import sim_decision_registry
from sr_od.application.currency_war.sim.runner import simulate_core_ab


def _core_factory():
    """现役核工厂:与 simulate_p1 默认分支同源(注册表自 sim 视图派生)。

    工厂在测试内每次调用新构造策略对象——与 simulate_core_ab 的
    「工厂每局各调一次」契约对齐;注册表在闭包外派生一次,工厂
    本身确定性、零 rng 消费(会话流派生是 seed 契约)。
    """
    reg = sim_decision_registry()

    def factory() -> DecisionV2Strategy:
        return DecisionV2Strategy(registry=reg)

    return factory


def test_core_ab_zero_drift_gate() -> None:
    """零漂移门:工厂注入臂 ≡ 默认构造臂(ledger 逐位相等)。

    什么真实错误会杀它:harness 注入路径改动了 simulate_p1 的 rng
    消耗序/决策调用时点(如工厂消费局内 rng、策略跨局复用引入
    状态漂移、参数传递错位)——任一都会让同 seed 配对局分叉,
    ledger_diff_pairs > 0。
    """
    rep = simulate_core_ab(_core_factory(), None, n=2, seed_base=1234,
                           pool='fallback', planes=1)
    assert rep['ledger_diff_pairs'] == 0, rep.get('ledger_first_diff')
    assert rep['identical_result_pairs'] == rep['n']
    assert rep['avg_hp_a'] == rep['avg_hp_b']
    # 双臂同池同指纹(含 +eqg 位;不一致时 simulate_core_ab 已 raise,
    # 这里锁回显字段存在且两臂共用)
    assert rep['pool_fingerprint'].endswith('+eqg1')


def test_core_ab_self_pairing_identity() -> None:
    """自配对:同工厂双臂 → SimResult 全字段恒等(臂间无不对称)。

    什么真实错误会杀它:harness 对两臂的参数拼装不对称(一臂漏传
    invest/p2_combat 等共享参数、或臂间 seed 编排错位)——任何臂间
    差异都会让 identical_result_pairs < n。
    """
    fac = _core_factory()
    rep = simulate_core_ab(fac, fac, n=2, seed_base=4321,
                           pool='fallback', planes=1)
    assert rep['identical_result_pairs'] == rep['n']
    assert rep['ledger_diff_pairs'] == 0
    assert rep['hp_resolution_floor']['n'] == rep['n']
    # 恒等双臂的配对差恒 0 → 噪声带判据的差值口径自洽
    assert rep['hp_resolution_floor']['mean_diff'] == 0.0


def test_core_ab_pool_fingerprint_guard(monkeypatch) -> None:
    """双臂池指纹不一致 = raise(对拍不公平,显式失败优于静默对比)。

    什么真实错误会杀它:harness 的池一致性守卫被删/被绕过(如未来
    重构把 resolve_pool 挪到臂内且允许两臂不同 pool 参数)——守卫
    整体脱落时 raise 不发生,本锁红;守卫在但变成入口前置拒绝
    (没跑局就抛)时,末尾的调用计数断言红(守卫语义退化为参数
    校验,失去「跑了局才发现漂移」的对账价值)。
    """
    import pytest

    import sr_od.application.currency_war.sim.runner as runner_mod

    orig = runner_mod.simulate_p1
    calls = {'n': 0}

    def _spoof_arm_b_fingerprint(seed, **kw):
        calls['n'] += 1
        res = orig(seed, **kw)
        if kw.get('strategy') is not None:
            # 只污染 A 臂(注入臂)指纹,模拟「双臂池漂移」
            res.pool_fingerprint = 'spoofed-mismatch'
        return res

    monkeypatch.setattr(runner_mod, 'simulate_p1', _spoof_arm_b_fingerprint)
    with pytest.raises(RuntimeError, match='池指纹不一致'):
        simulate_core_ab(_core_factory(), None,
                         n=1, seed_base=7, pool='fallback', planes=1)
    assert calls['n'] >= 2   # 两臂各至少跑一局后才触发守卫,非入口拒绝
