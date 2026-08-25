# -*- coding: utf-8 -*-
"""r421(ADR-0286,批㉓ F3/F4 + 批㉔ F1/F5)锁:sim↔生产三活跃分叉合批。

- 件1(批㉓ F3):xp_progress 真值化——sim 结算处维护(初始 0 / 3 买后
  cur=XP_PER_BUY×3 / 轮末升级按 XP_TO_NEXT_LEVEL 清零结转);
- 件2(批㉓ F4):轮岗概率建模——rotation_probs 翻倍档=基线×2、其余档
  重归一、非法档 None;sim 每备战期掷 ROTATION_CHANCE,
  draw_shop 消费轮岗后表(轮岗帧 1 费占比 ≈ 2×基线);
- 件3(批㉔ F1/F5):cap 真值接线——read_deploy_cap_debounced 域防抖
  两态(域外重读一帧;仍域外 None 拒信)、max_units 真值优先/level 兜底、
  sim 宝钻通道参数化(默认 0 = None;prob=1 → cap=level+宝钻数)。
"""
from __future__ import annotations

import random
import types

import pytest

from sr_od.application.currency_war import cw_observation
from sr_od.application.currency_war.cw_shop_odds import (
    REFRESH_PROB,
    ROTATION_CHANCE,
    rotation_probs,
)
from sr_od.application.currency_war.cw_sim import _Pool, simulate_p1
from sr_od.application.currency_war.cw_state import (
    XP_PER_BUY,
    XP_TO_NEXT_LEVEL,
    BuyCard,
    GameState,
)


# --- 件1:xp_progress 真值化 ----------------------------------------------


class _XpRecorder:
    """round1 首段买 3 张,其余段/轮全记录 st 快照后停(returns [])。"""

    def __init__(self) -> None:
        self.snapshots: list[tuple[int, tuple[int, int]]] = []
        self._bought = False

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        self.snapshots.append((st.round_num, st.xp_progress))
        if st.round_num == 1 and not self._bought and st.shop:
            self._bought = True
            return [BuyCard(card=c, reason='stub') for c in st.shop[:3]]
        return []


def test_sim_xp_progress_three_states() -> None:
    """三态:开局 (0, 4@lv3) → 3 买后 cur=12 → 轮末升级结转 (2, 20@lv5)。"""
    rec = _XpRecorder()
    simulate_p1(0, pool='fallback', strategy=rec)
    lv3_need = XP_TO_NEXT_LEVEL[3]
    assert rec.snapshots[0] == (1, (0, lv3_need)), '开局 xp 真值应为 (0, 当前级门槛)'
    after_buys = next(xp for rn, xp in rec.snapshots
                      if rn == 1 and xp[0] == 3 * XP_PER_BUY)
    assert after_buys == (12, lv3_need), '3 买后 xp_progress=12(锁)'
    # 轮末升级:lv3→4(need4)→5(need6),12−4−6=2 结转 → (2, 20)
    r2 = next(xp for rn, xp in rec.snapshots if rn == 2)
    assert r2 == (12 - 4 - 6, XP_TO_NEXT_LEVEL[5]), '升级清零结转按 XP_TO_NEXT_LEVEL'


# --- 件2:轮岗概率建模 -----------------------------------------------------


def test_rotation_probs_doubled_tier_is_2x_baseline() -> None:
    """锁:轮岗帧的档概率 = 基线×2;其余档重归一(和=1)。"""
    p = rotation_probs(6, 1)
    assert p is not None
    assert p[1] == pytest.approx(2 * REFRESH_PROB[6][1]), '翻倍档 = 基线×2'
    assert sum(p.values()) == pytest.approx(1.0), '概率表和 = 1'
    # 实读对拍邻域:lv6 1费翻倍 → 60/23/14/3(实读整数 60/22/15/3)
    assert p[1] == pytest.approx(0.6)
    assert abs(p[2] - 0.22) < 0.02 and abs(p[3] - 0.15) < 0.02


def test_rotation_probs_invalid_tiers_none() -> None:
    """基线 p=0(该级不出此费)或 2p≥1(lv1-3 纯 1 费,无剩余质量)→ None。"""
    assert rotation_probs(3, 1) is None      # p=1.0,翻倍不可能
    assert rotation_probs(6, 6) is None      # 该级不出 6 费(p=0)
    assert rotation_probs(1, 2) is None


def test_draw_shop_consumes_rotation_table() -> None:
    """draw_shop 消费轮岗后表:lv6 1费翻倍 → 1 费占比 ≈0.6 vs 基线 ≈0.30。"""
    probs = rotation_probs(6, 1)
    rng = random.Random(42)
    pool = _Pool(rng)
    n = 4000
    c1_rot = sum(1 for _ in range(n // 5)
                 for c in pool.draw_shop(6, probs=probs) if c.cost == 1)
    draws_rot = n // 5 * 5
    c1_base = sum(1 for _ in range(n // 5)
                  for c in pool.draw_shop(6) if c.cost == 1)
    assert abs(c1_rot / draws_rot - 0.6) < 0.05, c1_rot / draws_rot
    assert abs(c1_base / draws_rot - 0.30) < 0.05, c1_base / draws_rot


class _ProbsRecorder:
    """每段记录 (round, st.refresh_probs, st.deploy_cap, st.level);
    delegate=True 时委托真 DecisionV2Strategy(让 level 升到可轮岗档;
    LineStrategy 已随 ADR-0336 删)。"""

    def __init__(self, delegate: bool = False) -> None:
        self.rows: list[tuple[int, object, object, int]] = []
        self._inner = None
        if delegate:
            from sr_od.application.currency_war.decision_v2.strategy import (
                DecisionV2Strategy,
            )
            self._inner = DecisionV2Strategy()

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        if self._inner is not None:
            self._inner.update_target(st, sess, cfg)

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        self.rows.append((st.round_num, st.refresh_probs,
                          st.deploy_cap, st.level))
        if self._inner is not None:
            return self._inner.decide_prep(st, sess, cfg)
        return []


def test_sim_rotation_event_writes_truth_shaped_probs() -> None:
    """sim 轮岗事件:掷中帧 probs = 完整翻倍表(某档 = 该帧 level 基线×2),
    未掷中帧 None(基线);真策略(等级升到 lv≥5 可翻倍档)下必现轮岗帧。

    注:lv1-3 基线纯 1 费(p=1.0)→ 无可翻倍档,轮岗结构性不可能
    (与生产「低级帧无轮岗」同态);掷中但无可翻倍档 → None(退基线)。"""
    rows: list[tuple[int, object, int]] = []   # (round, probs, level)
    for seed in range(6):
        rec = _ProbsRecorder(delegate=True)
        simulate_p1(seed, pool='fallback', strategy=rec)
        rows.extend((rn, p, lv) for rn, p, _cap, lv in rec.rows)
    lv_ge5 = [(rn, p, lv) for rn, p, lv in rows if lv >= 5]
    rot = [(rn, p, lv) for rn, p, lv in lv_ge5 if p is not None]
    assert rot, '真策略多局 @20%×lv≥5 帧无轮岗帧(事件未接线?)'
    for rn, p, lv in rot:
        base = REFRESH_PROB.get(lv, {})
        assert any(abs(v - 2 * base.get(k, 0)) < 1e-9
                   for k, v in p.items()), (rn, lv, p)
        assert sum(p.values()) == pytest.approx(1.0)
    assert any(p is None for _rn, p, _lv in lv_ge5), '未掷中帧应为 None(退基线)'
    assert 0 < len(rot) / len(lv_ge5) < 0.5, '轮岗频率应在 20% 量级(非全帧/零帧)'
    assert all(p is None for _rn, p, lv in rows if lv < 4), \
        'lv<4(纯 1 费)无可翻倍档 → 恒 None'


# --- 件3:cap 真值接线 -----------------------------------------------------


class _FakeCtx:
    def __init__(self) -> None:
        self.controller = types.SimpleNamespace(screenshot=lambda: object())


def _patch_reader(monkeypatch, seq: list[int | None]):
    calls = {'n': 0}

    def fake_read(ctx, screen):
        i = min(calls['n'], len(seq) - 1)
        calls['n'] += 1
        return seq[i]

    monkeypatch.setattr(cw_observation, 'read_deploy_cap', fake_read)
    return calls


def test_cap_debounce_accepts_in_domain(monkeypatch) -> None:
    """域内(cap=level / level+1 / level+2)直采,不重读。"""
    for cap in (5, 6, 7):
        calls = _patch_reader(monkeypatch, [cap])
        out = cw_observation.read_deploy_cap_debounced(_FakeCtx(), object(), 5)
        assert out == cap
        assert calls['n'] == 1, '域内不应重读'


def test_cap_debounce_reread_recovers_then_rejects(monkeypatch) -> None:
    """域外(cap<level / |diff|>2):重读一帧——重读入域采重读值;
    仍域外 → None 拒信 + obs_conflict 留证。"""
    conflicts: list[tuple] = []
    monkeypatch.setattr(cw_observation, 'obs_conflict',
                        lambda *a, **k: conflicts.append(a))
    # ① cap<level 首读,重读入域 → 采重读值
    calls = _patch_reader(monkeypatch, [3, 5])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 5) == 5
    assert calls['n'] == 2 and not conflicts
    # ② 首读域外(cap=level+3),重读仍域外 → None + 留证
    calls = _patch_reader(monkeypatch, [8, 3])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 5) is None
    assert calls['n'] == 2 and len(conflicts) == 1
    # ③ 读不到(None)→ 原样 None,不重读
    calls = _patch_reader(monkeypatch, [None])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 5) is None
    assert calls['n'] == 1


def test_max_units_deploy_cap_priority() -> None:
    """max_units:deploy_cap 真值优先(≥level 才信),level 兜底,封顶 10。"""
    assert GameState(level=5, deploy_cap=7).max_units() == 7
    assert GameState(level=5, deploy_cap=12).max_units() == 10   # 封顶
    assert GameState(level=5, deploy_cap=None).max_units() == 5  # 兜底
    assert GameState(level=5, deploy_cap=3).max_units() == 5     # cap<level 不可信


def test_sim_diamond_cap_channel_parameterized() -> None:
    """宝钻通道参数化:默认 0 → deploy_cap 恒 None(与旧树同态);
    prob=1 → 每备战期 +1,cap = level + 宝钻数(>level)。"""
    rec = _ProbsRecorder()
    simulate_p1(1, pool='fallback', strategy=rec)
    assert all(cap is None for _rn, _p, cap, _lv in rec.rows), \
        '默认 diamond_cap_prob=0 不应注入'
    rec2 = _ProbsRecorder()
    simulate_p1(1, pool='fallback', strategy=rec2, diamond_cap_prob=1.0)
    rows2 = [(cap, lv) for _rn, _p, cap, lv in rec2.rows]
    assert rows2 and all(cap is not None and lv < cap <= lv + 9
                         for cap, lv in rows2), 'prob=1 → cap=level+宝钻数'
    assert GameState(level=rows2[0][1], deploy_cap=rows2[0][0]).max_units() \
        == min(rows2[0][0], 10), 'max_units 消费宝钻真值'
