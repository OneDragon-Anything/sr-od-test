"""cw_decision_bus(30 号决策总线)v0 测试:四类仲裁语义 + 缝 #2/#4 合成裁决 + 零漂移。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_decision_bus import (  # noqa: E402
    Claim,
    arbitrate,
)


def test_evidence_passthrough() -> None:
    """Evidence 无冲突语义:全量并入。"""
    kept, recs = arbitrate([Claim('evidence', 'pool_belief', 'n≥3'),
                            Claim('evidence', 'damage_ledger', 'gap=−2')])
    assert len(kept) == 2 and not recs


def test_goal_priority_seam2() -> None:
    """缝 #2(06 bundle vs 03 DP):同作用域双 Goal → 优先级表裁决(03 node_goal >
    bundle propose 语义:node_goal 70 > bundle 40)且记录双方。"""
    kept, recs = arbitrate([
        Claim('goal', 'horizon.node_goal', 'level@p2', scope='level'),
        Claim('goal', 'bundle.propose', 'hold_gold', scope='level'),
    ], decision_point='p2-r3')
    assert kept[0].source == 'horizon.node_goal'
    assert len(recs) == 1
    assert recs[0].winner == 'horizon.node_goal'
    assert recs[0].losers == ['bundle.propose']
    assert recs[0].rule == 'goal.priority[level]'


def test_veto_safety_seam4() -> None:
    """缝 #4(27 可行性 vs 18 姿态):同 scope 双 Veto → 安全序(state.sanity 最高;
    18 posture 在 27 前不可逆守卫后)。"""
    kept, recs = arbitrate([
        Claim('veto', 'posture.zone', 'risk_pursue', scope='line:DOT', confidence=0.0),
        Claim('veto', 'feasibility.multiplier', '×0.3', scope='line:DOT', confidence=0.3),
    ])
    rec = [r for r in recs if r.rule.startswith('veto.safety')]
    assert rec and rec[0].winner == 'posture.zone'   # 安全序:18 姿态在 27 之前
    # 胜 veto 生效(0.0 硬否决),败者不进生效集
    assert not any(c.source == 'feasibility.multiplier' and c.kind == 'veto' for c in kept)


def test_propose_veto_hard_and_soft() -> None:
    """Propose 过 Veto 域:硬否决(conf=0)剔除并记录;软 veto 乘入置信。"""
    kept, recs = arbitrate([
        Claim('propose', 'prep.candidate', 'buy:X', confidence=0.9),
        Claim('veto', 'state.sanity', 'unread', scope='buy:X', confidence=0.0),
        Claim('propose', 'bundle.propose', 'buy:Y', confidence=0.9),
        Claim('veto', 'feasibility.multiplier', '', scope='buy:Y', confidence=0.5),
    ])
    sources = {c.source: c for c in kept if c.kind == 'propose'}
    assert 'prep.candidate' not in sources          # 硬否决剔除
    assert sources['bundle.propose'].confidence == 0.45   # 软降权乘入
    assert any(r.rule == 'propose.vetoed' for r in recs)


def test_veto_undecidable_escalates() -> None:
    """不可裁决 veto(都不在安全序)→ 升级记录(12 号路由)。"""
    _kept, recs = arbitrate([
        Claim('veto', 'mystery.a', '', scope='x', confidence=0.1),
        Claim('veto', 'mystery.b', '', scope='x', confidence=0.1),
    ])
    rec = [r for r in recs if r.escalated]
    assert rec and rec[0].winner == '(escalated)'


def test_no_claims_zero_drift() -> None:
    """kill-switch:无声明 = 空输出(回退现调用图,零漂移)。"""
    kept, recs = arbitrate([])
    assert kept == [] and recs == []
