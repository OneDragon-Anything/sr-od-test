# -*- coding: utf-8 -*-
"""W82/ADR-0337:no_same 双快照互斥窗口修复锁(no_same_round_buy_sell 残留)。

W81 全窗复验(seeds 0-399,pool snapshot,ADR-0336 AD8 条件①)钉死的新
机制——ADR-0328 执行域对齐后仍存双快照窗口(seeds 259/304/342,
3/300,CI[0.34%,2.90%]):

1. 演进 CompTransaction 腾空 bench 槽 idx → ``exec_state.bench[idx]=None``;
2. 同趟 arbitrate 内先采纳 BuyCard X(分高),``simulate(working,…)`` 把
   X 落入该空槽 → ``working.bench[idx]=X``;
3. ``same_round_mutex`` 守卫读 **state**(exec_state)槽位 = None →
   短路跳过 → 放行;``index_drift`` 守卫读 **working** 槽位 = X,与候选
   intended(原始槽名 X)同名 → 放行;
4. SellBench(idx) 实卖刚买的同名卡 → 账本「BUY X → SELL X」→ no_same
   违规(实卖刚买卡,非名义违规)。

修法(ADR-0337,选型见 W82 报告 §0.2):``same_round_mutex`` 的 SellBench
分支改读 **working** 槽位(与 index_drift 同快照源)——r408「同轮已买
禁卖」按卖动作**执行时真正卖出的卡**(=working 槽,index_drift 已保证
== intended)裁决,双快照窗口结构性关闭。对已接受的卖,working 槽
char_id ≡ state 槽(char_id),登记/补偿路径无新漂移(推演见报告 §0.2)。
本文件锁:①双快照不一致态(腾空槽+同名买入落槽)→ 拒卖;②去登记变异
→ 卖通过 + 检查器涌现违规(守卫=唯一闸门,锁非空转);③W81 违规 seed
(259/304/342)确定性重放零违规(同 seed 同池=确定性断言,非统计叙述)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_no_same_round_buy_sell,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
    simulate,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2 import arbiter as arbiter_mod
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '公司', cost: int = 2) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=cost)


def _bench(name: str, faction: str = '公司', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    s.v2_round_key = (1, 4)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _exec_ledger(st: GameState, actions: list, rn: int = 4) -> dict:
    """按执行序转录账本(镜像 cw_sim:买带 card/reason;卖名=**执行时**
    槽内容——先行动作 simulate 推进,非入口快照)。"""
    wk = st.copy()
    acts: list[dict] = []
    for a in actions:
        if isinstance(a, BuyCard):
            acts.append({'__type__': 'BuyCard',
                         'card': {'x': a.card.x, 'faction': a.card.faction,
                                  'name': a.card.name, 'cost': a.card.cost},
                         'reason': a.reason})
        elif isinstance(a, SellBench):
            nm = (wk.bench[a.bench_idx].char_id
                  if 0 <= a.bench_idx < len(wk.bench or []) else '')
            acts.append({'__type__': 'SellBench', 'bench_idx': a.bench_idx,
                         'name': nm})
        wk = simulate(wk, a)
    return {'plane': 1, 'round_num': rn, 'actions': acts}


def _double_snapshot_state() -> GameState:
    """W81 seed 259 r1 形态的 exec_state:演进已腾空槽 0(其余 8 槽占用),
    arbitrate 收到的是执行域快照——候选(原始态生成)intended=三月七,
    槽 0 已空;同趟买入 三月七 将落该空槽。"""
    return _state(bench=[None] + [_bench(f'C{i}', slot=i)
                                  for i in range(1, 9)],
                  shop=[_card('三月七', faction='列车同行', cost=1)])


# --- ① 核心:双快照不一致态 → 拒卖 ---------------------------------------


def test_double_snapshot_emptied_slot_sell_rejected() -> None:
    """ADR-0337 核心:演进腾空槽(exec_state.bench[0]=None)+ 同趟买入
    X 落槽(working.bench[0]=X)+ 卖候选 intended=X——修前 mutex 读
    exec_state None 短路放行、index_drift 读 working 同名放行,实卖刚
    买卡(W81 seed 259 r1 形态);修后 mutex 读 working → X∈已买集 →
    「同轮已买」拒卖。"""
    sess = _sess()
    st = _double_snapshot_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _REG)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert buys and buys[0].card.name == '三月七', 'BUY X 应先采纳'
    assert not sells, \
        f'双快照窗口 SELL X 应被拒(同轮已买;修前实卖刚买卡):{res.actions}'
    assert '三月七' in sess.v2_round_bought, '采纳即登记已买集(ADR-0328)'
    rejects = [r['reject'] for r in res.log if not r['accepted']]
    assert any('同轮已买' in (r or '') for r in rejects), rejects
    # 执行序账本 → 检查器零违规(无卖执行)
    assert check_no_same_round_buy_sell(
        [_exec_ledger(st, res.actions)]) == []


# --- ② 变异自检:去登记 → 卖通过 + 违规涌现(守卫=唯一闸门) -------------


def test_mutation_no_registration_reveals_violation(monkeypatch) -> None:
    """ADR-0337 变异自检:把采纳处登记变异为 no-op(去守卫)→ 双快照
    窗口 SELL X 通过(mutex 读 working 槽但已买集空)→ 执行转录账本
    涌现 no_same 违规——证明守卫是违规的唯一闸门,检查器非空转。"""
    sess = _sess()
    st = _double_snapshot_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})
    monkeypatch.setattr(arbiter_mod, '_register_accepted',
                        lambda a, st_, sess_: None)
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _REG)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert sells, '变异(去登记)后 SELL X 应通过守卫——变异生效前提'
    assert '三月七' not in sess.v2_round_bought
    v = check_no_same_round_buy_sell([_exec_ledger(st, res.actions)])
    assert v and '三月七' in v[0], \
        f'去守卫变异必须涌现违规(守卫=唯一闸门):{v}'


# --- ③ W81 违规 seed 确定性重放零违规 ------------------------------------


def test_w81_violation_seeds_replay_zero() -> None:
    """ADR-0337 回归锁:W81 全窗复验钉死的违规 seed(259/304/342)
    确定性重放(同 seed 同池 snapshot),no_same_round_buy_sell 零违规
    ——修复在真实 sim 决策链上生效(与 ADR-0328 锁⑥同式)。"""
    from sr_od.application.currency_war.cw_sim import simulate_p1
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    for seed in (259, 304, 342):
        res = simulate_p1(seed, pool='snapshot', strategy=strat)
        v = check_no_same_round_buy_sell(res.ledger)
        assert not v, f'seed {seed} 残留同轮买卖(ADR-0337): {v[:3]}'
