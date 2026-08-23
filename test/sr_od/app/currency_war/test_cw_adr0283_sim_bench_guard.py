# -*- coding: utf-8 -*-
"""ADR-0283(sim bench 超容买守卫,批⑰ F6)锁测试。

生产 bench 满 = 硬模态拒买(ADR-0136);sim 执行层 BuyCard 前置
len(bench) ≥ BENCH_CAPACITY 容量检查——超容买跳过 + 计数披露。
"""
from __future__ import annotations


class _GreedyBuyStub:
    """无脑买桩:每段返回 12 张买(逼 bench 满,验证守卫跳过)。"""

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.cw_chars import CHARACTERS
        from sr_od.application.currency_war.cw_state import BuyCard, ShopCard
        name = next(n for n in CHARACTERS if CHARACTERS[n].cost == 1)
        card = ShopCard(x=100, faction='?', name=name, cost=1)
        return [BuyCard(card=card, reason='stub') for _ in range(12)]


def test_sim_bench_capacity_guard() -> None:
    """⑤ bench 满(BENCH_CAPACITY=9)后买被跳过:容量不变式 + 计数披露。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1
    from sr_od.application.currency_war.cw_state import BENCH_CAPACITY
    res = simulate_p1(1, pool='fallback', strategy=_GreedyBuyStub())
    skips = 0
    for row in res.ledger:
        st = row.get('state') or {}
        assert len(st.get('bench') or []) <= BENCH_CAPACITY, \
            f"r{row.get('round_num')} bench 超容(批⑰ F6 回归)"
        skips += (row.get('sim') or {}).get('bench_full_skipped_buys', 0)
    assert skips > 0, '满仓买确实发生且被守卫拦截(桩逼出超容场景)'


def test_sim_batch_discloses_guard_count() -> None:
    """批量报告披露 bench_full_skipped_buys(计数口径存在且 ≥0)。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1_batch
    rep = simulate_p1_batch(10, pool='fallback', seed_base=500,
                            ledger=False, checks=False)
    assert rep['bench_full_skipped_buys'] >= 0
