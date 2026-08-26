"""W227/ADR-0400:P1 末窗承接门(设计件 08 §4.2 Phase 1)单帧锁。

锁面(设计件 §4.1 判据 3 的结构面;分布面=A/B sim 批):
- 缺口判据窗口/辖域:r>=handoff_gate_min_round ∧ P1 ∧ 开——非末窗/关/
  达标恒 0(零漂移门的结构前提);
- formed_stop 承接维(挂载点 a):run 28/31 型构造局(成型低血,末窗
  承接档位未达标)→ 不停手继续投资(买候选保留);关臂照旧停手;
- EV 承接缺口项(挂载点 b):末窗兜底成型全 1★ 板的跨档买,基线臂
  EV≤0 拒、门臂 V+bonus 放行(auth trace 带 handoff_gap);非末窗
  同帧同拒(零漂移);
- sim 侧:账本 handoff_gap 字段存在;A/B 同 seed 非末窗逐位零漂移。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import logging
from dataclasses import replace

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    _check_constraint,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
    formed_stop_active,
)
from sr_od.application.currency_war.decision_v2.handoff import (
    handoff_gate_gap,
)
from sr_od.application.currency_war.decision_v2.phase import form_ok
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

#: 默认关(ADR-0400 A/B 裁决):行为臂全部显式开,基线臂=DEFAULT
_GATE_OFF = DEFAULT_REGISTRY
_GATE_ON = replace(DEFAULT_REGISTRY, handoff_gate_enabled=True)


def _card(name: str, cost: int, faction: str = '持续伤害') -> ShopCard:
    return ShopCard(name=name, faction=faction, cost=cost, x=0, star=1)


def _locked_formed_frame(**kw) -> GameState:
    """run 28/31 型构造帧:DOT队锁定成型(核心卡芙卡上场 2★+桑博补
    DOT 引擎),P1 末窗,低血(hp=15 → hp 维归零,总档 0=承接缺口 1)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5, 'hp': 15,
        'board': dict(comp.form_tiers),
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2),
                     BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                               star=1)],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


def _fallback_formed_frame(**kw) -> GameState:
    """兜底成型帧(未锁):仙舟3+DOT2 两体系(engines=2,form_ok 兜底
    判据过)但全 1★(core2=0 → 板面维归零);hp 健康 → 缺口走板面维
    (run 26 型星级深度主罚维)。"""
    base = {
        'plane': 1, 'round_num': 8, 'gold': 53, 'level': 5, 'hp': 40,
        'board': {},
        'deployed': [BenchChar(slot=i, char_id=n, faction='仙舟',
                               star=1)
                     for i, n in enumerate(
                         ['藿藿', '丹恒·饮月', '爻光', '桑博', '卡芙卡'])],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked() -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s.v3_mode = 'economy'
    return s


# ---------- ① 缺口判据窗口/辖域 ----------

def test_gate_gap_window_and_scope() -> None:
    """r7(非末窗)/关臂恒 0;末窗低血成型帧缺口 1;达标帧 0。"""
    sess = _sess_locked()
    st = _locked_formed_frame()
    assert form_ok(st, sess, _GATE_ON) is True   # 前置:成型谓词过
    assert handoff_gate_gap(st, sess, _GATE_ON) == 1
    # 非末窗(r7):不辖(零漂移边界)
    assert handoff_gate_gap(_locked_formed_frame(round_num=7), sess,
                            DEFAULT_REGISTRY) == 0
    # P2:不辖
    assert handoff_gate_gap(_locked_formed_frame(plane=2), sess,
                            DEFAULT_REGISTRY) == 0
    # 开关关:恒 0
    assert handoff_gate_gap(st, sess, _GATE_OFF) == 0
    # 达标帧(hp 修复到健康带 → hp_tier≥1 ∧ 板面维达标 → 总档 1)
    assert handoff_gate_gap(_locked_formed_frame(hp=64), sess,
                            _GATE_ON) == 0


# ---------- ② formed_stop 承接维(挂载点 a) ----------

def test_formed_stop_handoff_dim_run28_type() -> None:
    """run 28/31 型:末窗成型低血 → 承接门不停手(买候选保留=继续
    投资证据行);关臂照旧丢弃全部买候选。"""
    st = _locked_formed_frame()
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    # 基线臂(门关):停手,买被拦(ADR-0343 原语义)
    sess_off = _sess_locked()
    kept_off, _ = filter_candidates([cand], st, sess_off, _GATE_OFF)
    assert sess_off.v3_formed_stop is True
    assert not any(isinstance(c.action, BuyCard) for c in kept_off)
    # 门臂(显式开):不停手,买保留(继续投资)
    sess_on = _sess_locked()
    kept_on, _ = filter_candidates([cand], st, sess_on, _GATE_ON)
    assert sess_on.v3_formed_stop is False
    assert sess_on.v3_handoff_gap == 1
    assert any(isinstance(c.action, BuyCard) for c in kept_on)
    # 非末窗同帧(r7):两臂同停手(承接维不辖 r7,零漂移)
    st7 = _locked_formed_frame(round_num=7)
    s_a, s_b = _sess_locked(), _sess_locked()
    assert formed_stop_active(st7, s_a, _GATE_ON) is True
    assert formed_stop_active(st7, s_b, _GATE_OFF) is True


# ---------- ③ EV 承接缺口项(挂载点 b) ----------

def test_ev_gap_term_authorizes_final_window_buy() -> None:
    """末窗兜底成型全 1★ 板的跨档买(53→49 破 50 平台):基线臂
    EV=1−3=−2 拒;门臂 V+5×1 放行,auth trace 带 handoff_gap;
    同帧 r7(非末窗)门臂照拒(零漂移)。"""
    st = _fallback_formed_frame()
    sess = StrategySession()          # 未锁 → 兜底 form_ok(engines=2)
    sess.v3_mode = 'economy'
    assert form_ok(st, sess, _GATE_ON) is True
    assert handoff_gate_gap(st, sess, _GATE_ON) == 1
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    # 基线臂:EV≤0 破息拒
    r_off = _check_constraint('interest_rule', cand, st, st, sess,
                              _GATE_OFF, val=1.0, bd={'int_emb': 0.0})
    assert r_off is not None and 'EV≤0 破息拒' in r_off.describe
    # 门臂:缺口项放行 + 授权 trace
    auth: dict = {}
    r_on = _check_constraint('interest_rule', cand, st, st, sess,
                             _GATE_ON, val=1.0,
                             bd={'int_emb': 0.0}, auth=auth)
    assert r_on is None
    assert auth.get('handoff_gap') == 1 and auth.get('ev_auth', 0) > 0
    # 非末窗同帧(r7):门臂照拒(承接项不辖非末窗)
    st7 = _fallback_formed_frame(round_num=7)
    assert _check_constraint('interest_rule', cand, st7, st7, sess,
                             DEFAULT_REGISTRY, val=1.0,
                             bd={'int_emb': 0.0}) is not None
    # 达标帧(hp 同 40 但核心 2★ 补上 → 总档 1):门臂照拒(不达标才放宽)
    dep = list(_fallback_formed_frame().deployed)
    dep[0] = replace(dep[0], star=2)
    st_ok = _fallback_formed_frame(deployed=dep)
    assert handoff_gate_gap(st_ok, sess, _GATE_ON) == 0
    assert _check_constraint('interest_rule', cand, st_ok, st_ok, sess,
                             DEFAULT_REGISTRY, val=1.0,
                             bd={'int_emb': 0.0}) is not None


# ---------- ④ sim 侧:账本字段 + A/B 非末窗零漂移 ----------

def test_sim_ledger_handoff_gap_and_zero_drift() -> None:
    """账本轮行带 handoff_gap(默认 0);A/B(门开/关)同 seed 的
    P1 非末窗(round<8)账本行逐位一致(设计件 §4.1 判据 3 后半,
    n 取最小 4)。"""
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert all('handoff_gap' in row for row in r.ledger)
    assert all((row.get('handoff_gap') or 0) >= 0 for row in r.ledger)
    for seed in range(4):
        on = cw_sim.simulate_p1(seed, pool='fallback', planes=2,
                                 strategy=_strategy_on())
        off = cw_sim.simulate_p1(seed, pool='fallback', planes=2)
        pre_on = [row for row in on.ledger
                  if row.get('plane') == 1 and row['round_num'] < 8]
        pre_off = [row for row in off.ledger
                   if row.get('plane') == 1 and row['round_num'] < 8]
        import json
        assert json.dumps(pre_on, default=str, ensure_ascii=False) \
            == json.dumps(pre_off, default=str, ensure_ascii=False), (
            f'seed {seed}:P1 非末窗漂移——承接门越权辖非末窗')


def _strategy_on():
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    return DecisionV2Strategy(registry=_GATE_ON)
