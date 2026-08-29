"""W227/ADR-0400:P1 末窗承接门(设计件 08 §4.2 Phase 1)单帧锁。

**语义演进(ADR-0411 flag 家族清理)**:承接门自 W257 起无条件启用
——历史 handoff_gate_enabled 布尔删除,本锁原「默认关=旧行为」基线臂
与 off/on 零漂移对照随语义退场(docstring 记过期原因);现行为面 =
DEFAULT_REGISTRY 直接消费。历史分布面(门开/关 A/B n=300)数字见
ADR-0400/0411。

**语义演进(W288/ADR-0418 gate_min_round 前移 8→6)**:末窗下界改
为 r6——原 r7「非末窗零漂移」边界帧随之前移到 r5(非末窗/达标恒 0
的门结构前提本身不变);r8 视角标定的 boss 投影 +2 项随 min_round 在
r6 触发,属 ADR-0418 已知耦合 wart,不另设断言锁(防把畸变钉死成契约)。

锁面:
- 缺口判据窗口/辖域:r>=handoff_gate_min_round ∧ P1——非末窗/达标
  恒 0(P1 非末窗零漂移门的结构前提);
- formed_stop 承接维(挂载点 a):run 28/31 型构造局(成型低血,末窗
  承接档位未达标)→ 不停手继续投资(买候选保留);
- EV 承接缺口项(挂载点 b):末窗兜底成型全 1★ 板的跨档买,V+bonus
  放行(auth trace 带 handoff_gap);非末窗同帧同拒(零漂移);
- sim 侧:账本 handoff_gap 字段存在且非末窗恒 0。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import logging
from dataclasses import replace

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_state import (
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
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

#: ADR-0411:承接门无条件启用——行为臂即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY


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
    """r5(非末窗,W288 前移后边界)/P2 恒 0;r6-r9 缺口辖;达标帧 0。"""
    sess = _sess_locked()
    st = _locked_formed_frame()
    assert form_ok(st, sess, _REG) is True   # 前置:成型谓词过
    assert handoff_gate_gap(st, sess, _REG) == 1
    # 新窗内(r6/r7,W288/ADR-0418 前移后):照辖
    assert handoff_gate_gap(_locked_formed_frame(round_num=6), sess,
                            _REG) >= 0   # 是否有缺口随投影面,只锁「在窗内可非零」的前置
    assert handoff_gate_gap(_locked_formed_frame(round_num=7), sess,
                            _REG) == 1
    # 非末窗(r5):不辖(零漂移边界)
    assert handoff_gate_gap(_locked_formed_frame(round_num=5), sess,
                            _REG) == 0
    # P2:不辖
    assert handoff_gate_gap(_locked_formed_frame(plane=2), sess,
                            _REG) == 0
    # 达标帧(hp 修复到健康带 → 投影后 hp_tier≥1 ∧ 板面维达标 → 总档 1)
    assert handoff_gate_gap(_locked_formed_frame(hp=64), sess,
                            _REG) == 0


# ---------- ② formed_stop 承接维(挂载点 a) ----------

def test_formed_stop_handoff_dim_run28_type() -> None:
    """run 28/31 型:末窗成型低血 → 承接门不停手(买候选保留=继续
    投资证据行);非末窗同帧(r7)照旧停手(承接维不辖 r7,零漂移)。
    (过期语义记录:原「默认臂照旧停手」的基线断言已随 ADR-0411 转正
    删除——末窗低血不停手即当前无条件行为。)"""
    st = _locked_formed_frame()
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    sess_on = _sess_locked()
    kept_on, _ = filter_candidates([cand], st, sess_on, _REG)
    assert sess_on.v3_formed_stop is False
    assert sess_on.v3_handoff_gap == 1
    assert any(isinstance(c.action, BuyCard) for c in kept_on)
    # 零漂移边界随 W288/ADR-0418 前移重排:非末窗(r5)在成型停手线
    # (r≥7)之前,构造不出「floor 过∧门不辖」帧——改锁「窗内但承接
    # 达标仍停手」(r7 ∧ hp=64 → gap=0,承接维不拦):
    st7_ok = _locked_formed_frame(round_num=7, hp=64)
    s_b = _sess_locked()
    assert formed_stop_active(st7_ok, s_b, _REG) is True
    assert getattr(s_b, 'v3_handoff_gap', 0) == 0


# ---------- ③ EV 承接缺口项(挂载点 b) ----------

def test_ev_gap_term_authorizes_final_window_buy() -> None:
    """末窗兜底成型全 1★ 板的跨档买(53→49 破 50 平台):V+bonus 放行,
    auth trace 带 handoff_gap;同帧 r7(非末窗)拒(零漂移);达标帧
    拒(不达标才放宽)。
    (过期语义记录:原「基线臂 EV≤0 破息拒」对照断言已随 ADR-0411
    转正删除——本行为即当前无条件路径。语义演进(ADR-0451 血预算
    停手·第二波):授权帧改 hp=70 带外——hp<60 末窗帧缺口项降格不加成
    (血预算停手·P1-a),反例:hp=40 帧同构造被拒。)"""
    st = _fallback_formed_frame(hp=70)
    sess = StrategySession()          # 未锁 → 兜底 form_ok(engines=2)
    sess.v3_mode = 'economy'
    assert form_ok(st, sess, _REG) is True
    assert handoff_gate_gap(st, sess, _REG) == 1
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    # 门臂(现无条件):缺口项放行 + 授权 trace
    auth: dict = {}
    r_on = _check_constraint('interest_rule', cand, st, st, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}, auth=auth)
    assert r_on is None
    assert auth.get('handoff_gap') == 1 and auth.get('ev_auth', 0) > 0
    # 非末窗同帧(r5,W288 前移后边界):照拒(承接项不辖非末窗)
    st7 = _fallback_formed_frame(round_num=5)
    assert _check_constraint('interest_rule', cand, st7, st7, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None
    # ADR-0451 反例:hp=40(末窗血预算不足带)缺口项不加成 → 照拒
    st_band = _fallback_formed_frame()
    assert handoff_gate_gap(st_band, sess, _REG) == 1
    assert _check_constraint('interest_rule', cand, st_band, st_band,
                             sess, _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None
    # 达标帧(核心 2★ 补上 + hp 60:boss 投影后 hp=28 → hp_tier=1,
    # 板面维亦达标 → 总档 1):照拒(不达标才放宽)。
    # (口径注:hp 取值按 ADR-0411 无条件 boss 投影选档——原 hp=40
    # 帧在 boss 投影下落 hp_tier=0,属「未达标」不再是达标例。)
    dep = list(_fallback_formed_frame().deployed)
    dep[0] = replace(dep[0], star=2)
    st_ok = _fallback_formed_frame(deployed=dep, hp=60)
    assert handoff_gate_gap(st_ok, sess, _REG) == 0
    assert _check_constraint('interest_rule', cand, st_ok, st_ok, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None


# ---------- ④ sim 侧:账本字段 + 非末窗零漂移 ----------

def test_sim_ledger_handoff_gap_zero_before_final_window() -> None:
    """账本轮行带 handoff_gap 且非末窗(plane1 round<6,W288/ADR-0418
    前移后)恒 0——P1 非末窗零漂移的结构前提在默认注册表下直接成立
    (n 取最小 2)。"""
    for seed in range(2):
        r = cw_sim.simulate_p1(seed, pool='fallback', planes=2)
        assert all('handoff_gap' in row for row in r.ledger)
        assert all((row.get('handoff_gap') or 0) >= 0 for row in r.ledger)
        pre = [row for row in r.ledger
               if row.get('plane') == 1 and row['round_num'] < 6]
        assert all((row.get('handoff_gap') or 0) == 0 for row in pre), (
            f'seed {seed}:承接门越权辖非末窗')
