"""cw_belief(04 号信念层 v0)测试:K2 抗毒化回放 + 表示能力(ADR-0163)。"""
import pytest

from sr_od.application.currency_war.cw_belief import (
    Evidence,
    FieldBelief,
    make_gold_belief,
    make_hp_belief,
)


def test_read_failure_keeps_prior():
    """核心表示能力:读不到(None)不产生证据 → 先验原样保留。
    (M19 hp=100 毒化在此表示下不可表达:没有「默认值」概念。)"""
    b = make_hp_belief()
    b.observe(Evidence('settlement', 84, conf=0.95))       # 结算真值 84
    mode_before = b.mode_value()
    b.decay()   # OCR 失败回合 = 只衰减,不喂默认 100
    assert 70 <= b.mode_value() <= 95                      # 仍在真值邻域,不跳 100
    assert b.mode_value() != 100.0


def test_track_transition_infers_when_unreadable():
    """gold 读不到:跟踪转移继续推断(上回合 40 − 刷新 2 = 38),不是默认 0。"""
    g = make_gold_belief()
    g.observe(Evidence('ocr', 40, conf=0.9))
    g.track_transition(-2)     # 其间只花 2 金刷新
    assert 30 <= g.mode_value() <= 46
    assert g.mode_value() != 0.0


def test_observation_converges():
    """高置信观测收敛到真值邻域;众数投影供 GameState 兼容层。"""
    b = FieldBelief('hp', 0.0, 100.0)
    for _ in range(3):
        b.observe(Evidence('ocr', 62, conf=0.95))
    assert 55 <= b.mode_value() <= 70
    assert b.confidence() > 0.5


def test_confidence_decays_without_confirmation():
    """未确证回合数 ↑ → 置信 ↓(dead-reckoning 漂移 = 置信衰减,自然触发重确证)。"""
    b = make_hp_belief()
    b.observe(Evidence('ocr', 60, conf=0.95))
    c0 = b.confidence()
    for _ in range(8):
        b.decay()
    assert b.confidence() < c0
    assert b.rounds_since_confirm == 8


def test_percentile_and_interval():
    """悲观分位(hp 低置信消费)+ 可信区间(不可逆门 required certainty)。"""
    b = make_hp_belief()
    b.observe(Evidence('ocr', 30, conf=0.6))
    p25 = b.percentile(0.25)
    p75 = b.percentile(0.75)
    assert p25 <= p75
    lo, hi = b.credible_interval(0.9)
    assert lo <= b.mode_value() <= hi


def test_support_hard_clip():
    """sanity bounds = 支撑集硬截断(越界读不进分布:−5 金/200 金都被截在桶边)。"""
    g = make_gold_belief()
    g.observe(Evidence('ocr', 200, conf=0.9))   # 越界误读
    assert g.mode_value() <= 110.0              # 不出支撑集
    g.observe(Evidence('ocr', -5, conf=0.9))
    assert g.mode_value() >= 0.0
