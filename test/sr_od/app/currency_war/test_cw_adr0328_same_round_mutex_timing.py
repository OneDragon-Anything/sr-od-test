# -*- coding: utf-8 -*-
"""W67/ADR-0328:r408 守卫时序缺口修复锁(no_same_round_buy_sell 回归)。

W66 合流总验最高价值异常:v2 no_same_round_buy_sell 同 seed 14→25、
n=400 达 96/400(24%)——同轮「BUY X(店新副本)+ SELL X(段首旧副本)」
振荡。机制(探针钉死 seeds 0/6/14):r408 守卫(same_round_mutex /
round_sell_blocked / _sell_blocked)查 ``session.v2_round_bought``,而该
集合只在 decide_prep 尾部(arbitrate 之后)统一登记——同趟 arbitrate 内
先采纳 BUY X 再裁决 SELL X 时,守卫读的是**上一段已买集**,双双过。

修法(ADR-0328):登记点从 decide_prep 尾部前移到**动作采纳处**(同一
事务域)——arbiter 主循环采纳 BuyCard 即登记 v2_round_bought(卖对称
登记 v2_round_sold)/补偿趟受益买重发/carry_gate 腾位买。本文件锁:
①同趟 BUY 采纳后 SELL 拒(回归核心);②先卖后买 r408 原方向不回归;
③去登记变异必须涌现违规(检查器非空转);④carry_gate 第三发射点登记;
⑤候选管线端到端(S3 merge 买 + free_bench 卖形态);⑥W66 探针 seed
重放零违规。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_intention import (
    HoardTarget,
    IntentionState,
)
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_no_same_round_buy_sell,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import arbiter as arbiter_mod
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    carry_gate_actions,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY

_SELL_TAGS = ('off_target', 'for_gold', 'free_bench')


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


def _locked_sess() -> StrategySession:
    """意向锁定 session(锁定套=列车同行;hoard=意向线采购集子样)。"""
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    s = _sess(v3_intention=ist)
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '花火', '瓦尔特', '三月七'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    return s


def _oscillation_state() -> GameState:
    """W66 违规形态(S3 同星豁免放大面):bench 满(9/9)含 X×2 同 1★,
    店内第 3 张 X → BUY X(merge,容量豁免)与 SELL X(free_bench,目标
    件让位)候选共现——修前同趟双双过,oscillation 白拿 XP。"""
    st = _state(bench=[_bench('花火', faction='量子同频', slot=i)
                       if i < 2 else _bench(f'C{i}', slot=i)
                       for i in range(9)],
                shop=[_card('花火', faction='量子同频', cost=2)])
    return st


def _ledger_row(st: GameState, actions: list, rn: int = 4) -> dict:
    """把 arbitrate 动作序列转录成检查器账本行(镜像 cw_sim 转录:
    BuyCard 带 card 嵌套 + reason;SellBench 带 name 取 state 快照槽)。"""
    acts: list[dict] = []
    for a in actions:
        if isinstance(a, BuyCard):
            acts.append({'__type__': 'BuyCard',
                         'card': {'x': a.card.x, 'faction': a.card.faction,
                                  'name': a.card.name, 'cost': a.card.cost},
                         'reason': a.reason})
        elif isinstance(a, SellBench):
            nm = (st.bench[a.bench_idx].char_id
                  if 0 <= a.bench_idx < len(st.bench or []) else '')
            acts.append({'__type__': 'SellBench',
                         'bench_idx': a.bench_idx, 'name': nm})
    return {'plane': 1, 'round_num': rn, 'actions': acts}


# --- ① 核心回归:同趟 BUY X 采纳后 SELL X 拒(登记点=采纳处) ---------------


def test_arbitrate_buy_then_sell_same_round_rejected() -> None:
    """ADR-0328 核心:同一趟 arbitrate 内先采纳 BUY X(merge,容量豁免)
    后,SELL X(free_bench 旧副本)候选被 same_round_mutex 拒——修前
    (登记延迟 decide_prep 尾)守卫读上一段已买集,双双过(W66 96/400)。"""
    sess = _sess()
    st = _oscillation_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      merge=True, source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='free_bench',
                       source='test', breakdown_hint={'name': '花火'})
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _REG)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert buys and buys[0].card.name == '花火', 'BUY X 应先采纳'
    assert not sells, f'同趟已采纳 BUY X → SELL X 应被拒(修前双双过):{res.actions}'
    assert '花火' in sess.v2_round_bought, '采纳即登记已买集(ADR-0328)'
    assert '花火' not in sess.v2_round_sold
    rejects = [r['reject'] for r in res.log if not r['accepted']]
    assert any('同轮已买' in (r or '') for r in rejects), rejects
    # 转录账本 → 检查器零违规(修复后 sim 侧同构)
    assert check_no_same_round_buy_sell(
        [_ledger_row(st, res.actions)]) == []


# --- ② 对称:先 SELL 后 BUY 的 r408 原方向同趟成立(不回归) ---------------


def test_arbitrate_sell_then_buy_same_round_rejected() -> None:
    """ADR-0328 对称臂:先采纳 SELL X → 后续 BUY X 候选被
    same_round_mutex(已卖禁买)拒——r408 原方向在同趟内也成立
    (修前 v2_round_sold 同样延迟登记,先卖后买也可双双过)。"""
    sess = _sess()
    # W197/ADR-0380 语义化适配:卖出件换非 TT 件银枝(原三月七=列车
    # 唯一件,现被卖侧下界守卫拒——TT 辖域由 test_cw_w197 承接;
    # 本锁的语义=同轮先卖后买的互斥,与件身份无关)
    st = _state(bench=[_bench('银枝', faction='星间旅人', slot=0)],
                shop=[_card('银枝', faction='星间旅人', cost=2)])
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '银枝'})
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    res = arbitrate([(sell_c, 5.0, {}), (buy_c, 4.0, {})], st, sess, _REG)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    assert sells and st.bench[sells[0].bench_idx].char_id == '银枝'
    assert not buys, f'同轮已卖 X → BUY X 应被拒(r408 不回归):{res.actions}'
    assert '银枝' in sess.v2_round_sold, '采纳即登记已卖集(ADR-0328)'
    rejects = [r['reject'] for r in res.log if not r['accepted']]
    assert any('同轮已卖' in (r or '') for r in rejects), rejects
    # 卖→买(腾位)合法形态对照:不同名卖后买不报(检查器边界)
    assert check_no_same_round_buy_sell(
        [_ledger_row(st, res.actions)]) == []


# --- ③ 变异自检:去登记变异必须涌现违规(守卫=唯一闸门) -------------------


def test_mutation_remove_registration_reveals_violation(monkeypatch) -> None:
    """ADR-0328 变异自检:把采纳处登记变异为 no-op(去守卫)→ 同趟
    BUY X 采纳后 SELL X 候选通过守卫 → check_no_same_round_buy_sell
    涌现违规——证明守卫是违规的唯一闸门,检查器非空转(回归锁自身
    有效性)。"""
    sess = _sess()
    st = _oscillation_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      merge=True, source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='free_bench',
                       source='test', breakdown_hint={'name': '花火'})
    monkeypatch.setattr(arbiter_mod, '_register_accepted',
                        lambda a, st_, sess_: None)
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _REG)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert sells, '变异(去登记)后 SELL X 应通过守卫——变异生效前提'
    assert '花火' not in sess.v2_round_bought
    v = check_no_same_round_buy_sell([_ledger_row(st, res.actions)])
    assert v and '花火' in v[0], \
        f'去守卫变异必须涌现违规(守卫=唯一闸门):{v}'


# --- ④ carry_gate 发射点:腾位买即登记同轮已买集 ---------------------------


def test_carry_gate_buy_registered_round_bought() -> None:
    """ADR-0328 第三发射点:carry_gate 腾位买核心 X 即登记
    v2_round_bought——carry_gate 先于 arbitrate 执行,不登记则同趟
    arbitrate 内 SELL X(旧副本)候选守卫读空集,双双过。"""
    sess = _locked_sess()
    bench = [_bench(n, faction='列车同行', slot=i)
             for i, n in enumerate(['三月七', '花火', '瓦尔特',
                                    '丹恒·饮月', '希儿', '爻光',
                                    '藿藿', '花火', '三月七'])]
    st = _state(round_num=4, gold=50,
                shop=[_card('姬子·启行', faction='列车同行', cost=4)],
                bench=bench)
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 2, 'carry_gate 应腾位买核心'
    buy = acts[1]
    assert isinstance(buy, BuyCard) and buy.card.name == '姬子·启行'
    assert '姬子·启行' in sess.v2_round_bought, \
        '腾位买即登记同轮已买集(ADR-0328)'
    sold_name = st.bench[acts[0].bench_idx].char_id
    assert sold_name in sess.v2_round_sold


# --- ⑤ 候选管线端到端(S3 merge 买 + free_bench 卖形态) --------------------


def test_decide_pipeline_oscillation_pair_rejected() -> None:
    """ADR-0328 端到端:generate_candidates 产出的 BUY X(merge)与
    SELL X(free_bench)候选共现(W66 违规形态)→ arbitrate 后 SELL X
    不在执行序列——修复落在真实候选管线上,非仅直构 arbitrate。"""
    sess = _locked_sess()
    st = _oscillation_state()
    cands = generate_candidates(st, sess, _REG)
    buys_x = [c for c in cands if isinstance(c.action, BuyCard)
              and c.action.card.name == '花火']
    sells_x = [c for c in cands if c.tag in _SELL_TAGS
               and c.breakdown_hint.get('name') == '花火']
    assert buys_x and sells_x, \
        f'候选管线应共现 BUY X + SELL X(修前双双过):' \
        f'buy={[(c.tag, c.merge) for c in buys_x]} ' \
        f'sell={[(c.tag, c.action.bench_idx) for c in sells_x]}'
    scored = [(buys_x[0], 5.0, {})] + [(sells_x[0], 1.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert not sells, f'管线产物 SELL X 应被同趟已买拒:{res.actions}'
    assert check_no_same_round_buy_sell(
        [_ledger_row(st, res.actions)]) == []


# --- ⑥ W66 探针 seed 重放零违规 ---------------------------------------------


def test_residual_seeds_zero_violation_v2() -> None:
    """ADR-0328 回归锁:W66 探针钉死的违规 seed(0/6/14)重放,
    no_same_round_buy_sell 归零——修复在真实 sim 决策链上生效。"""
    from sr_od.application.currency_war.sim.cw_sim import simulate_p1
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    for seed in (0, 6, 14):
        res = simulate_p1(seed, pool='snapshot', strategy=strat)
        v = check_no_same_round_buy_sell(res.ledger)
        assert not v, f'seed {seed} 残留同轮买卖(ADR-0328): {v[:3]}'
