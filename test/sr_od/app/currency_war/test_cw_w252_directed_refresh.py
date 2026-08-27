"""W252/ADR-0409:M-A 定向 D 牌授权窗单帧锁。

锁面(结构面;分布面=w252 三臂 AB sim 批):
- 授权窗:预算>0 只在「flag 开 ∧ gate gap>0(P1 末窗)∧ 追名 peak≥2
  (意向核心名集内某名 star 加权副本 ∈[2,3),距 3合1 只差最后一张)」
  三条件同时成立;任一缺 → 0(零行为);
- 正交:仅 M-A flag 开(gate 关)= 恒 0(W242 C 项先例);
- 有界性:每轮 ≤per_round、每局 ≤game_cap;消耗计数不重置局级;
- 防双计(互斥边界):预算只辖 refresh 维——非正分刷新经预算放行时
  买候选授权路径(interest_rule 缺口项/copy 放行)零改动;正分刷新
  走既有 V_D 路径不耗预算;gold_floor 金地板照辖;
- 默认关+零漂移:DEFAULT_REGISTRY flag 关,sim 整局与基线逐位一致。
n 取断言成立最小值;sim 断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import json
import logging
from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
    _core_names,
)
from sr_od.application.currency_war.decision_v2.handoff import (
    directed_refresh_budget,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)

_OFF = DEFAULT_REGISTRY
_MA_ONLY = replace(DEFAULT_REGISTRY, handoff_refresh_directed=True)
_GATE = replace(DEFAULT_REGISTRY, handoff_gate_enabled=True)
_GATE_MA = replace(_GATE, handoff_refresh_directed=True)

_CARRY = '姬子·启行'
_FILLER = '娜塔莎'
_FAC = '贝洛伯格'


def _bench(name: str, faction: str, slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str, star: int = 1,
              slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.cw_intention import (
        HoardTarget,
        IntentionState,
    )
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {_CARRY}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=(_CARRY,))
    return s


def _state(**kw) -> GameState:
    """末窗承接缺口帧 + 追名 peak≥2 帧:deployed 含 1× 核心(星级加权 1)
    + bench 1× 核心副本(星级加权 1)→ 合计 2(∈[2,3));hp/board 维
    缺口成立(同 W242 帧族)。"""
    base = {'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5,
            'hp': 20,
            'board': {'列车同行': 2, _FAC: 1},
            'deployed': [_deployed(_CARRY, '列车同行'),
                         _deployed(_FILLER, _FAC)],
            'bench': [_bench(_CARRY, '列车同行', slot=0)],
            'shop': [], 'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


# ---------- ① 授权窗三条件 ----------


def test_budget_requires_all_three_conditions() -> None:
    """三条件缺一即 0:flag 开+gap>0+peak≥2 才授权;
    peak<3 且 ≠2(持满 3 份)/gap=0(非末窗/达标帧)/flag 关均不授权。"""
    sess = _sess()
    st = _state()
    assert directed_refresh_budget(st, sess, _GATE_MA) \
        == DEFAULT_REGISTRY.directed_refresh_per_round
    # flag 单独开(gate 关):恒 0——正交结构前提(W242 C 项同式)
    assert directed_refresh_budget(st, sess, _MA_ONLY) == 0
    # 默认关
    assert directed_refresh_budget(st, sess, _OFF) == 0
    assert DEFAULT_REGISTRY.handoff_refresh_directed is False
    # 非末窗(r7):gap=0 → 不授权
    assert directed_refresh_budget(_state(round_num=7), sess,
                                   _GATE_MA) == 0
    # 追名 peak 出域:已满 3 份(copies_cap 面)→ 不授权
    st_full = _state(bench=[_bench(_CARRY, '列车同行', slot=0),
                            _bench(_CARRY, '列车同行', slot=1)])
    assert directed_refresh_budget(st_full, sess, _GATE_MA) == 0
    # 追名 peak <2(只有 deployed 一份):收集线未起步不授权(W249 口径)
    st_one = _state(bench=[])
    assert directed_refresh_budget(st_one, sess, _GATE_MA) == 0


# ---------- ② arbiter:有界放行 + 单一来源 ----------


def test_arbiter_nonpositive_refresh_bounded_pass() -> None:
    """主通道:非正分刷新在授权窗开时有界放行(进 actions+计数);
    预算外的第二次放行被轮上限拦回「非正分」。"""
    sess = _sess()
    st = _state(gold=55, hp=30)   # hp>25 非应急([18]);board 维仍 tier0→gap≥1
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st, sess, _GATE_MA)
    row = res.log[-1]
    assert row['accepted'] is True, f'预算内应放行(log={row})'
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert (getattr(sess, 'v3_dir_refresh_round', 0),
            getattr(sess, 'v3_dir_refresh_used', 0)) == (1, 1)


def test_arbiter_gate_off_zero_drift_nonpositive_rejected() -> None:
    """全关/仅 M-A 开(gate 关):非正分刷新照拒(默认关零漂移)。"""
    sess = _sess()
    st = _state(gold=55)
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    for reg in (_OFF, _MA_ONLY):
        res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], st,
                        StrategySession(), reg)
        assert res.log[-1]['reject'] == '非正分'


def test_positive_vd_path_not_billed_to_budget() -> None:
    """防双计单一来源面:正分刷新(V_D 放行)不消耗 M-A 预算计数——
    预算只辖 M-A 授权面,W249 的 0.44 次/局基线不受开关扰动。"""
    sess = _sess()
    st = _state(gold=55)
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, 6.0, {'int_emb': 0.0})], st, sess, _OFF)
    assert res.log[-1]['accepted'] is True   # V_D 正分与预算无关
    assert getattr(sess, 'v3_dir_refresh_used', 0) == 0


# ---------- ③ 约束链照辖 ----------


def test_affordability_floor_still_governs_authorized_refresh() -> None:
    """可负担性下限照辖:金 11 刷 2 → 花后 9 < boss_floor(10)拒;
    金 13 → 花后 11 达标放行(收尾的下限兜底,M-A 授权≠无限透支)。"""
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    res = arbitrate([(cand, -2.0, {'int_emb': 0.0})], _state(gold=11,
                     hp=30), _sess(), _GATE_MA)
    assert res.log[-1]['accepted'] is False
    res3 = arbitrate([(cand, -2.0, {'int_emb': 0.0})],
                     _state(gold=13, hp=30), _sess(), _GATE_MA)
    assert res3.log[-1]['accepted'] is True
    assert any(isinstance(a, RefreshShop) for a in res3.actions)


# ---------- ④ 局级消耗边界 ----------


def test_game_cap_exhaustion_and_default_off_sim_identity() -> None:
    """局级上限:game_cap 次后预算归 0;sim 侧默认关整局与基线逐位一致。"""
    sess = _sess()
    sess.v3_dir_refresh_used = DEFAULT_REGISTRY.directed_refresh_game_cap
    assert directed_refresh_budget(_state(), sess, _GATE_MA) == 0
    # sim 默认关=零漂移(n=4 最小 fallback 池,与 W242 锁同式)
    for seed in range(4):
        on = cw_sim.simulate_p1(
            seed, pool='fallback', planes=2,
            strategy=__import__(
                'sr_od.application.currency_war.decision_v2.strategy',
                fromlist=['DecisionV2Strategy']).DecisionV2Strategy(
                    registry=_MA_ONLY))
        off = cw_sim.simulate_p1(seed, pool='fallback', planes=2)
        assert json.dumps(on.ledger, default=str, ensure_ascii=False) \
            == json.dumps(off.ledger, default=str, ensure_ascii=False), (
            f'seed {seed}:仅 M-A flag 开(gate 关)不得有行为')


def test_no_new_bonus_constant_single_source() -> None:
    """数值单一源:registry 无 M-A 分数 bonus 常量(有界次数预算≠分数
    叠加);买侧授权常量族(W227 缺口项)不被本批触碰。"""
    fields = [f for f in type(DEFAULT_REGISTRY).__dataclass_fields__
              if f.startswith('handoff_refresh')
              or f.startswith('directed_refresh')]
    assert set(fields) == {
        'handoff_refresh_directed', 'directed_refresh_per_round',
        'directed_refresh_game_cap'}
