"""血预算停手·停升级线锁(设计件 12 §3.1/§2.3-P1-b;ADR-0448)。

锁面:
- 停线数值单一源:discipline.p1/p2_levelup_stop_hp 推导值(21/11)
  与 cw_sim_checks 镜像常量双向一致(镜像漂移锁);
- 谓词辖域:P1/P2 各自线内拒、线外放;唯一豁免=plane_last_battle
  ALL IN 窗(豁免反例锁);开关 off=零辖域;
- 接线三面:arbiter 'blood_budget_stop' 约束拒付(计数/原因落
  RejectReason)/ remediation 稳态多击组整组拒发 / 拒付计数进
  session.v3_blood_budget_rejects;
- 段级检查:seg_p2/p1_blood_budget_levelup 对违规帧行出事件、
  ALL IN 豁免帧不出;
- sim 账本披露键存在性(单局冒烟,不锁分布)。

判据出处:设计件 12 §3.1(P2 停升级线=ceil(d·vd_p2_loss)=21)/
§2.3-P1-b(P1 停追级线=ceil(d·L_c(rung2))=11,完备性条款)/
§5.2-5.3 接缝(独立谓词 AND、非第五覆盖态、ALL IN 让位)。
"""
from __future__ import annotations

import dataclasses
import logging

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    LevelUp,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_sim_checks import (
    _P1_LEVELUP_STOP_HP,
    _P2_LEVELUP_STOP_HP,
    seg_check_p1_blood_budget_levelup,
    seg_check_p2_blood_budget_levelup,
)
from sr_od.application.currency_war.decision_v2.arbiter import (
    _check_constraint,
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    blood_budget_levelup_blocked,
    p1_levelup_stop_hp,
    p2_levelup_stop_hp,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.remediation import (
    steady_state_levelup_group,
)

logging.disable(logging.CRITICAL)


def _p2_state(hp: int = 16, round_num: int = 3, node: str = 'battle',
              gold: int = 100) -> GameState:
    """P2 备战帧(⑳+1 型:hp 危机段;默认 hp=16<21 追级泵病灶态)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _lv_cand() -> Candidate:
    return Candidate(action=LevelUp(cost=4), tag='levelup', source='shop')


def _allin_sess() -> StrategySession:
    """带 P2 槽序表(7 槽)的 session——plane_last_battle 真值源。"""
    s = StrategySession()
    s.plane_node_table = ['battle'] * 7
    return s


# ---------- 停线数值:单一源推导 + 镜像双向锁 ----------

def test_stop_lines_derive_from_registry() -> None:
    """P2=ceil(1×20.05)=21 / P1=ceil(1×10.58)=11(设计件 12 §6)。"""
    assert p2_levelup_stop_hp(DEFAULT_REGISTRY) == 21
    assert p1_levelup_stop_hp(DEFAULT_REGISTRY) == 11


def test_mirror_constants_match_discipline() -> None:
    """cw_sim_checks 镜像常量 ↔ discipline 单一源双向锁(漂移即红)。"""
    assert _P2_LEVELUP_STOP_HP == p2_levelup_stop_hp(DEFAULT_REGISTRY)
    assert _P1_LEVELUP_STOP_HP == p1_levelup_stop_hp(DEFAULT_REGISTRY)


# ---------- 谓词辖域 ----------

def test_predicate_domain() -> None:
    """线内拒/线外放:P2 hp21 拒、hp22 放;P1 hp11 拒、hp12 放。"""
    sess = StrategySession()
    assert blood_budget_levelup_blocked(_p2_state(hp=21), sess,
                                        DEFAULT_REGISTRY)
    assert not blood_budget_levelup_blocked(_p2_state(hp=22), sess,
                                            DEFAULT_REGISTRY)
    p1 = _p2_state(hp=11)
    p1.plane = 1
    assert blood_budget_levelup_blocked(p1, sess, DEFAULT_REGISTRY)
    p1_ok = _p2_state(hp=12)
    p1_ok.plane = 1
    assert not blood_budget_levelup_blocked(p1_ok, sess, DEFAULT_REGISTRY)


def test_predicate_allin_exempt_counterexample() -> None:
    """ALL IN 豁免反例:P2 r7 boss 帧 hp=16(<21)不停手(位面末
    ALL IN 清零窗,停手让位;[18])。同帧非位面末(r3 boss 窗)照拒。"""
    allin = _p2_state(hp=16, round_num=7, node='boss')
    assert blood_budget_levelup_blocked(allin, _allin_sess(),
                                        DEFAULT_REGISTRY) is False
    not_last = _p2_state(hp=16, round_num=3, node='boss')
    assert blood_budget_levelup_blocked(not_last, _allin_sess(),
                                        DEFAULT_REGISTRY)


def test_predicate_flag_off_zero_scope() -> None:
    """开关 off=A/B 对照臂:同帧不辖(A/B 基线臂注入面)。"""
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  blood_budget_stop_enabled=False)
    assert not blood_budget_levelup_blocked(_p2_state(hp=16),
                                            StrategySession(), reg_off)


# ---------- 接线:约束拒付 / 稳态组 / 计数披露 ----------

def test_constraint_rejects_with_reason_and_counter() -> None:
    """arbiter 约束拒付:RejectReason 带血预算停手原因 + session 计数+1。"""
    sess = StrategySession()
    st = _p2_state(hp=16)
    r = _check_constraint('blood_budget_stop', _lv_cand(), st, st, sess,
                          DEFAULT_REGISTRY)
    assert r is not None and '血预算停手拒' in r.describe
    assert sess.v3_blood_budget_rejects == 1
    # 线外帧:本约束放行(None=交给后续约束链)
    sess2 = StrategySession()
    assert _check_constraint('blood_budget_stop', _lv_cand(),
                             _p2_state(hp=30), _p2_state(hp=30), sess2,
                             DEFAULT_REGISTRY) is None
    assert sess2.v3_blood_budget_rejects == 0


def test_arbitrate_end_to_end_no_levelup_in_stop_band() -> None:
    """端到端:血线内帧的升级候选不产 LevelUp 动作(ALL IN 外)。"""
    sess = StrategySession()
    st = _p2_state(hp=16)
    res = arbitrate([(_lv_cand(), 5.0, {})], st, sess, DEFAULT_REGISTRY)
    assert not [a for a in res.actions
                if isinstance(a, LevelUp)]
    assert any('blood_budget_stop' in (row.get('reject') or '')
               for row in res.log)


def test_steady_group_blocked_in_stop_band() -> None:
    """稳态多击组整组拒发 + 拒付计数(⑳+1「血线 16 追级泵 6 次」
    的形态反转:同帧稳态组=0 组)。"""
    sess = StrategySession()
    st = _p2_state(hp=16)
    st.deployed = [BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                   for i in range(6)]
    st.bench[0] = BenchChar(slot=1, char_id='希儿', faction='量子')
    st.xp_progress = (16, 40)
    assert steady_state_levelup_group(st.copy(), st, sess,
                                      DEFAULT_REGISTRY) == []
    assert sess.v3_blood_budget_rejects == 1
    # ALL IN 窗豁免:同构造在 r7 boss 帧照发(豁免面)
    sess2 = _allin_sess()
    st2 = _p2_state(hp=16, round_num=7, node='boss')
    st2.deployed = [BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                    for i in range(6)]
    st2.bench[0] = BenchChar(slot=1, char_id='希儿', faction='量子')
    st2.xp_progress = (16, 40)
    acts = steady_state_levelup_group(st2.copy(), st2, sess2,
                                      DEFAULT_REGISTRY)
    assert len(acts) == 6
    assert sess2.v3_blood_budget_rejects == 0


# ---------- 段级检查 ----------

def _row(plane: int, hp: int, rn: int, node: str,
         levelups: int) -> dict:
    return {
        'plane': plane, 'round_num': rn, 'hp': hp,
        'sim': {'node': node},
        'actions': ([{'__type__': 'LevelUp', 'cost': 4}] * levelups),
    }


def test_seg_checks_violation_and_allin_exempt() -> None:
    """违规帧出事件;ALL IN 豁免帧与线外帧不出(反例内嵌)。

    hp 口径=决策帧(=上一行结算 hp):违规行的**前一行** hp 在线内。"""
    rows_p2 = [
        _row(2, 35, 1, 'battle', 0),    # 局首:决策 hp=开局,不出事件
        _row(2, 18, 2, 'battle', 2),    # 决策 hp=35(线外)→ 不出
        _row(2, 10, 3, 'battle', 1),    # 决策 hp=18≤21 → 违规事件
        _row(2, 5, 7, 'boss', 6),       # 决策 hp=10 但 ALL IN 帧 → 豁免
        _row(2, 30, 8, 'battle', 0),    # 无升级:不出事件
    ]
    ev = seg_check_p2_blood_budget_levelup(rows_p2)
    assert len(ev) == 1 and ev[0]['round_num'] == 3 and ev[0]['hp'] == 18
    rows_p1 = [
        _row(1, 12, 4, 'battle', 0),
        _row(1, 10, 5, 'battle', 1),    # 决策 hp=12(线外)→ 不出
        _row(1, 9, 6, 'battle', 1),     # 决策 hp=10≤11 → 违规事件
        _row(1, 8, 7, 'battle', 0),     # 无升级
        _row(1, 7, 9, 'boss', 2),       # ALL IN 豁免(P1 r9)
    ]
    ev1 = seg_check_p1_blood_budget_levelup(rows_p1)
    assert len(ev1) == 1 and ev1[0]['plane'] == 1 and ev1[0]['hp'] == 10


# ---------- sim 账本披露键(单局冒烟,不锁分布) ----------

def test_sim_ledger_discloses_reject_key() -> None:
    """账本行 sim.blood_budget_levelup_rejects 键存在(批量聚合的
    数据源;单局冒烟,pool='fallback' 免快照依赖)。"""
    from sr_od.application.currency_war import cw_sim
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert r.ledger
    for row in r.ledger:
        assert 'blood_budget_levelup_rejects' in (row.get('sim') or {})
