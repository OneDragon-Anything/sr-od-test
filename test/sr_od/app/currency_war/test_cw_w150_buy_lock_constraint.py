"""W150/ADR-0359 买侧通道锁定目标约束锁(scoring 层降级+末轮围栏)。

锁定对象(decision_v2/scoring.py + registry.py + cw_intention.locked_buy_scope):

- 锁定帧(``locked_buy_scope`` 非 None:P1 p1_pair 非空 ∪ comp 锁定态)
  时,``off_lock_buy_tags`` 辖的 line_opportunistic/bond_fallback 候选中
  目标件 ∉ 锁定目标体系集者,层3 评分减 ``off_lock_buy_penalty``
  (降级非禁绝,[31]④ 填充不变量保留);
- 位面末轮 boss 窗的 line_opportunistic 非目标件直接拒
  (final_fence;目标件+填充照旧);
- 未锁局(空窗/弱意向/降格)/应急态/开关关 = 行为不变(回归)。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.cw_intention import (
    HoardTarget,
    IntentionState,
    _pair_members,
    locked_buy_scope,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    _off_lock_demotion,
    score_candidate,
)

_REG = DEFAULT_REGISTRY
_REG_OFF = replace(DEFAULT_REGISTRY, buy_lock_constraint_enabled=False)


def _pair_sess(pair: tuple[str, ...]) -> StrategySession:
    """P1 配方锁定帧会话(p1_pair 非空;hoard=对成员集,生产真实形态)。"""
    s = StrategySession()
    ist = IntentionState()
    ist.p1_pair = pair
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset(_pair_members(pair)), frozenset(), 'p1_pair')
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'level': 5, 'gold': 60,
            'hp': 80, 'board': {'仙舟': 2},
            'deployed': [BenchChar(slot=0, char_id='青雀', faction='仙舟')],
            'bench': [None] * 9}
    base.update(kw)
    st = GameState(**base)
    return st


def _cand(name: str, tag: str, faction: str, cost: int) -> Candidate:
    return Candidate(
        action=BuyCard(ShopCard(x=1, name=name, faction=faction, cost=cost),
                       reason=''),
        tag=tag, source='shop', breakdown_hint={'cost': cost})


# --- ① 锁定帧降级(候选 A) ---------------------------------------------------


def test_locked_pair_offscope_opportunistic_demoted() -> None:
    """锁定帧(仙舟+DOT 对)的非目标件(三月七=列车,引擎件但∉对)
    line_opportunistic 候选降级:评分 −penalty,bd 记依据。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(shop=[])
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'
    v_on, bd_on = score_candidate(cand, st, sess, _REG)
    v_off, bd_off = score_candidate(cand, st, sess, _REG_OFF)
    assert abs((v_off - v_on) - _REG.off_lock_buy_penalty) < 1e-9
    assert bd_on.get('off_lock') == 'demote'
    assert 'off_lock' not in bd_off


def test_locked_pair_inscope_not_demoted() -> None:
    """对内体系件(青雀=仙舟)不降级——方向件不受辖。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state()
    cand = _cand('青雀', 'line_opportunistic', '仙舟', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == ''
    v_on, _ = score_candidate(cand, st, sess, _REG)
    v_off, _ = score_candidate(cand, st, sess, _REG_OFF)
    assert abs(v_on - v_off) < 1e-9


def test_locked_pair_bond_fallback_offscope_demoted() -> None:
    """bond_fallback 非目标填充件(阿格莱雅=昼之半神,∉对)降级
    ——降级非禁绝([31]④ 填充通道保留,只让位目标件)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(board={'仙舟': 2, '昼之半神': 1})
    cand = _cand('阿格莱雅', 'bond_fallback', '昼之半神', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'


# --- ② 末轮围栏(候选 B) ---------------------------------------------------


def test_final_round_boss_fence_rejects_offscope_opportunistic() -> None:
    """位面末轮 boss 窗:非目标件 opportunistic 直接拒(非正分,
    W143 strict 型末轮面;run17 直证);开关关=不拒(回归)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    sess.node_type_current = 'boss'
    st = _state(round_num=9)
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'final_fence'
    v_on, bd_on = score_candidate(cand, st, sess, _REG)
    assert v_on <= 0
    assert bd_on.get('off_lock') == 'final_fence'
    assert _off_lock_demotion(cand, st, sess, _REG_OFF) == ''


def test_final_round_fence_not_before_r9_or_nonboss() -> None:
    """围栏只辖位面末轮 boss 窗:r8/非 boss 节点只走常规降级。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    sess.node_type_current = 'boss'
    assert _off_lock_demotion(cand, _state(round_num=8), sess, _REG) \
        == 'demote'
    sess.node_type_current = 'battle'
    assert _off_lock_demotion(cand, _state(round_num=9), sess, _REG) \
        == 'demote'


def test_final_round_bond_fallback_fill_preserved() -> None:
    """末轮填充照旧([31]④ 梯队):bond_fallback 非目标件末轮 boss 窗
    仍只降级不围栏——填充通道不被掐死。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    sess.node_type_current = 'boss'
    st = _state(round_num=9, board={'仙舟': 2, '昼之半神': 1})
    cand = _cand('阿格莱雅', 'bond_fallback', '昼之半神', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'


# --- ③ 未锁局/边界回归 ------------------------------------------------------


def test_unlocked_frame_no_constraint() -> None:
    """未锁局(空窗/弱意向/降格)无锁定帧:不约束,评分与开关无关
    ——未锁局行为不变(回归)。"""
    for ist in (IntentionState(),
                IntentionState(phase='weak', weak_comp='DOT队'),
                IntentionState(demoted_endgame=True)):
        sess = StrategySession()
        sess.v3_intention = ist
        sess.v3_hoard = HoardTarget(frozenset(), frozenset(), 'p1_transition')
        st = _state()
        cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
        assert _off_lock_demotion(cand, st, sess, _REG) == ''
    # 空窗态(P1 配方锁开着但 p1_pair 空)同不辖
    ist = IntentionState()
    assert locked_buy_scope(ist) is None


def test_emergency_exempt() -> None:
    """应急态豁免([18] hp 报警战力优先,方向次要)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(hp=_REG.emergency_hp)
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == ''


# --- ④ comp 锁定帧(P2+/P1①资格)约束基准 -------------------------------


def test_locked_comp_frame_scope() -> None:
    """comp 锁定帧:scope=comp 采购集(_line_hoard);线外件降级、
    线内件不辖。"""
    sess = StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = 'DOT队'
    sess.v3_intention = ist
    scope = locked_buy_scope(ist)
    assert scope is not None and scope
    # 线外件(三月七=列车)降级;线内件(采购集成员)不辖
    assert '三月七' not in scope
    st = _state(plane=2)
    cand_out = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand_out, st, sess, _REG) == 'demote'
    cand_in = _cand(sorted(scope)[0], 'line_opportunistic', '持续伤害', 2)
    assert _off_lock_demotion(cand_in, st, sess, _REG) == ''
