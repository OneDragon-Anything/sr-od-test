# -*- coding: utf-8 -*-
"""r420(ADR-0284/0285,批㉒ F1/F3/F5 + 批㉑ F1/F3 + 批㉒ F4)锁:

- 件1(ADR-0284):商店槽消费语义——买走即下架(生产一致)、
  刷新全 5 槽重抽、幻影再买归 0、池 take 地板如实记;
  检查项 shop_slot_consumption / phantom_rebuy_disclosure 双向锁;
- 件2(ADR-0285):carry_gate_bench_deadlock 金足判据 floor 对齐
  (wave_gold−cost≥floor 才算 miss 可救;floor 边界两态);
- 件3(ADR-0285):sim_endgold_calib 守卫残金双口径(净滞留 =
  末金 − bench_full_skipped_gold 折算);
- 件4(ADR-0285):ab_resolution_floor(配对差 95% 底,差值小于底
  = 噪声带内)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war.cw_sim import (
    _Pool,
    simulate_p1,
    simulate_p1_ab,
    simulate_p1_batch,
)


# --- 件1:槽消费语义 -------------------------------------------------------


def test_buy_consumes_slot_waves_all_five() -> None:
    """波内同名买入 ≤ 供给槽(检查过);每波恒 5 槽(offer 与
    refresh 同为全 5 槽重抽——批㉒ F1 的「刷新现行?」查证锁)。"""
    for seed in (0, 1, 2):
        r = simulate_p1(seed, pool='fallback')
        assert not chk.check_shop_slot_consumption(r.ledger), \
            f'seed{seed}: 波内买入超供给(槽消费缺失)'
        for row in r.ledger:
            for w in (row['sim'].get('shop_waves') or []):
                assert len(w['cards']) == 5, (
                    f"seed{seed} r{row['round_num']} {w['event']} 波 "
                    f"{len(w['cards'])} 槽 ≠ 5(全 5 槽重抽)")


def test_phantom_rebuy_and_pool_floor_zero_real_strategy() -> None:
    """真策略批次:幻影再买归 0(批㉒ F1 修复验收)+ 池地板
    零命中(批㉒ F5:槽消费落地后池超卖不可达)。"""
    rep = simulate_p1_batch(20, seed_base=0, pool='fallback',
                            ledger=False, checks=False)
    assert rep['phantom_rebuys'] == 0, '幻影再买未归 0(ADR-0284)'
    assert rep['pool_floor_hits'] == 0, '池 take 地板被命中(池守恒破)'
    assert rep['bench_full_skipped_gold'] >= 0   # 口径存在且披露


class _DoubleBuyStub:
    """同段重复提案同一店内卡:第 2 笔应命中已消费槽 → 跳过 +
    披露计数(金/池不消费)。"""

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.cw_state import BuyCard
        if not st.shop:
            return []
        return [BuyCard(card=st.shop[0], reason='stub')] * 2


def test_consumed_slot_rebuy_skipped_and_disclosed() -> None:
    """已消费槽再买:不执行(金只扣一次)+ 入账本 phantom_rebuys;
    账本守恒不破(跳过的买不产生金流)。"""
    r = simulate_p1(1, pool='fallback', strategy=_DoubleBuyStub())
    phantom = sum((row['sim'].get('phantom_rebuys') or 0)
                  for row in r.ledger)
    assert phantom > 0, '重复提案应计入幻影再买披露'
    # 守恒断言:跳过的买不产生金流(金只扣一次)
    assert not chk.check_ledger_consistency(r.ledger), \
        '已消费槽再买被跳过后金流守恒不应破'


class _SyntheticCardStub:
    """店外构造卡(x=100):legacy 执行路径(ADR-0283 桩兼容)+ 披露。"""

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.cw_state import BuyCard, ShopCard
        name = next(n for n in CHARACTERS if CHARACTERS[n].cost == 1)
        return [BuyCard(card=ShopCard(x=100, faction='?', name=name,
                                      cost=1), reason='stub')] * 12


def test_out_of_shop_synthetic_executes_with_disclosure() -> None:
    """店外构造卡(测试桩):仍执行(bench 守卫测试可达,ADR-0283
    桩兼容)但计入披露——真批次出现即回归(检查项辖)。"""
    r = simulate_p1(1, pool='fallback', strategy=_SyntheticCardStub())
    buys = sum(1 for row in r.ledger for a in row['actions']
               if a['__type__'] == 'BuyCard')
    assert buys > 0, '店外构造(桩)应走 legacy 执行'
    assert r.phantom_rebuys > 0, '店外构造必须披露(非静默)'


def test_check_shop_slot_consumption_bidirectional() -> None:
    """坏:波内同名买 2 > 供给 1 → 报;好:≤ 供给 → 过;刷新切波
    后供给重置(跨波同名各买 1 合法)。"""
    def _row(actions, cards):
        return {'plane': 1, 'round_num': 5, 'actions': actions,
                'sim': {'shop_waves': [
                    {'event': 'offer', 'gold': 30, 'cards': cards}]}}
    buy = lambda: {'__type__': 'BuyCard',   # noqa: E731
                   'card': {'name': 'A', 'cost': 1}, 'reason': 'line'}
    bad = _row([buy(), buy()], [{'name': 'A', 'cost': 1}])
    assert chk.check_shop_slot_consumption([bad]), '超供给买入未报'
    good = _row([buy()], [{'name': 'A', 'cost': 1}])
    assert not chk.check_shop_slot_consumption([good])
    # 刷新切波:两波各供 1 份 A,各买 1 → 合法
    two_waves = {'plane': 1, 'round_num': 5,
                 'actions': [buy(),
                             {'__type__': 'RefreshShop', 'cost': 2},
                             buy()],
                 'sim': {'shop_waves': [
                     {'event': 'offer', 'gold': 30,
                      'cards': [{'name': 'A', 'cost': 1}]},
                     {'event': 'refresh', 'gold': 28,
                      'cards': [{'name': 'A', 'cost': 1}]}]}}
    assert not chk.check_shop_slot_consumption([two_waves]), \
        '刷新后供给重置,跨波同名各买 1 合法'
    assert 'shop_slot_consumption' in chk._BATCH_CHECKS


def test_check_phantom_rebuy_disclosure_bidirectional() -> None:
    """坏:sim.phantom_rebuys>0 → 报;好:=0 → 过;登记进批量集。"""
    bad = [{'plane': 1, 'round_num': 3,
            'sim': {'phantom_rebuys': 2}}]
    assert chk.check_phantom_rebuy_disclosure(bad)
    good = [{'plane': 1, 'round_num': 3, 'sim': {}}]
    assert not chk.check_phantom_rebuy_disclosure(good)
    assert 'phantom_rebuy_disclosure' in chk._BATCH_CHECKS


def test_pool_take_floor_hits_recorded() -> None:
    """批㉒ F5:take 逼近池地板如实记——超容量 take 计数(旧
    max(0,…) 静默吞)。"""
    p = _Pool(random.Random(7))
    name = next(iter(p.copies))
    cap = p.copies[name]
    for _ in range(cap):
        p.take(name)
    assert p.floor_hits == 0 and p.copies[name] == 0
    p.take(name)   # 第 cap+1 次:地板
    assert p.floor_hits == 1, '地板命中未记(静默吞回归)'
    assert p.copies[name] == 0


# --- 件2:carry 门 floor 对齐(批㉑ F1) ----------------------------------
# (check_carry_gate_bench_deadlock 随 v1 线库检查器删除,ADR-0336;
# carry 腾位门语义由 decision_v2 discipline 层4 承载,对应锁在
# test_cw_w35 纪律族)

# --- 件3:endgold 双口径(批㉑ F3/F5) ------------------------------------


def test_endgold_dual_criterion_guard_residual() -> None:
    """守卫残金口径(锚已随 economy v2 重锚为 45.1,ADR-0447):
    末金 90 含 45 守卫拦截折算 → 净滞留 45(总口径 2.0 违规 vs 净
    口径 ≈1.0)→ 净口径不违规;纯策略滞留(零拦截)90 → 双口径同违规。"""
    def _game(end_gold: int, skipped_gold: int) -> list[dict]:
        return [{
            'plane': 1, 'round_num': 9, 'gold': end_gold,
            'sim': {'bench_full_skipped_gold': skipped_gold},
        }]
    rep = chk.check_sim_endgold_calib([_game(90, 45)])
    assert rep['violations'] == 0, '净口径 45/45.1 ≤1.5,不应违规'
    assert rep['ratio'] == round(90 / 45.1, 2), '总口径并行披露(90/45.1)'
    assert rep['net_ratio'] == round(45 / 45.1, 2), '净口径 = (90−45)/45.1'
    assert rep['guard_skipped_gold_avg'] == 45.0
    rep2 = chk.check_sim_endgold_calib([_game(90, 0)])
    assert rep2['violations'] == 1, '纯策略滞留 90 → 违规(漂移哨兵语义)'


# --- 件4:A/B 分辨率底(批㉒ F4) -----------------------------------------


def test_ab_resolution_floor_noise_band() -> None:
    """差值小于 95% 底 → 噪声带内(不得叙述方向);大差值 → 可叙述。"""
    b = [30.0 for _ in range(100)]
    a = [30.0 + (5.0 if i % 2 else -5.0) for i in range(100)]
    rep = chk.check_ab_resolution_floor(a, b)
    assert rep['noise_band'] is True, \
        'mean 0(±5 对称抖动)必在噪声带内'
    assert rep['n'] == 100 and rep['ci95_floor'] > 0
    big = chk.check_ab_resolution_floor([30.0] * 100, [20.0] * 100)
    assert big['noise_band'] is False and big['ci95_floor'] == 0.0, \
        '恒定差 10(sd=0,底 0)超过底,可叙述方向'
    tiny = chk.check_ab_resolution_floor([1.0], [2.0])
    assert tiny['n'] == 1 and '不判' in (tiny.get('note') or '')


def test_simulate_p1_ab_report_shape() -> None:
    """simulate_p1_ab 报告附分辨率底(件4 落地接线)。"""
    rep = simulate_p1_ab(8, pool='fallback', seed_base=0)
    assert set(rep) >= {'n', 'avg_hp_a', 'avg_hp_b', 'ab_resolution_floor'}
    assert rep['ab_resolution_floor']['n'] == 8
