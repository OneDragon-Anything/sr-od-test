# -*- coding: utf-8 -*-
"""r421(ADR-0286,批㉓ F3/F4 + 批㉔ F1/F5)锁:sim↔生产三活跃分叉合批。

- 件1(批㉓ F3):xp_progress 真值化——sim 结算处维护(初始 0 / 3 买后
  cur=XP_PER_BUY×3 / 轮末升级按 XP_TO_NEXT_LEVEL 清零结转);
- 件2(批㉓ F4):轮岗概率建模——rotation_probs 翻倍档=基线×2、其余档
  重归一、非法档 None;**事件侧已按勘误重锁**(DESIGN_FINAL_ATTACK
  阻断-2:轮岗=已选环境每阶段 100% 重掷,非 20% 无条件事件)——
  缺省侧锁见本文件 test_sim_rotation_event_never_fires_without_env;
- 件3(批㉔ F1/F5):cap 真值接线——read_deploy_cap_debounced 域防抖
  两态(域外重读一帧;仍域外 None 拒信)、max_units 真值优先/level 兜底、
  sim 宝钻通道参数化(默认 0 = None;prob=1 → cap=level+宝钻数)。
"""
from __future__ import annotations

import random
import types

import pytest

from sr_od.application.currency_war.obs import cw_observation
from sr_od.application.currency_war.data.cw_shop_odds import (
    REFRESH_PROB,
    rotation_probs,
)

from sr_od.application.currency_war.sim.pool import _Pool

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.kernel.cw_state import (
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

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        st = sess.shop_state_frame
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
    # n 4000→1000(2026-09-03 瘦身批,纪律 12):1000 抽下 ±0.05 容差
    # 仍 ≈3σ,种子固定=确定性;语义只需「消费轮岗表」的占比分离。
    n = 1000
    c1_rot = sum(1 for _ in range(n // 5)
                 for c in pool.draw_shop(6, probs=probs) if c.cost == 1)
    draws_rot = n // 5 * 5
    c1_base = sum(1 for _ in range(n // 5)
                  for c in pool.draw_shop(6) if c.cost == 1)
    assert abs(c1_rot / draws_rot - 0.6) < 0.05, c1_rot / draws_rot
    assert abs(c1_base / draws_rot - 0.30) < 0.05, c1_base / draws_rot


class _ProbsRecorder:
    """每段记录 (round, st.refresh_probs, st.deploy_cap, st.level);
    delegate=True 时委托真 MandateV1Strategy(让 level 升到可轮岗档;
    LineStrategy 已随 ADR-0336 删)。"""

    def __init__(self, delegate: bool = False) -> None:
        self.rows: list[tuple[int, object, object, int]] = []
        self._inner = None
        if delegate:
            from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
                MandateV1Strategy,
            )
            self._inner = MandateV1Strategy()

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        if self._inner is not None:
            self._inner.update_target(st, sess, cfg)

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        st = sess.shop_state_frame
        self.rows.append((st.round_num, st.refresh_probs,
                          st.deploy_cap, st.level))
        if self._inner is not None:
            return self._inner.decide_shop_screen(sess, cfg)
        return []


def test_sim_rotation_event_never_fires_without_env() -> None:
    """锁已按勘误重推(01 §4.10 概率表族,DESIGN_FINAL_ATTACK 阻断-2):
    旧「ROTATION_CHANCE=0.2 无条件掷事件」把 replay 观测在场频率误当机制
    概率——机制语义 = 已选轮岗环境后每备战阶段 100% 重掷翻倍档。本锁钉
    勘误后的**缺省侧**:无环境注入局,全部备战阶段概率条恒基线(None)。"""
    rec = _ProbsRecorder(delegate=True)
    simulate_p1(0, pool='fallback', strategy=rec)
    assert rec.rows, '真策略局应有备战段'
    for rn, p, _cap, lv in rec.rows:
        assert p is None, f'未选轮岗环境不得翻倍(rn={rn},lv={lv})'


# --- 件3:cap 真值接线 -----------------------------------------------------


class _FakeCtx:
    def __init__(self) -> None:
        self.controller = types.SimpleNamespace(screenshot=lambda: object())


def _patch_reader(monkeypatch, seq: list[int | None]):
    calls = {'n': 0}

    def fake_read(ctx, screen, level=None):
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


def test_cap_debounce_out_of_domain_equal_pair_accepted(monkeypatch) -> None:
    """ADR-0420:域外但**两帧一致**且 ≤ 绝对上界 13 → 采信(e4972b43
    实拍 diff=5 真实高档,旧域拒信致 6 槽降级跑在 9 格板上)+ 留证。
    d2daffd6 后判据镜像上下两向:cap<level 两帧一致同样采信——cap=level+宝钻
    机制里 cap<level 的唯一现实来源是 level 读错/毒化
    (帧证据 obs_conflict_deploy_paddle__d9f64136:画面 4/4、level 先验 5),
    采真值比拒信退 level 兜底更接近画面事实,不再恒拒。"""
    conflicts: list[tuple] = []
    monkeypatch.setattr(cw_observation, 'obs_conflict',
                        lambda *a, **k: conflicts.append((a, k)))
    calls = _patch_reader(monkeypatch, [13, 13])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 8) == 13
    assert calls['n'] == 2 and len(conflicts) == 1
    assert '采信' in str(conflicts[0][1]), '采信路径必须留证供判读'
    # 两帧一致但超绝对上界(前台4+后台9=13 实拍上限)→ 拒
    calls = _patch_reader(monkeypatch, [15, 15])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 8) is None
    # cap<level 两帧一致 → 采信(下向同判据,level 先验疑毒化;留证注明)
    # 注:[15,15] 拒信路径同样留证,故共 3 条
    calls = _patch_reader(monkeypatch, [3, 3])
    assert cw_observation.read_deploy_cap_debounced(
        _FakeCtx(), object(), 5) == 3
    assert calls['n'] == 2 and len(conflicts) == 3
    assert '采信' in str(conflicts[2][1]) and 'cap<level' in str(conflicts[2][1])


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
