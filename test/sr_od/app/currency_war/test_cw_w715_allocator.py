"""死亡窗支出分配器 v6 锁组(W684 v6 设计 §7 判前锁 + W706 §8 六条
实现级瑕疵的锁面增补;模型主体 = decision_v2/allocator.py)。

锁面 ↔ 性质映射(v6 §7;W706 §8-6 三增补已并入计数):
- P1 量纲锁 → test_triplet_units_and_hand_recalc(三元组同单位断言 +
  W690 同式手算重算,**禁按 v5 式对拍**;§8-1 Δp_eff 定义式先钉);
- P2 破坏族重derive 锁 → test_breaking_edge_rederive_13vs7(13-vs-7
  构造反例数字作断言用例);复合合并锁 → test_comp_merge_atomic;
  状态推进锁 → test_state_advance_budget_guard;
- P3 稳态断言锁 → test_domain_predicate_current_value_ttf(辖域谓词
  现值直用,无迟滞;**T,T,F 振荡序列显式用例**,W706 §8-4);
- P5 两域分域锁 → test_two_domain_split_verdict(同一提案两域异判,
  含 Tier-2 边界帧大额提案显式用例,W706 §8-6);复判登记锁 →
  test_param_set_recheck_registered(弱标定带不固化的机制化);
- P6/W706 §8-6 增补:DP-oracle 最优性锁 → test_dp_oracle_optimality;
  刷新估计器锁 → test_refresh_estimator_hand_recalc(§8-2 估计器
  可手算性,不锁精度)。

出处纪律:每条锁 docstring 引设计章/证明命题;锁推导不锁分布。
"""
from __future__ import annotations

import dataclasses
import itertools
import logging
import random

import pytest

from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision_v2 import allocator
from sr_od.application.currency_war.decision_v2.allocator import (
    ALLOC_PARAM_SET,
    ALLOC_PARAM_SET_VERSION,
    ALLOCATOR_ENABLED,
    AllocDomain,
    AllocProposal,
    _opportunity_cost,
    _refresh_dpeff_estimate,
    _supply_impl,
    _w_per_battle,
    alloc_domain,
    allocate,
    allocator_run,
)
from sr_od.application.currency_war.decision_v2.ev import interest_cost
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)

logging.disable(logging.CRITICAL)


# ---------- 构造器(复用 test_cw_p1_terminal_release 的帧构造纪律) ----------

def _faction_names(faction: str, k: int) -> list[str]:
    return [n for n, c in CHARACTERS.items()
            if faction in (c.factions or ())][:k]


def _deploy(state: GameState, names: list[str]) -> GameState:
    state.deployed = [
        BenchChar(slot=i + 1, char_id=n,
                  faction=(CHARACTERS[n].factions or ['?'])[0], star=1)
        for i, n in enumerate(names)]
    return state


def _stop_state(gold: int = 200, hp: int = 80, level: int = 8,
                round_num: int = 7, n_dep: int = 5) -> GameState:
    """停手窗域帧:form_ok 兜底路(phase_fallback:两体系达成)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, level, gold, hp
    st.round_num = round_num
    st.node_type = 'battle'
    _deploy(st, _faction_names('仙舟', 3) + _faction_names('列车同行',
                                                          max(0, n_dep - 3)))
    return st


def _death_state(gold: int = 200, round_num: int = 8) -> GameState:
    """死亡域帧:hp=10 ∈ 遭遇+boss 双穿透链域(S0 上界 ≤ ε)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 8, gold, 10
    st.round_num = round_num
    st.node_type = 'battle'
    _deploy(st, _faction_names('仙舟', 2))
    return st


def _sess(table: list[str] | None = None) -> StrategySession:
    s = StrategySession()
    s.plane_node_table = table if table is not None else ['battle'] * 9
    return s


def _stop_registry():
    """承接门目标档位置 0(gap 恒 0,隔离承接维——A/B 注册表注入面,
    禁 monkeypatch 生产函数;被隔离维非本锁对象)。"""
    return dataclasses.replace(DEFAULT_REGISTRY,
                               handoff_gate_tier_target=0)


DEATH_TABLE = ['battle'] * 7 + ['encounter', 'boss']


# ---------- P5/复判登记锁(W690 §4-4;P23 §4 适用边界 1) ----------

def test_param_set_recheck_registered() -> None:
    """参数集版本化契约:版本号单源、复判条款带 Δp 标定来源与重开
    阈值、弱标定带以登记数据存在(不进决策分支——带端点只作复判
    对照,改动须同步 version+recheck)。"""
    assert ALLOC_PARAM_SET.version == ALLOC_PARAM_SET_VERSION
    assert ALLOC_PARAM_SET.delta_p_band == (0.03, 0.117)
    assert ALLOC_PARAM_SET.ev_band == (-97.0, 19.0)
    assert '0.35' in ALLOC_PARAM_SET.recheck
    assert 'Δp' in ALLOC_PARAM_SET.recheck
    # 开关缺省形态(策略开关生命周期第 3 态=开臂,报告附验证记录)
    assert ALLOCATOR_ENABLED is True


# ---------- P1 量纲锁(§4-P1;W706 §8-1 Δp_eff 定义式) ----------

def test_triplet_units_and_hand_recalc() -> None:
    """三元组同单位断言 + W690 同式手算重算:跨档买件的
    Δp_eff = Δwin_eq×L_c×hp_to_gold + w(win_eq 单源插值的每场金当量
    口径,W706 §8-1 定义式;场/金单位分明)。构造:2 仙舟板(e0=0,
    进度 2/3),店内第 3 仙舟(跨档件)。"""
    st = _stop_state()
    _deploy(st, _faction_names('仙舟', 2))
    third = next(n for n in _faction_names('仙舟', 6)
                 if n not in {d.char_id for d in st.deployed})
    st.shop = [ShopCard(x=1, name=third, cost=3)]
    props = _supply_impl(st, _sess(), _stop_registry(),
                         AllocDomain.STOP_WINDOW)
    buys = [p for p in props if p.kind == 'buy' and p.name == third]
    assert buys, '跨档件应被救回面供给(merge∨bench空位∧deploy空位)'
    p = buys[0]
    reg = _stop_registry()
    ss = _sess()
    w = _w_per_battle(st, ss)
    l_c = max(0.0, reg.vd_p1_loss_intercept
              + reg.vd_p1_loss_slope_rung * 0)   # rung0 手算
    hr = reg.h3_win_rate
    # win_eq 手算:跨档前 e=0 frac=2/3;跨档后 e=1 frac=0
    before = hr[0] + (2 / 3) * (hr[1] - hr[0])
    expect = (hr[1] - before) * l_c * reg.hp_to_gold + w
    assert p.dpeff == pytest.approx(expect)
    assert p.dpeff > 0
    # 单位断言:dpeff 金/场、m_eff 场、cost 金(int)
    assert 0 < p.dpeff < 100 and isinstance(p.cost, int) and p.cost == 3
    assert 0 < p.m_eff <= 30


# ---------- W706 §8-2 增补:刷新估计器锁(可手算性,不锁精度) ----------

def test_refresh_estimator_hand_recalc(monkeypatch) -> None:
    """估计器 = P(一刷见可上场目标)×目标部署每场金当量增量(单样本
    代理;§8-2 单样本代理选项)。手算重算:p_hit=Σrefresh_prob 封顶 1,
    增量取跨档档差式。目标名集 monkeypatch(隔离意向依赖,非生产桩)。"""
    from sr_od.application.currency_war.decision_v2 import candidates
    st = _stop_state()
    _deploy(st, _faction_names('仙舟', 2))
    tgt = _faction_names('仙舟', 6)[5]
    monkeypatch.setattr(candidates, '_target_names',
                        lambda state, session: {tgt})
    reg = _stop_registry()
    got = _refresh_dpeff_estimate(st, _sess(), reg)
    ch = CHARACTERS[tgt]
    from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
    p_hit = refresh_prob(st.level, ch.cost)
    w = _w_per_battle(st, _sess())
    l_c = reg.vd_p1_loss_intercept + reg.vd_p1_loss_slope_rung * 0
    hr = reg.h3_win_rate
    before = hr[0] + (2 / 3) * (hr[1] - hr[0])
    assert got == pytest.approx(min(1.0, p_hit)
                                * ((hr[1] - before) * l_c
                                   * reg.hp_to_gold + w))


# ---------- P5 两域分域锁(P23.2 vs P23.3;W706 §8-6 边界帧用例) ----------

def test_two_domain_split_verdict() -> None:
    """同一提案(Δp>0,大额 C=84)两域异判:停手窗域 EV<0 拒(P23.2
    中心负判方向),死亡域第二账式 V=m_eff×Δp_eff>0 放(P23.3)。
    死亡域帧即 Tier-2 边界帧显式用例(S0 加权成本=参数集内替换,
    W706 §8-5 落点)。"""
    reg = DEFAULT_REGISTRY
    w = 1.0   # 构造小增量(w 量级,刻意不取跨档 Δp:纯 w 大额提案在
    # 停手窗必负,是 P23.2 负判的最强稳健形态)
    big = AllocProposal(kind='levelup', dpeff=w, m_eff=0.0, cost=84)
    st_stop, ss_stop = _stop_state(), _sess()
    big_stop = dataclasses.replace(big)
    m_stop = allocator._m_horizon(st_stop, ss_stop, reg)
    v_stop = m_stop * w - _opportunity_cost(st_stop, ss_stop, reg,
                                            big_stop,
                                            AllocDomain.STOP_WINDOW)
    assert v_stop < 0, '停手窗域大额低增量提案必须判拒(P23.2)'
    st_death, ss_death = _death_state(), _sess(DEATH_TABLE)
    big_death = dataclasses.replace(big)
    m_death = min(allocator._m_horizon(st_death, ss_death, reg),
                  allocator._deploy_free_battles(st_death, ss_death, reg))
    v_death = m_death * w - _opportunity_cost(st_death, ss_death, reg,
                                              big_death,
                                              AllocDomain.DEATH)
    assert v_death > 0, '死亡域第二账式必须放行(P23.3 攥金死锁反命题)'


# ---------- P2 破坏族重derive 锁(13-vs-7 构造反例;§4-P2) ----------

def _prop(kind: str, v: float, cost: int, name: str = '') -> AllocProposal:
    return AllocProposal(kind=kind, dpeff=0.0, m_eff=1.0, cost=cost, v=v,
                         name=name, bench_slots=0)


def test_breaking_edge_rederive_13vs7() -> None:
    """破坏边语义化:静态店面对拍账 13(买 A7+B6)vs 重derive 后继账
    7(刷新期望值)。断言:①后继账不占优时取静态账(13>7,买组合);
    ②后继账占优时 refresh 独占本帧——静态 13 **不叠加**进账(记账=
    兑现:买方账对旧店面的估值随刷新作废,后继店态下帧重derive)。"""
    buys = [_prop('buy', 7.0, 3, 'A'), _prop('buy', 6.0, 3, 'B')]
    reg = DEFAULT_REGISTRY
    st = GameState()
    # ① 重derive 账 7 < 静态 13 → 取买组合
    out = allocate(buys + [_prop('refresh', 7.0, 2)], 100, 5, reg, st)
    assert {p.kind for p in out} == {'buy'} and len(out) == 2
    # ② 重derive 账 14 > 静态 13 → refresh 独占,13 不叠加(总账=14 非 27)
    out = allocate(buys + [_prop('refresh', 14.0, 2)], 100, 5, reg, st)
    assert [p.kind for p in out] == ['refresh']
    assert sum(p.v for p in out) == pytest.approx(14.0)


# ---------- P2 复合合并锁(前置边闭合;§2.1 ②) ----------

def test_comp_merge_atomic(monkeypatch) -> None:
    """板满帧店内目标件 × 升级闭合为 Π_comp:复合提案原子含
    [BuyCard, LevelUp]、cost 为和;单独买(无 deploy 位)不被救回面
    供给——复合账不可拆选。"""
    from sr_od.application.currency_war.decision_v2 import candidates
    from sr_od.application.currency_war.kernel.cw_economy import (
        xp_click_cost,
    )
    st = _stop_state()
    xz = _faction_names('仙舟', 8)
    pad = [n for n in CHARACTERS if n not in xz]
    _deploy(st, (xz + pad)[:8])   # 板满(level8 cap=8;仙舟不足他件补位)
    tgt = next(n for n in _faction_names('列车同行', 8)
               if n not in {d.char_id for d in st.deployed})
    st.shop = [ShopCard(x=1, name=tgt, cost=3)]
    monkeypatch.setattr(candidates, '_target_names',
                        lambda state, session: {tgt})
    props = _supply_impl(st, _sess(), _stop_registry(),
                         AllocDomain.STOP_WINDOW)
    comps = [p for p in props if p.kind == 'comp']
    assert comps, '板满+目标件在店应闭合 Π_comp'
    c = comps[0]
    kinds = {type(a).__name__ for a in c.actions}
    assert kinds == {'BuyCard', 'LevelUp'}
    assert c.cost == 3 + xp_click_cost(st)
    assert not any(p.kind == 'buy' and p.name == tgt for p in props)
    out = allocate(props, 500, 5, DEFAULT_REGISTRY, st)
    if any(p.kind == 'comp' for p in out):
        sel = next(p for p in out if p.kind == 'comp')
        assert len(sel.actions) == 2   # 原子:两动作同帧同组发射


# ---------- P6/§8-6 增补:DP-oracle 最优性锁 ----------

def test_dp_oracle_optimality() -> None:
    """帧内分配 = 精确组合选择:随机构造帧(金/槽约束 + 刷新互斥)
    上,allocate 输出值与 2^n 全枚举 oracle 一致(含不可行子集剔除;
    W706 §8-3:禁落成单维金背包)。"""
    rng = random.Random(715)
    reg = DEFAULT_REGISTRY
    st = GameState()
    for _trial in range(20):
        n = 7
        others = [
            AllocProposal(kind='buy', dpeff=0.0, m_eff=1.0,
                          cost=rng.randint(1, 9),
                          v=round(rng.uniform(-2, 10), 2),
                          name=f'c{i}',
                          bench_slots=rng.choice([0, 1]))
            for i in range(n)]
        refresh = _prop('refresh', round(rng.uniform(-1, 12), 2), 2)
        budget = rng.randint(5, 30)
        bench_free = rng.randint(0, 3)
        got = allocate(others + [refresh], budget, bench_free, reg, st)
        gv = sum(p.v for p in got)
        # oracle:出清负判 → 只取 v>0;刷新互斥(独占或不含);全子集
        pos = [p for p in others if p.v > 0]
        best = 0.0
        for mask in range(1 << len(pos)):
            sub = [pos[i] for i in range(len(pos)) if mask >> i & 1]
            if not sub:
                continue
            if sum(p.cost for p in sub) > budget:
                continue
            if sum(p.bench_slots for p in sub) > bench_free:
                continue
            best = max(best, sum(p.v for p in sub))
        if refresh.v > 0:
            best = max(best, refresh.v)
        assert gv == pytest.approx(best)
        assert sum(p.cost for p in got) <= budget
        assert sum(p.bench_slots for p in got) <= bench_free


# ---------- P2 状态推进锁 / FM-A6 金流守卫 ----------

def test_state_advance_budget_guard() -> None:
    """R_t 状态推进:选中组合成本和 ≤ E_t=max(0,gold−reserve)
    (W635-F1 储备消费不改写);预算 0 帧(金在储备段内)零动作。"""
    res = allocator_run(_stop_state(gold=40), _sess(),
                        _stop_registry())
    assert res.active and not res.actions
    assert res.frame['budget'] == 0
    res = allocator_run(_stop_state(gold=200), _sess(), _stop_registry())
    total = res.frame['budget']
    spent = sum(res.frame['alloc_gold'].values())
    assert spent <= total <= 200


# ---------- P3 稳态断言锁 + W706 §8-4 T,T,F 显式用例 ----------

def test_domain_predicate_current_value_ttf() -> None:
    """辖域谓词现值直用:alloc_domain 无跨帧记忆(纯函数),序列
    [death, 非, death] → [DEATH, None, DEATH]——T,T,F 振荡残余的
    行为=谓词现值逐帧跟随(2/3 帧接管、1/3 帧回现状,有界;断言
    实测违约才升级机制,本层不预置迟滞——§0 核实降级)。"""
    d1 = alloc_domain(_death_state(), _sess(DEATH_TABLE),
                      DEFAULT_REGISTRY)
    mid = alloc_domain(_stop_state(), _sess(), _stop_registry())
    d2 = alloc_domain(_death_state(), _sess(DEATH_TABLE),
                      DEFAULT_REGISTRY)
    assert (d1, mid, d2) == (AllocDomain.DEATH, AllocDomain.STOP_WINDOW,
                             AllocDomain.DEATH)
    # 常规帧出辖域:P_t 不被构造
    plain = GameState()
    plain.plane, plain.hp, plain.gold, plain.level = 1, 80, 30, 6
    plain.round_num, plain.node_type = 2, 'battle'
    assert alloc_domain(plain, _sess(), DEFAULT_REGISTRY) is None


# ---------- W718 修复回归:刷新臂预算门(实锤 640564 金负值) ----------

def test_budget_zero_blocks_refresh() -> None:
    """R_t 预算约束必须门控刷新分支:budget=0(金贴储备线)帧刷新
    不出手;cost>budget 同拒——修复前 allocate() 只比 V 值绕过
    _feasible,26 帧/10 局 budget=0 出手、640564 金 −2(W718 §一面2)。
    回归锁:预算 0 帧零分配器出手(含刷新臂)。"""
    reg = DEFAULT_REGISTRY
    st = GameState()
    r14 = _prop('refresh', 14.0, 2)
    assert allocate([r14], 0, 5, reg, st) == []
    assert allocate([r14], 1, 5, reg, st) == []   # cost 2 > budget 1
    out = allocate([r14], 2, 5, reg, st)
    assert [p.kind for p in out] == ['refresh']   # 预算内仍放行


# ---------- W718 修复回归:Π_up 继承 [12]/[33] 授权白名单 ----------

def test_levelup_supply_inherits_auth_whitelist(monkeypatch) -> None:
    """供给层继承上游授权白名单(ev.levelup_ev_basis,与 arbiter 升级
    门/段级检查同谓词):白名单拒('')的帧分配器不出升级/复合提案
    (辖域冲突裁决:豁免的是濒死止损,不越过白名单;seed 640516
    seg_unjustified_levelup 2 起回归)。放行臂名回写 auth_basis 观测
    字段供检查器对账。"""
    from sr_od.application.currency_war.decision_v2 import ev as ev_mod
    st = _stop_state(level=8, n_dep=8)   # 板满
    from sr_od.application.currency_war.kernel.cw_state import BenchChar
    st.bench = [BenchChar(slot=1, char_id='青雀', faction='仙舟', star=1)]
    monkeypatch.setattr(ev_mod, 'levelup_ev_basis',
                        lambda *a, **k: '')   # 白名单拒
    props = _supply_impl(st, _sess(), _stop_registry(),
                         AllocDomain.STOP_WINDOW)
    assert not [p for p in props if p.kind in ('levelup', 'comp')], \
        '白名单拒帧不得供给升级/复合提案'
    monkeypatch.setattr(ev_mod, 'levelup_ev_basis',
                        lambda *a, **k: 'static_ev')   # 白名单放行
    props = _supply_impl(st, _sess(), _stop_registry(),
                         AllocDomain.STOP_WINDOW)
    lus = [p for p in props if p.kind == 'levelup']
    assert lus and lus[0].actions[0].auth_basis == 'static_ev'




# ---------- 记账扩展:分配器帧位(v6 §6) ----------

def test_alloc_frame_bit_disclosure() -> None:
    """辖域帧披露各渠道获配金(frame['alloc_gold'] 按 kind 分账)+
    参数集版本字段;非辖域帧 active=False 带原因(记账位逐帧可判读)。"""
    res = allocator_run(_death_state(), _sess(DEATH_TABLE),
                        DEFAULT_REGISTRY)
    assert res.frame['active'] is True
    assert res.frame['domain'] == 'death'
    assert res.frame['param_set'] == ALLOC_PARAM_SET_VERSION
    assert set(res.frame['alloc_gold'].keys()) == {
        'buy', 'levelup', 'refresh', 'comp'}
    res2 = allocator_run(GameState(), _sess(), DEFAULT_REGISTRY)
    assert res2.frame['active'] is False
