"""P2 危机带锁(停手线 P2 覆盖 + 危机买入闸门 + floor 兼容)。

出处(R2 存活面批;设计依据见各锁 docstring):
- 病灶一修 = ``discipline.p2_crisis_band``/``p2_crisis_stop_hp``:
  ``blood_budget_refresh_blocked`` 的 P2 臂(带内搜索型刷新停付),
  依据 = P21 敏感网格(d=2 档全负域,免 β)+ 双失缓冲血预算算术
  (registry emergency_hp 推导同款);证据锚 = R2 批最重局 s21
  (P2 危机段单轮 4-8 连刷零拦截,``blood_budget_refresh_rejects``
  全批 0)。
- 病灶二修 = ``arbiter._crisis_buy_gate_open``:危机带内目标件/合成
  完成件买候选越过非正分门 + gold_floor/interest_rule 让位(可负担性
  hard 下界保留),依据 = P48 三段管辖 λ>0 段「转化优先、S 线降级」;
  证据锚 = s21 p2r5(hp17 金 101 目标件在售零买入,买候选评 0 分被
  结构性拒,同帧负分刷新反获泄息预算放行=激励倒置)。
- floor 兼容(P56/p54):刷新通道 floor 语义零触碰——P2 臂只辖
  刷新授权的停付面,不产生任何「门过⟹刷后破线」路径;买入侧走义务
  让渡辖域(p54 A3/[41] 先例)并以 gold−cost≥0 封底。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    blood_budget_refresh_blocked,
    p2_crisis_band,
    p2_crisis_stop_hp,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)

_REG = DEFAULT_REGISTRY


def _sess() -> StrategySession:
    return StrategySession()


def _p2_state(hp: int = 36, gold: int = 100, round_num: int = 3,
              node: str = 'battle') -> GameState:
    """P2 备战帧(默认 hp=36 ∈ (应急带 25, 危机线 41] 危机带)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, 9, gold, hp
    st.round_num = round_num
    st.node_type = node
    st.bench = [BenchChar(slot=0, char_id='爻光', faction='仙舟')]
    st.deployed = [BenchChar(slot=i + 1, char_id='椒丘', faction='仙舟')
                   for i in range(2)]
    return st


def _buy_cand(name: str = '希儿', cost: int = 3,
              merge: bool = False) -> Candidate:
    card = ShopCard(x=0, name=name, cost=cost, faction='贝洛伯格')
    return Candidate(action=BuyCard(card=card, reason='test'),
                     tag='line_carry', source='test', merge=merge)


# ---------- 病灶一:停手线 P2 覆盖 ----------

def test_p2_crisis_stop_hp_matches_registry_math() -> None:
    """危机线 = ceil(2×vd_p2_loss)(注册表直调零新参数;双失缓冲算术
    与 P21 d=2 档同值互证)——常量漂移即红。"""
    import math
    assert p2_crisis_stop_hp(_REG) == math.ceil(2 * _REG.vd_p2_loss)


def test_p2_refresh_stop_band_and_exemptions() -> None:
    """停手线 P2 覆盖锁:危机带内搜索刷新停付;应急带(急救型保留)/
    带外/开关 off 不辖。出处 = R2 存活面批病灶一修(见模块 docstring);
    旧「P2 标定前零辖域」语义已被本设计取代(12_blood_budget_semantics
    §3.2 数值线的免 β 落域路径 = P21 网格 d=2)。"""
    sess = _sess()
    assert blood_budget_refresh_blocked(_p2_state(hp=41), sess, _REG)
    assert blood_budget_refresh_blocked(_p2_state(hp=36), sess, _REG)
    assert not blood_budget_refresh_blocked(_p2_state(hp=42), sess, _REG)
    # 应急带(hp≤emergency_hp=25):急救型豁免在 P2 臂之前,保留
    assert not blood_budget_refresh_blocked(_p2_state(hp=25), sess, _REG)
    assert not blood_budget_refresh_blocked(_p2_state(hp=17), sess, _REG)
    # 开关 off = A/B 对照臂零辖域
    reg_off = dataclasses.replace(_REG, blood_budget_refresh_stop_enabled=False)
    assert not blood_budget_refresh_blocked(_p2_state(hp=36), sess, reg_off)
    # P1 末窗线原语义零漂移(P1 域仍走 p1_exit_blood_short)
    p1 = GameState()
    p1.plane, p1.level, p1.gold, p1.hp = 1, 6, 100, 40
    p1.round_num, p1.node_type = 7, 'battle'
    assert blood_budget_refresh_blocked(p1, sess, _REG)


def test_p2_crisis_band_domain() -> None:
    """共域谓词边界:plane≥2 ∧ hp 真值 ∧ hp≤线;hp=None 不判带(误拦
    代价非对称取不拦,与 P1 末窗线同款口径)。"""
    assert p2_crisis_band(_p2_state(hp=41), _REG)
    assert not p2_crisis_band(_p2_state(hp=42), _REG)
    p3 = _p2_state(hp=30)
    p3.plane = 3
    assert p2_crisis_band(p3, _REG)
    st = _p2_state(hp=36)
    st.hp = None
    assert not p2_crisis_band(st, _REG)
    p1 = _p2_state(hp=36)
    p1.plane = 1
    assert not p2_crisis_band(p1, _REG)


# ---------- 病灶二:危机买入闸门 ----------

def test_crisis_buy_bypasses_nonpositive_and_interest_gates() -> None:
    """危机闸门触发锁:危机带内目标件买候选评 0 分仍放行(非正分门
    越过 + 息纪律两门让位),auth trace 带 crisis_buy 分键。机制复现
    = s21 p2r2 形态(金 51 目标件 3 费,pre-fix 被
    interest_rule EV≤0 拒)。"""
    sess = _sess()
    st = _p2_state(hp=36, gold=51)
    res = arbitrate([(_buy_cand('希儿', cost=3), 0.0, {})], st, sess, _REG)
    assert any(isinstance(a, BuyCard) for a in res.actions)
    row = next(r for r in res.log if r.get('accepted'))
    assert 'crisis_buy' in (row.get('ev_auth') or {})


def test_crisis_buy_gate_scoped_to_band_and_targets() -> None:
    """辖域锁:带外(hp=80)评 0 分照拒(非正分,零漂移面);带内
    非目标件评 0 分照拒(闸门只辖转化面)。"""
    sess = _sess()
    out_band = arbitrate([(_buy_cand('希儿', cost=3), 0.0, {})],
                         _p2_state(hp=80, gold=100), sess, _REG)
    assert not out_band.actions
    assert any('非正分' in (r.get('reject') or '') for r in out_band.log)
    # 非目标件(注册表内非引擎件名)
    from sr_od.application.currency_war.data.cw_chars import CHARACTERS
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        engine_char_names,
    )
    engines = set(engine_char_names())
    non_target = next(n for n in CHARACTERS if n not in engines)
    in_band = arbitrate([(_buy_cand(non_target, cost=3), 0.0, {})],
                        _p2_state(hp=36, gold=100), sess, _REG)
    assert not in_band.actions


def test_crisis_buy_affordability_hard_floor() -> None:
    """floor 兼容锁(P56):危机买入受可负担性 hard 下界封底——金不足
    (gold−cost<0)不放行;刷新通道 floor(p54)语义零触碰(停手线
    只辖授权停付面,本锁以「开关 off 臂刷新行为回到基线」作通道不变
    的结构锚)。"""
    sess = _sess()
    st = _p2_state(hp=36, gold=2)
    res = arbitrate([(_buy_cand('希儿', cost=3), 0.0, {})], st, sess, _REG)
    assert not res.actions
    # 刷新通道零触碰:开关 off(基线臂)时危机带刷新照常放行 = P2 臂
    # 是唯一的刷新域新增约束,无其他 floor 面改动
    reg_off = dataclasses.replace(_REG, blood_budget_refresh_stop_enabled=False)
    assert not blood_budget_refresh_blocked(_p2_state(hp=36), _sess(), reg_off)


def test_crisis_merge_completion_candidate_passes() -> None:
    """合成完成件(merge=True,第三张买入即 2★)在危机带内同样越过
    非正分门(完成价值在星级阶梯,评分维构造性零增量)。"""
    sess = _sess()
    st = _p2_state(hp=36, gold=100)
    res = arbitrate([(_buy_cand('希儿', cost=3, merge=True), 0.0, {})],
                    st, sess, _REG)
    assert any(isinstance(a, BuyCard) for a in res.actions)
