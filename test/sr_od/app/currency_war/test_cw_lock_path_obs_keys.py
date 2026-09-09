"""锁线断头 P2 定向通道·观测件锁(硬砍批后残存;分键语义以
kernel/cw_intention.LOCK_PATH_OBS_KEY_PREFIXES 登记面与各测 docstring 为准)。

残存判据(硬砍批三保留条):① promote_candidates 派生公式(决策逻辑,锁的
是候选推导行为非计数);② p1_pair_frozen_obs 快照生命周期(G8 门的决策输入);
③ 零行为守卫(观测分键不得改变状态机终态)+ 键前缀注册门(schema/注册表级
守卫:一键族一锁)。

砍除面墓碑(硬砍批:遥测分键逐键计数锁 = 「遥测键名字符串锁」砍类,计数
值/键名失守不改变 bot 行为;键域由残存注册门测辖定):
- G5 fail_thickness 支 / G6 supply_gate_cull + neardeath_direction_obs_* /
  G7 handoff_frame/cand_empty(+neardeath 版)/ G8 promote_candidate_frame/
  nonempty 分键 / 锁定率帧计数(intention_frame_p*)。
"""
from __future__ import annotations

import copy
from dataclasses import is_dataclass
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionSignal,
    IntentionState,
    promote_candidates,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

#: P2 位面轮数真值(ADR-0366 语料:P2=7;与 test_cw_line_feasibility 同构)。
_P2_SESSION_TABLE = [1] * 7


def _counting_session() -> SimpleNamespace:
    return SimpleNamespace(cw4_counters={}, plane_node_table=list(_P2_SESSION_TABLE))


def _plain_session() -> SimpleNamespace:
    """无 cw4_counters 容器的 session(缺省形态;helper 应惰性建空 dict)。"""
    return SimpleNamespace(plane_node_table=list(_P2_SESSION_TABLE))


def _state(plane: int = 2, round_num: int = 1, hp: int = 40,
           level: int = 7, gold: int = 0) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.hp = hp
    st.level = level
    st.gold = gold
    return st


def _snapshot(obj) -> dict:
    """IntentionState → 可比较 dict(dataclass 递归;集合排序)。"""
    assert is_dataclass(obj)
    out = {}
    for f in obj.__dataclass_fields__.values():
        v = getattr(obj, f.name)
        if isinstance(v, set):
            out[f.name] = sorted(v)
        elif is_dataclass(v) and not isinstance(v, type):
            out[f.name] = _snapshot(v)
        else:
            out[f.name] = v
    return out


def _bench_char(name: str, slot: int) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions or ['?'])[0],
                     position_pref=ch.position_pref())


# ---------- G5:weakplane_exempt_eval(豁免 fail-closed 守卫;分键计数测已砍) ----------

def test_g5_weakplane_cull_hit_branch(monkeypatch):
    """厚资产 + 核心在手:豁免判据(设计稿 §2.2:厚度 ≥ A_min ∧ 核心
    在店/在手)预演命中 hit 支——fail-closed 期仍只计数,不放行。"""
    comp = ci.get_comp('DOT队')
    monkeypatch.setattr(ci, 'detect_signals',
                        lambda s: [IntentionSignal(3, 'core_card', 'DOT队',
                                                   't', 1.0)])
    st = _state(plane=2)
    # 五名 core 各 1★ = 厚度 5.0 ≥ A_min(registry.revoke_evidence_min_thickness)
    st.bench = [_bench_char(n, i)
                for i, n in enumerate(comp.core_chars[:5])]
    sess = _counting_session()
    out = update_intention(st, IntentionState(), sess, None)
    ct = state_of(sess).cw4_counters
    assert ct.get('weakplane_exempt_eval') == 1
    assert ct.get('weakplane_exempt_eval_hit') == 1
    # 零行为守卫:hit 支不产生豁免——弱面线不会被锁
    assert out.locked_comp != 'DOT队'


# ---------- G7/G8 之间的分键计数测已砍(墓碑见模块 docstring) ----------

# ---------- G8:promote_candidates 纯派生(决策逻辑) ----------

def _pair_bond_comp(pair: tuple[str, ...]):
    """pair 体系键交集的首条 v2 线(非弱面;测试定位用派生,不手写线名)。"""
    from sr_od.application.currency_war.kernel.cw_intention import _pair_bond_keys
    bonds = _pair_bond_keys(pair)
    for c in ci._v2_comps():
        if 2 not in (c.weak_planes or ()) \
                and (set(c.form_tiers) | set(c.sub_tiers)) & bonds:
            return c
    raise AssertionError('无 pair 体系键交集线:测试前提失效')


def test_g8_promote_candidates_pure_derivation(monkeypatch):
    """晋升候选集公式逐支验证(设计稿 §2.1):pair 体系键交集 / evicted /
    weak_planes / _core_reachable / plane==2 的 G>ε 门;纯函数不突变输入。"""
    pair = ('仙舟', '列车同行')
    comp = _pair_bond_comp(pair)
    monkeypatch.setattr(ci, 'line_completion_feasibility',
                        lambda *a, **k: 0.5)
    st = _state(plane=2)
    st.shop = [ShopCard(x=0, name=ci.intention_core(comp), cost=3)]
    ist = IntentionState()
    ist.p1_pair_frozen_obs = pair
    before = _snapshot(ist)
    cands = promote_candidates(st, ist, None, None)
    assert comp.name in [c.name for c in cands]
    # evicted 支:驱逐线出局
    ist_ev = IntentionState()
    ist_ev.p1_pair_frozen_obs = pair
    ist_ev.evicted.add(comp.name)
    assert comp.name not in [c.name for c in promote_candidates(st, ist_ev, None, None)]
    # G 门(plane==2):G ≤ ε 出局
    monkeypatch.setattr(ci, 'line_completion_feasibility',
                        lambda *a, **k: 0.0)
    assert comp.name not in [c.name for c in promote_candidates(st, ist, None, None)]
    # 空快照(P1 无配方方向)恒空
    assert promote_candidates(st, IntentionState(), None, None) == []
    # 纯函数守卫:调用前后 IntentionState 逐位不变
    assert _snapshot(ist) == before


# ---------- p1_pair_frozen_obs 快照生命周期 ----------

def test_frozen_pair_snapshot_lifecycle():
    """P1 派生非空对随帧冻结;进 P2 后 p1_pair 清空而快照保留
    (退场前的冻结副本语义,设计稿 §2.1 观测载体)。
    锁红重推(T-171 支持度端口降档):原 fixture 希儿单卡即锁(支持度
    在手二元 1.0)语义已被分级公式取代——希儿单卡 = 0.5 开线候选不再
    即锁(出处 = T-171 设计方案 §5.1/§6.3-4,取代 ADR-0519 C2 的
    post-state 条款),锁红 ≠ 改动错,故按新口径重推 fixture:希儿+1
    去重放大器(桑博,贝腿 2 成员)= 1.0 满支持构造锁帧;生命周期
    断言本体(冻结/清空/快照保留)不变。"""
    st1 = _state(plane=1, round_num=1)
    st1.bench = [_bench_char('希儿', 0), _bench_char('桑博', 1)]
    # 希儿+桑博:去重后贝腿 2 成员 = 1.0 ≥ 锁门槛 → 派生非空(T-171 §5.1)
    ist = IntentionState()
    out1 = update_intention(st1, ist, None, None)
    assert out1.p1_pair                       # P1 配方对已锁帧
    assert out1.p1_pair_frozen_obs == out1.p1_pair
    out2 = update_intention(_state(plane=2, round_num=1), out1, None, None)
    assert out2.p1_pair == ()                 # exit_p1 清空(既有语义零变更)
    assert out2.p1_pair_frozen_obs            # 快照保留


# ---------- 缺省零漂移 + 只观测零行为守卫 ----------

def test_zero_drift_with_and_without_counter_session(monkeypatch):
    """守卫锁(设计稿约束「分键代码不改变任何判定结果」):同输入下,
    session=None / 计数 session / 无容器 session 三臂终态 IntentionState
    逐位相等——对照帧零漂移。"""
    monkeypatch.setattr(ci, 'detect_signals',
                        lambda s: [IntentionSignal(3, 'core_card', 'DOT队',
                                                   't', 1.0),
                                   IntentionSignal(1, 'strategy', '绯英欢愉',
                                                   't', 1.0)])
    base = None
    for sess in (None, _counting_session(), _plain_session()):
        st = _state(plane=2)
        out = update_intention(copy.deepcopy(st), IntentionState(), sess, None)
        snap = _snapshot(out)
        if base is None:
            base = snap
        assert snap == base, '观测分键改变了状态机终态:零行为守卫破线'
    # session=None 臂兼辖「纯逻辑直调零异常」契约(抛错即本测红),
    # 原单测 test_session_none_counts_nothing 为其真子集,已删。


def test_default_session_counter_container_lazily_created():
    """容器缺席 → 惰性建空 dict 再计数(先例 = mandate_v1/entry 初始化面);
    全部键落在登记前缀族内(与既有键族零交集,设计稿 §4 条款③)。"""
    sess = _plain_session()
    update_intention(_state(plane=2), IntentionState(), sess, None)
    ct = getattr(state_of(sess), 'cw4_counters', None)
    assert isinstance(ct, dict) and ct
    for k in ct:
        assert k.startswith(ci.LOCK_PATH_OBS_KEY_PREFIXES), f'未登记键:{k}'
