"""cw_line_tribunal(20 号战略假设审判层 v0)测试:LR/门限定价/三态/防拖延(ADR-0171)。"""
import pytest

from sr_od.application.currency_war.cw_line_tribunal import (
    HypothesisRegistry,
    LineHypothesis,
    decision_threshold,
    evidence_lr,
    verdict,
)


def _hyp(kind='commit', deadline=12):
    return LineHypothesis(
        hyp_id='h1', line='列车同行', kind=kind,
        checkpoints=[4, 8], deadline=deadline,
        expected={4: 0.3, 8: 0.6, 12: 0.9},
    )


def test_conservative_merge_min_not_product():
    """保守合并:通道 LR 乘积合成后取 min(防相关性双计)。"""
    h = _hyp()
    h.add_evidence(4, 'pool_absence', '核心缺席3刷', 2.0)
    h.add_evidence(4, 'pool_absence', '核心缺席4刷', 2.0)     # 池通道累计 4.0
    h.add_evidence(4, 'timeline_lag', '进度掉队', 3.0)
    # 乘积会 12;保守 min = 3.0
    assert h.cumulative_lr == 3.0
    assert evidence_lr({'a': 4.0, 'b': 3.0}) == 3.0
    assert evidence_lr({}) == 1.0


def test_threshold_priced_by_costs():
    """门限定价:血健康(错守便宜)→ K 大(多守);边缘区 → K 小(早弃)。非常数。"""
    k_healthy = decision_threshold(cost_abandon=18.0, cost_hold=6.0)    # 错守便宜
    k_edge = decision_threshold(cost_abandon=18.0, cost_hold=36.0)      # λ_hp 高
    assert k_healthy == 3.0 and k_edge == 0.5
    assert k_healthy > k_edge
    assert decision_threshold(10.0, 0.0) > 1e8    # 错守免费 → 永不弃


def test_three_state_verdicts():
    """三态:LR≥K 弃;0.5K≤LR<K amended(现五门表达不了的中间判决);<0.5K 守。"""
    h = _hyp()
    h.add_evidence(4, 'pool_absence', '缺席', 3.0)
    v = verdict(h, 4, cost_abandon=18.0, cost_hold=6.0)      # K=3 → LR=3 ≥ K
    assert v.action == 'abandon'
    h2 = _hyp()
    h2.add_evidence(4, 'pool_absence', '缺席', 2.0)          # K=3, 0.5K=1.5 → amended
    v2 = verdict(h2, 4, cost_abandon=18.0, cost_hold=6.0)
    assert v2.action == 'amended'
    h3 = _hyp()
    h3.add_evidence(4, 'pool_absence', '轻', 1.1)            # < 1.5 → 守
    v3 = verdict(h3, 4, cost_abandon=18.0, cost_hold=6.0)
    assert v3.action == 'hold'


def test_deadline_prevents_procrastination():
    """预注册防拖延:deadline 到、LR>1(证据偏负)但不足 K → 强制弃(M22「再等等」)。"""
    h = _hyp(deadline=8)
    h.add_evidence(8, 'timeline_lag', '进度掉队', 1.2)       # LR=1.2 < K(设 K 大)
    v = verdict(h, 8, cost_abandon=50.0, cost_hold=5.0)      # K=10 → 正常会 hold
    assert v.action == 'abandon' and 'deadline' in v.reason


def test_registry_lifecycle():
    """登记簿:登记→判决→关闭(消费端接线的宿主)。"""
    reg = HypothesisRegistry()
    reg.register(_hyp())
    vs = reg.judge_all(4, cost_abandon=18.0, cost_hold=6.0)
    assert 'h1' in vs
    reg.close('h1')
    assert reg.judge_all(4, 18.0, 6.0) == {}


def test_progress_lag_channel():
    """时间线掉队通道输入:期望曲线 vs 实际。"""
    h = _hyp()
    assert abs(h.progress_lag(4, 0.1) - 0.2) < 1e-9   # 期望 0.3 实际 0.1
    assert h.progress_lag(4, 0.5) == 0.0       # 超前不掉队
    assert h.progress_lag(5, 0.0) == 0.0       # 非检查点
