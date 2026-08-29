# -*- coding: utf-8 -*-
"""批㉞ 检查项锁:decision_v2_supply_label_consistency(供给 vs 标签)。

变异自检纪律:检查器必须被变异锁钉死——生成器掉候选(标签漏接 M1)
与幽灵候选(绕豁免)两向都必须涌现违规,否则检查器是安慰剂。
"""
from __future__ import annotations

import sr_od.application.currency_war.decision_v2.candidates as _cands
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_decision_v2_supply_label_consistency,
)


def test_supply_label_consistency_green() -> None:
    """探针态 0 违规(红 = 直通门标签-候选一致性回归)。"""
    r = check_decision_v2_supply_label_consistency()
    assert r['violations'] == 0, f'{r}'


def test_supply_label_m1_mutation_kill(monkeypatch) -> None:
    """去门变异:生成器丢掉全部买候选 → 标签仍非 None,必须涌现
    M1(标签漏接)违规。"""
    _orig = _cands.generate_candidates

    def _drop_buys(state, session, registry):
        return [c for c in _orig(state, session, registry)
                if c.tag not in ('line_carry', 'line_opportunistic',
                                 'bridge_core', 'engine_seed', 'pair',
                                 'copy', 'bond_fallback', 'carry_gate')]
    monkeypatch.setattr(_cands, 'generate_candidates', _drop_buys)
    r = check_decision_v2_supply_label_consistency()
    assert r['violations'] > 0, (
        '变异未杀:买候选全丢仍 0 违规 = 检查器不消费候选集(安慰剂)')


def test_supply_label_ghost_mutation_kill(monkeypatch) -> None:
    """幽灵候选变异:给本应无标签的散件塞买候选 → 必须涌现
    「无标签但存在买候选」违规(双向不变式)。"""
    from sr_od.application.currency_war.kernel.cw_state import BuyCard

    _orig = _cands.generate_candidates

    def _inject_ghost(state, session, registry):
        out = _orig(state, session, registry)
        # 找一张标签恒 None 的散件(不预设卡名,防门名单演化漂移)
        for card in (state.shop or []):
            if not card.name:
                continue
            if _cands._buy_tag(card, state, session, registry) is None \
                    and not _cands._copy_swap_useless(
                        card, state, session):
                out.append(type(out[0])(
                    action=BuyCard(card, reason='ghost'),
                    tag='pair', source='mutation'))
                break
        return out
    monkeypatch.setattr(_cands, 'generate_candidates', _inject_ghost)
    r = check_decision_v2_supply_label_consistency()
    assert r['violations'] > 0, (
        '变异未杀:幽灵候选不报 = 双向不变式的幽灵侧缺失')
