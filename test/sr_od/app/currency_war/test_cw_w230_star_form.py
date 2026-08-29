"""ADR-0401form 星级分量锁。

锁面:
- form 分量断言:star_depth 折算(Σ(star−1) deployed 全量口径)/
  权重端点 ws=0 逐位回旧 form(ADR-0377 形态);
- 校准带内:锚 R1 统计量(案 b 臂)落真值带(存活轮/胜率带);
- P1 锚回归:form 星级分量只辖 plane>=2 → P1 面两臂(ws=0/默认)
  逐位零漂移;
- 敏感性网格键:form_star_weights 维入表。
n 取断言成立最小值(README 纪律);结算链路用 snapshot。
"""
from __future__ import annotations

import dataclasses
import logging

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_sim import P2ReplayEntry
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.data.cw_battle_tables import P2CombatCalib
from sr_od.application.currency_war.kernel import cw_battle_calib as _calib

logging.disable(logging.CRITICAL)


def _st(stars: tuple[int, ...] = (), level: int = 6) -> GameState:
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, 50, 60
    # 仙舟×3 = 达成仙舟体系 → engines=1(绝对锚,同 锁)
    units = [BenchChar(slot=1, char_id='c0', faction='仙舟', star=stars[0] if stars else 1),
             BenchChar(slot=2, char_id='c1', faction='仙舟', star=stars[1] if len(stars) > 1 else 1),
             BenchChar(slot=3, char_id='c2', faction='仙舟', star=stars[2] if len(stars) > 2 else 1)]
    st.deployed = units
    return st


# ---------- form 分量断言 ----------

def test_form_star_component_arithmetic() -> None:
    """form = engines + w·(lv−6) + ws·Σ(star−1):星级折算 + 全量口径。"""
    calib = P2CombatCalib()          # ws=0.5 默认
    base = _calib.p2_form_key(_st(), calib)          # 全 1★ → star_depth=0
    # 一颗 2★:star_depth=1 → form +0.5
    assert abs(_calib.p2_form_key(_st((2, 1, 1)), calib)
               - (base + 0.5)) < 1e-9
    # 一颗 3★:star_depth=2 → form +1.0(线性,3★ 对 2★ 仍有增量)
    assert abs(_calib.p2_form_key(_st((3, 1, 1)), calib)
               - (base + 1.0)) < 1e-9
    # 两颗 2★:star_depth=2
    assert abs(_calib.p2_form_key(_st((2, 2, 1)), calib)
               - (base + 1.0)) < 1e-9
    # win_p 通道:星级 ↑ → 胜率 ↑(因果通道存在的最小断言)
    wp1 = _calib.p2_win_p(_st((1, 1, 1)), 'battle', 1, calib)
    wp2 = _calib.p2_win_p(_st((2, 2, 1)), 'battle', 1, calib)
    assert wp2 > wp1


def test_form_star_weight_zero_returns_old_form() -> None:
    """ws=0 = ADR-0377 旧 form 形态逐位回(engines+level 折算)。"""
    old = dataclasses.replace(P2CombatCalib(), form_star_weight=0.0)
    for stars in ((), (2, 1, 1), (3, 2, 2), (3, 3, 3)):
        st = _st(stars)
        expect = _calib._settle_rung(st) + old.form_level_weight * (
            st.level - old.form_level_base)
        assert abs(_calib.p2_form_key(st, old) - expect) < 1e-9


# ---------- 校准带内(锚 R1 统计量,ADR-0377 同门) ----------

def test_calibration_anchor_r1_in_band() -> None:
    """案 b 臂(真值进场态)锚 R1 主统计量带内:存活轮 ∈ [0,7](真值
    轮数带 [0,6]+1)/聚合胜率 ∈ [0, 0.285](真值边际 0.135+0.15)。
    语料=truth_star.json 标定口径;单 seed 抽样核(全量对拍
    在批报告,本锁防 form 改动把统计量打出带)。"""
    entries = [
        P2ReplayEntry(hp=60, gold=30, level=6,
                      deployed=[{'char_id': '丹恒·饮月', 'faction': '仙舟',
                                 'star': 2, 'position_pref': 'front'}]),
        P2ReplayEntry(hp=35, gold=20, level=6,
                      deployed=[{'char_id': '丹恒·饮月', 'faction': '仙舟',
                                 'star': 1, 'position_pref': 'front'},
                                {'char_id': '停云', 'faction': '仙舟',
                                 'star': 2, 'position_pref': 'front'},
                                {'char_id': '符玄', 'faction': '仙舟',
                                 'star': 1, 'position_pref': 'front'}]),
    ]
    rounds_all, wt, ww = [], 0, 0
    for e in entries:
        for s in range(4):
            r = cw_sim.simulate_p2_replay_entry(e, s, pool='snapshot')
            if r.p2_entered:
                rounds_all.append(r.p2_rounds)
                wt += r.p2_combat_total
                ww += r.p2_combat_wins
    assert rounds_all and 0 <= sum(rounds_all) / len(rounds_all) <= 7
    if wt:
        assert 0.0 <= ww / wt <= 0.285


# ---------- P1 锚回归(form 只辖 plane>=2) ----------

def test_p1_zero_drift_star_form() -> None:
    """ws=0(旧 form)vs 默认 ws=0.5:P1 段逐位零漂移(planes=2 批的
    plane=1 账本行;星级分量只进 P2 战斗结算)。"""
    old = dataclasses.replace(P2CombatCalib(), form_star_weight=0.0)
    for seed in (0, 1, 2):
        ra = cw_sim.simulate_p1(seed, pool='fallback', planes=2,
                                p2_combat=P2CombatCalib())
        rb = cw_sim.simulate_p1(seed, pool='fallback', planes=2,
                                p2_combat=old)
        pa = [row for row in ra.ledger if row.get('plane') == 1]
        pb = [row for row in rb.ledger if row.get('plane') == 1]
        assert pa == pb


# ---------- 敏感性网格键 ----------

def test_sensitivity_grid_star_key() -> None:
    """simulate_p2_sensitivity 网格行带 form_star_weight 键(维入表)。"""
    out = cw_sim.simulate_p2_sensitivity(
        n=2, pool='fallback', planes=2, betas=(0.04,), gammas=(0.02,),
        event_gold_arms=('p1',), form_level_weights=(0.25,),
        form_star_weights=(0.0, 0.5))
    assert len(out['grid']) == 2
    assert {row['form_star_weight'] for row in out['grid']} == {0.0, 0.5}
