"""模块间集成接缝测试(ADR-0166/0171/0161 documented 接线;本轮落地)。"""
from sr_od.application.currency_war.cw_damage_ledger import DamageLedger
from sr_od.application.currency_war.cw_first_passage import (
    board_tier_of,
    p_win_projection,
)
from sr_od.application.currency_war.cw_line_tribunal import (
    LineHypothesis,
    pool_absence_lr,
    timeline_lag_lr,
    verdict,
)
from sr_od.application.currency_war.cw_pool_belief import PoolBelief


def test_ledger_fold_vs_rescue_pricing():
    """账本×首达:gap×λ_hp 三态计价(fold/保守/rescue;不再手写阈值)。"""
    led = DamageLedger()
    for _ in range(5):
        led.record_throughput(2.0)
    # gap<0(reward 白过)→ fold
    r = led.fold_vs_rescue_pricing('reward', 0, lam_hp=0.1)
    assert r['action'] == 'fold'
    # gap>0(boss 高难度)且 λ_hp 高(临界)→ rescue
    r2 = led.fold_vs_rescue_pricing('boss', 30, lam_hp=0.2)
    assert r2['action'] == 'rescue'
    # gap>0(elite 带难度)但 λ_hp 低(盈余)→ conservative
    r3 = led.fold_vs_rescue_pricing('elite', 3, lam_hp=0.01)
    assert r3['action'] == 'conservative'


def test_pool_absence_channel():
    """池信念→审判 LR:P(n≥k) 高→活证据;低→死证据;无信念→中性。"""
    pb = PoolBelief()
    # 大量缺席观测(目标从不上镜)→ 枯 → LR 高
    for _ in range(150):
        pb.observe_refresh([('他卡A', 3), ('他卡B', 3), ('他卡C', 3), ('他卡D', 3), ('他卡E', 3)], level=7)
    lr_depleted = pool_absence_lr(pb, '姬子·启行', 3)
    assert lr_depleted > 1.0
    # 冷启动(无该卡条目)→ 中性 1.0
    assert pool_absence_lr(PoolBelief(), '姬子·启行', 3) == 1.0
    assert pool_absence_lr(None, 'x', 3) == 1.0


def test_timeline_lag_channel():
    """掉队通道:lag=0 → 中性;lag 增 → LR 单调升(封顶)。"""
    assert timeline_lag_lr(0.0) == 1.0
    a, b, c = timeline_lag_lr(0.2), timeline_lag_lr(0.5), timeline_lag_lr(1.0)
    assert 1.0 < a < b < c
    assert timeline_lag_lr(10.0) < 200.0   # 封顶


def test_channels_feed_verdict_end_to_end():
    """端到端:两通道 LR → 假设账本 → 三态判决(集成主链路)。"""
    pb = PoolBelief()
    for _ in range(150):
        pb.observe_refresh([('他卡A', 3), ('他卡B', 3), ('他卡C', 3), ('他卡D', 3), ('他卡E', 3)], level=7)
    h = LineHypothesis('h1', '列车线', 'commit', checkpoints=[6], deadline=10,
                       expected={6: 0.5})
    h.add_evidence(6, 'pool_absence', '核心缺席', pool_absence_lr(pb, '姬子·启行', 3))
    h.add_evidence(6, 'timeline_lag', '进度掉队', timeline_lag_lr(0.4))
    v = verdict(h, 6, cost_abandon=18.0, cost_hold=6.0)   # K=3
    assert v.action in ('abandon', 'amended')
    assert v.lr > 1.0


def test_pwin_projection_adapter():
    """首达供给方适配:GameState(等级/hp/剩余)→ P(win)一站式(salvage/计价入口)。"""
    strong = p_win_projection(level=8, hp=80, nodes_left=9, rb=0.8)
    weak = p_win_projection(level=4, hp=25, nodes_left=9, rb=0.0)
    assert strong > weak
    assert 0.0 <= weak <= strong <= 1.0
    assert board_tier_of(9, 0.8) == 3
    assert board_tier_of(2, 0.0) == 0
