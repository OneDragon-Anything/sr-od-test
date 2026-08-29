# -*- coding: utf-8 -*-
"""轮岗/概率条真值接线测试(r77)。

锁三件事:
1. parse_prob_bar:OCR 文本 → {费用:概率}(5 数和≈100%);坏输入 → None。
2. boosted_cost_tier:观测 vs 基线判翻倍档(60/22/15/3/0@lv6 → 1费)。
3. _sample_cost 覆盖:probs_override 生效(轮岗局采样分布 ≈ 观测,非基线)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'src'))

from sr_od.application.currency_war.strategy_v1.cw_plan import _sample_cost
from sr_od.application.currency_war.data.cw_shop_odds import (
    REFRESH_PROB,
    boosted_cost_tier,
    parse_prob_bar,
)


def test_parse_prob_bar_valid():
    texts = ['60%', '■22%', '■15%', '■3%', '■0%']   # 实读轮岗局(lv6 1费翻倍)
    assert parse_prob_bar(texts) == {1: 0.6, 2: 0.22, 3: 0.15, 4: 0.03, 5: 0.0}


def test_parse_prob_bar_rejects_bad():
    assert parse_prob_bar(['60%', '22%']) is None          # 不足 5 档
    assert parse_prob_bar([]) is None
    assert parse_prob_bar(['40%', '30%', '40%', '10%', '5%']) is None   # 和≠100


def test_boosted_cost_tier_lungang():
    obs = {1: 0.6, 2: 0.22, 3: 0.15, 4: 0.03, 5: 0.0}
    assert boosted_cost_tier(obs, 6) == 1      # 0.6/0.3 = 2.0
    assert boosted_cost_tier(REFRESH_PROB[6], 6) is None   # 基线无翻倍档


def test_sample_cost_override_distribution():
    """轮岗局 override 采样:1费占比应显著高于基线(60% vs 30%)。"""
    import random
    rng = random.Random(42)
    override = {1: 0.6, 2: 0.22, 3: 0.15, 4: 0.03, 5: 0.0}
    n = 2000
    c1 = sum(1 for _ in range(n) if _sample_cost(6, rng, probs_override=override) == 1)
    assert abs(c1 / n - 0.6) < 0.05, c1 / n
    c1_base = sum(1 for _ in range(n) if _sample_cost(6, rng) == 1)
    assert abs(c1_base / n - 0.30) < 0.05, c1_base / n
    assert c1 > c1_base * 1.5   # 轮岗翻倍 → 采样分布显著偏移
