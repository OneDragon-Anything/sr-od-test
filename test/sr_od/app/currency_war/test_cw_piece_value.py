"""W836 · 件价值模型 Phase 1 单帧锁组(W831 v2 §5.1 判前锁 + W833 三补丁)。

设计出处:.debug/temp/currency_war/w831_piece_value_design/REPORT.md v2
(§4 落码规格/§5.1 六结构锁)+ w833_piece_value_attack/REPORT_v2_check.md
三补丁(④哨兵语义=「禁进评分/决策路径,披露键除外」+类型层收窄)。

锁语义不锁分布数值(测试纪律):锁契约与结构,权重/分量值为占位。
开关组 piece_value_*(伞+buy/keep/merge)默认关 = 第 1 态零漂移锚,
每锁带 off 臂对照断言(生命周期第 3 态盘点义务:开臂翻默认时按本
锁组 off 臂清单重推语义)。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.piece_value import (
    PieceValueBreakdown,
    PieceValueWeightPhase1,
    evaluate_piece,
    phase1_weight_from_registry,
)
from sr_od.application.currency_war.decision.decision_v2.realization import (
    missing_members,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    TRANSITION_TRAITS,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)

_CORE = '姬子·启行'   # 列车同行 3 费成员(锁定线;断言走语义不锁牌面)
_REG_OFF = DEFAULT_REGISTRY


def _reg_pv(**kw) -> object:
    """Phase 1 开臂形态 registry(伞+buy 开;权重可注)。"""
    base = {'piece_value_enabled': True, 'piece_value_buy_enabled': True}
    base.update(kw)
    return dataclasses.replace(_REG_OFF, **base)


def _sess(locked: bool = True) -> StrategySession:
    s = StrategySession()
    ist = IntentionState()
    if locked:
        ist.phase = 'locked'
        ist.locked_comp = '列车同行'
    s.v3_intention = ist
    return s


def _st(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


def _scope() -> frozenset[str]:
    """锁定线成员集(与消费点同源:cw_intention.locked_buy_scope)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        locked_buy_scope,
    )
    return frozenset(locked_buy_scope(_sess().v3_intention))


def _dot_name() -> str:
    """线外体系钥匙件对照:1 费持续伤害成员(DOT2=过渡体系之一)。"""
    return sorted(n for n, c in CHARACTERS.items()
                  if c.cost == 1 and '持续伤害' in (c.factions + c.flows))[0]


def _plain_name(cost: int) -> str:
    """非过渡体系的对照散件(指定费用;体系键集为空)。"""
    eng_bonds = {b for b, _t in TRANSITION_TRAITS}
    for n, c in sorted(CHARACTERS.items()):
        if c.cost == cost and not ((set(c.factions or ())
                                    | set(c.flows or ())) & eng_bonds):
            return n
    raise AssertionError(f'no plain char with cost={cost}')


# ===== 锁 0(开关组缺省态)=====

def test_lock0_switch_group_defaults_off() -> None:
    """伞+三子旗标默认全关,权重缺省 0(生命周期第 1 态)。"""
    for f in ('piece_value_enabled', 'piece_value_buy_enabled',
              'piece_value_keep_enabled', 'piece_value_merge_enabled'):
        assert getattr(_REG_OFF, f) is False
    assert _REG_OFF.piece_value_w_activation == 0.0
    assert _REG_OFF.piece_value_w_retention == 0.0


# ===== 锁 1 分量可分解性 =====

def test_lock1_decomposability() -> None:
    """total ≡ 辖域门内分量加权和:改任一权重只动对应分量的贡献。"""
    st = _st(board={'持续伤害': 1})   # k→k+1 恰达帧:激活靶件在场语境
    w0 = PieceValueWeightPhase1()
    bd0 = evaluate_piece(_dot_name(), st, w0, _REG_OFF,
                         session=_sess(), target_scope=_scope())
    assert bd0.total == 0.0
    wa = PieceValueWeightPhase1(w_activation=2.0, w_retention=0.0)
    wr = PieceValueWeightPhase1(w_activation=0.0, w_retention=3.0)
    bda = evaluate_piece(_dot_name(), st, wa, _REG_OFF,
                         session=_sess(), target_scope=_scope())
    bdr = evaluate_piece(_dot_name(), st, wr, _REG_OFF,
                         session=_sess(), target_scope=_scope())
    assert bda.total == pytest.approx(2.0 * bda.activation)
    assert bdr.total == pytest.approx(3.0 * bdr.retention)
    # 全量 weight:total = w_a·A + w_r·B 逐位(分解式本身)
    w1 = PieceValueWeightPhase1(w_activation=0.5, w_retention=1.5)
    bd1 = evaluate_piece(_dot_name(), st, w1, _REG_OFF,
                         session=_sess(), target_scope=_scope())
    assert bd1.total == pytest.approx(
        0.5 * bd1.activation + 1.5 * bd1.retention)


# ===== 锁 2 辖域门 =====

def test_lock2_scope_gates() -> None:
    """A/B 辖域门:P20 e≥2 激活恒 0;非体系件激活恒 0;线内成员
    A/B 恒 0;非满息段留存恒 0(P11);bench 满栏留存恒 0;非锁定
    帧(target_scope 空)A/B 恒 0。"""
    w = PieceValueWeightPhase1(w_activation=1.0, w_retention=1.0)
    sess = _sess()
    scope = _scope()
    # ① 锁定帧线外体系钥匙件 e<2 ∧ k→k+1 恰达:激活>0(开臂形态靶件)
    bd_key = evaluate_piece(_dot_name(), _st(board={'持续伤害': 1}), w,
                            _REG_OFF, session=sess, target_scope=scope)
    assert bd_key.activation > 0.0
    # ② e≥2(双引擎在场:DOT2×2 + 列车同行×2):激活恒 0(P20 辖域硬门控)
    dep = [BenchChar(slot=0, char_id=_dot_name(), star=1,
                     faction='持续伤害'),
           BenchChar(slot=1, char_id=_dot_name(), star=1,
                     faction='持续伤害'),
           BenchChar(slot=2, char_id=_CORE, star=1, faction='列车同行'),
           BenchChar(slot=3, char_id=_CORE, star=1, faction='列车同行')]
    st_e2 = _st(deployed=dep)
    st_e2.board = {'持续伤害': 1}
    from sr_od.application.currency_war.decision.decision_v2.scoring import (
        _engines_formed,
    )
    assert _engines_formed(st_e2, _REG_OFF) >= 2
    assert evaluate_piece(_dot_name(), st_e2, w, _REG_OFF, session=sess,
                          target_scope=scope).activation == 0.0
    # ③ 非体系散件:激活恒 0(同费用对照)
    assert evaluate_piece(_plain_name(1), _st(), w, _REG_OFF,
                          session=sess,
                          target_scope=scope).activation == 0.0
    # ④ 线内成员:A/B 恒 0(target 外辖域)
    bd_core = evaluate_piece(_CORE, _st(), w, _REG_OFF, session=sess,
                             target_scope=scope)
    assert bd_core.activation == 0.0
    assert bd_core.retention == 0.0
    # ⑤ 非满息段(gold<息线):留存恒 0(P11)
    bd_poor = evaluate_piece(_plain_name(5), _st(gold=40), w, _REG_OFF,
                             session=sess, target_scope=scope)
    assert bd_poor.retention == 0.0
    # ⑥ bench 满栏:留存恒 0(挤占禁囤,与 P29 定性门同判据)
    full = [BenchChar(slot=i, char_id=_plain_name(1), star=1,
                      faction='?') for i in range(9)]
    bd_full = evaluate_piece(_plain_name(5), _st(bench=full), w, _REG_OFF,
                             session=sess, target_scope=scope)
    assert bd_full.retention == 0.0
    # ⑦ 非锁定帧(scope 空):A/B 恒 0(Phase 1 试点辖域=锁定帧)
    bd_unlocked = evaluate_piece(_dot_name(), _st(), w, _REG_OFF,
                                 session=sess, target_scope=frozenset())
    assert bd_unlocked.activation == 0.0
    assert bd_unlocked.retention == 0.0


# ===== 锁 3 单调性(命题直推)=====

def test_lock3_monotonicity() -> None:
    """①体系钥匙件 activation > 同费散件(P20 倍数>1 方向);
    ②再遇越稀有(费用序数代理)retention 单调不减(P1);
    ③满息段 interest_cost ≡ 0(P11)。"""
    w = PieceValueWeightPhase1(w_activation=1.0, w_retention=1.0)
    sess = _sess()
    scope = _scope()
    st_act = _st(board={'持续伤害': 1})
    assert evaluate_piece(_dot_name(), st_act, w, _REG_OFF, session=sess,
                          target_scope=scope).activation > 0.0
    assert evaluate_piece(_plain_name(1), st_act, w, _REG_OFF,
                          session=sess,
                          target_scope=scope).activation == 0.0
    costs = sorted({c.cost for c in CHARACTERS.values() if 1 <= c.cost <= 5})
    prev: float | None = None
    for cost in costs:
        name = _plain_name(cost)
        r = evaluate_piece(name, _st(), w, _REG_OFF, session=sess,
                           target_scope=scope).retention
        assert r == pytest.approx(float(cost))   # 费用序数代理直译
        if prev is not None:
            assert r >= prev   # P1:越稀有越囤,单调不减
        prev = r
    # 满息段(gold≥息线)F 分量恒 0
    for g in (50, 55, 60, 80):
        bd = evaluate_piece(_plain_name(3), _st(gold=g), w, _REG_OFF,
                            session=sess, target_scope=scope)
        assert bd.interest_cost == 0.0
    # 破息段跨档 F 分量为负(P13/P33 档差口径);E 分量随占用为负
    _b3 = [BenchChar(slot=i, char_id=_plain_name(1), star=1, faction='?')
           for i in range(3)]
    bd = evaluate_piece(_plain_name(4), _st(gold=43, bench=_b3), w,
                        _REG_OFF, session=sess, target_scope=scope)
    assert bd.interest_cost < 0.0
    assert bd.bench_cost < 0.0


# ===== 锁 4 off 恒等零漂移 =====

def test_lock4_off_identity_zero_drift() -> None:
    """伞关(含权重非零注但伞关)→ 消费点行为逐位等于现行基线:
    分值不变且 bd 无 pv* 披露键(零漂移锚,W802 13 锁同款)。"""
    st = _st()
    sess = _sess()
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=_dot_name(),
                                             cost=1)),
                     tag='bond_fallback', source='test')
    base_v, base_bd = score_candidate(cand, st, sess, _REG_OFF)
    # 权重非零但伞关:仍零漂移
    reg_w = dataclasses.replace(
        _REG_OFF, piece_value_w_activation=1.0,
        piece_value_w_retention=1.0)
    off_v, off_bd = score_candidate(cand, st, sess, reg_w)
    assert off_v == pytest.approx(base_v)
    assert not [k for k in off_bd if k.startswith('pv')]
    assert base_bd == off_bd
    # 伞开但权重缺省 0:分值不变(加项为 0),披露键在场
    reg_on0 = _reg_pv()
    on0_v, on0_bd = score_candidate(cand, st, sess, reg_on0)
    assert on0_v == pytest.approx(base_v)
    assert 'pv' in on0_bd and on0_bd['pv'] == 0.0


# ===== 锁 5 纯函数 =====

def test_lock5_pure_function() -> None:
    """同输入两次调用输出逐位相等;输入 state 不被改写(零副作用)。"""
    st = _st(board={'持续伤害': 1}, bench=[
        BenchChar(slot=0, char_id=_CORE, star=1, faction='列车同行')])
    sess = _sess()
    w = phase1_weight_from_registry(dataclasses.replace(
        _REG_OFF, piece_value_w_activation=1.0, piece_value_w_retention=1.0))
    snap = (st.gold, st.board and dict(st.board), len(st.bench or []),
            [b.char_id for b in st.bench or [] if b is not None])
    b1 = evaluate_piece(_dot_name(), st, w, _REG_OFF, session=sess,
                        target_scope=_scope())
    b2 = evaluate_piece(_dot_name(), st, w, _REG_OFF, session=sess,
                        target_scope=_scope())
    assert b1 == b2
    assert (st.gold, dict(st.board), len(st.bench or []),
            [b.char_id for b in st.bench or [] if b is not None]) == snap


# ===== 锁 6 Phase 1 消费面收窄哨兵(W833 补丁④)=====

def test_lock6_phase1_sentinel_narrowing() -> None:
    """类型层收窄:Phase 1 weight 类型只有 w_activation/w_retention
    两字段(全量 weight 类型 Phase 2 才引入,提前引入=锁红);
    registry 无 C/D/E/F 权重字段(契约锁兜底);C/D/E/F 禁进 total
    合成——非零 C/D/E/F 分量在 Phase 1 weight 下 total 不含其贡献。"""
    assert [f.name for f in dataclasses.fields(PieceValueWeightPhase1)] \
        == ['w_activation', 'w_retention']
    for absent in ('piece_value_w_tier_gap', 'piece_value_w_merge',
                   'piece_value_w_bench_cost', 'piece_value_w_interest_cost',
                   'piece_value_w_bench', 'piece_value_w_interest'):
        assert not hasattr(_REG_OFF, absent)
    # 全零权重下,非零披露分量的 total 恒 0(合成面只辖 A/B)
    bd = PieceValueBreakdown(activation=0.0, retention=0.0, tier_gap=9.0,
                             merge=8.0, bench_cost=-7.0, interest_cost=-6.0)
    assert bd.total == 0.0
    # 披露面与决策面分离:消费点 bd 携带 pv* 披露键,但分值增量
    # == pv.total(锁 4 已锁 off 臂;此处锁 on 臂披露≠决策越权)
    st = _st()
    sess = _sess()
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=_dot_name(),
                                             cost=1)),
                     tag='bond_fallback', source='test')
    reg = _reg_pv(piece_value_w_activation=1.0,
                  piece_value_w_retention=1.0)
    v, bd_out = score_candidate(cand, st, sess, reg)
    pv_bd = evaluate_piece(cand.action.card, st,
                           phase1_weight_from_registry(reg), reg,
                           session=sess, target_scope=_scope())
    assert bd_out.get('pv') == pytest.approx(round(pv_bd.total, 4))
    base_v, _ = score_candidate(cand, st, sess, _REG_OFF)
    assert v == pytest.approx(base_v + pv_bd.total)


# ===== 锁 7 κ 通道零改动(W802 锁 #3 恒等式基线保护)=====

def test_lock7_kappa_channel_unchanged() -> None:
    """W802 锁 #3 恒等式(on = raw·(1−κ),raw>0)在 Phase 1 交付下
    原样成立:pv 加项计入 raw、经同一 κ 折扣(外侧应用),κ 路径
    零改动;pv 全关时恒等式与 HEAD 基线逐位一致。"""
    name = _dot_name()
    st = _st(board={'持续伤害': 1}, gold=55)
    sess = _sess()
    cand = Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=1)),
                     tag='bond_fallback', source='test')
    kappa = _REG_OFF.realization_off_lock_kappa
    penalty = _REG_OFF.off_lock_buy_penalty
    # pv 关(HEAD 基线):锁 #3 原样
    off0, _ = score_candidate(cand, st, sess, _REG_OFF)
    on0, _ = score_candidate(cand, st, sess, dataclasses.replace(
        _REG_OFF, realization_chain_enabled=True,
        realization_buy_enabled=True))
    raw0 = off0 + penalty
    assert raw0 > 0
    assert on0 == pytest.approx(raw0 * (1.0 - kappa))
    # pv 开:同一恒等式在含 pv 加项的 raw 上成立(κ 语义零改动)
    reg_pv_off = _reg_pv(piece_value_w_activation=1.0,
                         piece_value_w_retention=1.0)
    reg_pv_on = dataclasses.replace(reg_pv_off,
                                    realization_chain_enabled=True,
                                    realization_buy_enabled=True)
    off1, _ = score_candidate(cand, st, sess, reg_pv_off)
    on1, _ = score_candidate(cand, st, sess, reg_pv_on)
    raw1 = off1 + penalty
    assert raw1 > raw0   # pv 加项在场(靶件为线外体系钥匙件)
    assert on1 == pytest.approx(raw1 * (1.0 - kappa))


# ===== 锁 8 C 分量 missing_members 同源对拍 =====

def test_lock8_tier_gap_single_source() -> None:
    """线内缺档成员的 tier_gap 与 realization.missing_members 同帧
    值逐位同源(禁另写缺件判定);非缺件成员 tier_gap=0。"""
    sess = _sess()
    scope = _scope()
    st = _st(board={'列车同行': 1})
    assert _CORE in scope
    missing = missing_members(st, sess, _REG_OFF)
    assert _CORE in missing
    bd = evaluate_piece(_CORE, st, PieceValueWeightPhase1(), _REG_OFF,
                        session=sess, target_scope=scope)
    assert bd.tier_gap == pytest.approx(
        _REG_OFF.realization_delta_p_tier * (1.0 - missing[_CORE]))
    # 线外件不在缺件清单 → tier_gap 恒 0
    bd_out = evaluate_piece(_dot_name(), st, PieceValueWeightPhase1(),
                            _REG_OFF, session=sess, target_scope=scope)
    assert bd_out.tier_gap == 0.0
