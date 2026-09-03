# -*- coding: utf-8 -*-
"""test_cw_sim_mutex_tx 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- adr0328_same_round_mutex_timing: test_cw_adr0328_same_round_mutex_timing.py
- adr0337_mutex_working_snapshot: test_cw_adr0337_mutex_working_snapshot.py
- adr0283_sim_bench_guard: test_cw_adr0283_sim_bench_guard.py
- action_v2: test_cw_action_v2.py
- w666_replay_context_freeze: test_cw_w666_replay_context_freeze.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== adr0328_same_round_mutex_timing ====================

from sr_od.application.currency_war.kernel.cw_intention import (
    HoardTarget,
    IntentionState,
)

from sr_od.application.currency_war.sim.checks.ledger import check_no_same_round_buy_sell
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

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    for seed in (0, 6, 14):
        res = simulate_p1(seed, pool='snapshot', strategy=strat)
        v = check_no_same_round_buy_sell(res.ledger)
        assert not v, f'seed {seed} 残留同轮买卖(ADR-0328): {v[:3]}'


def test_seed181_remedy_seed_fallback_zero_violation() -> None:
    """F5 回归锁(seed 181 确定性复现):腾位补偿的「唯一可卖=种子」
    死锁豁免路径曾绕过同轮已买守卫——同趟 arbitrate 刚采纳 BuyCard
    三月七(d2_engine_seed 单张)后,同趟 bench_capacity 补偿把该
    刚买种子当最弱件卖回(r408 主守卫读 v2_round_bought 有登记,
    但 seed_age_blocked 分支绕开 sell_priority_key,补偿组重验只查
    资源三约束)。修后该 seed 重放零违规(ADR-0267 0 容忍)。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    res = simulate_p1(181, pool='snapshot', strategy=strat, planes=1)
    v = check_no_same_round_buy_sell(res.ledger)
    assert not v, f'seed 181 同轮买卖复发(腾位补偿种子兜底): {v[:3]}'


# ==================== adr0337_mutex_working_snapshot ====================

from sr_od.application.currency_war.sim.checks.ledger import check_no_same_round_buy_sell
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
    simulate,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2 import arbiter as arbiter_mod
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_adr0337_mutex_working_snapshot_REG = DEFAULT_REGISTRY


def _adr0337_mutex_working_snapshot_card(name: str, faction: str = '公司', cost: int = 2) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=cost)


def _adr0337_mutex_working_snapshot_bench(name: str, faction: str = '公司', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _adr0337_mutex_working_snapshot_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _adr0337_mutex_working_snapshot_sess(**kw) -> StrategySession:
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
    arbitrate 收到的是执行域快照——候选(原始态生成)intended=银枝
    (W197/ADR-0380 语义化适配:原三月七=列车唯一件,现被卖侧下界守卫
    先拒——本锁语义=双快照互斥窗口,与件身份无关,换非 TT 件银枝),
    槽 0 已空;同趟买入 银枝 将落该空槽。"""
    return _adr0337_mutex_working_snapshot_state(bench=[None] + [_adr0337_mutex_working_snapshot_bench(f'C{i}', slot=i)
                                  for i in range(1, 9)],
                  shop=[_adr0337_mutex_working_snapshot_card('银枝', faction='星间旅人', cost=1)])


# --- ① 核心:双快照不一致态 → 拒卖 ---------------------------------------


def test_double_snapshot_emptied_slot_sell_rejected() -> None:
    """ADR-0337 核心:演进腾空槽(exec_state.bench[0]=None)+ 同趟买入
    X 落槽(working.bench[0]=X)+ 卖候选 intended=X——修前 mutex 读
    exec_state None 短路放行、index_drift 读 working 同名放行,实卖刚
    买卡(W81 seed 259 r1 形态);修后 mutex 读 working → X∈已买集 →
    「同轮已买」拒卖。"""
    sess = _adr0337_mutex_working_snapshot_sess()
    st = _double_snapshot_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '银枝'})
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _adr0337_mutex_working_snapshot_REG)
    buys = [a for a in res.actions if isinstance(a, BuyCard)]
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert buys and buys[0].card.name == '银枝', 'BUY X 应先采纳'
    assert not sells, \
        f'双快照窗口 SELL X 应被拒(同轮已买;修前实卖刚买卡):{res.actions}'
    assert '银枝' in sess.v2_round_bought, '采纳即登记已买集(ADR-0328)'
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
    sess = _adr0337_mutex_working_snapshot_sess()
    st = _double_snapshot_state()
    buy_c = Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                      source='test')
    sell_c = Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '银枝'})
    monkeypatch.setattr(arbiter_mod, '_register_accepted',
                        lambda a, st_, sess_: None)
    res = arbitrate([(buy_c, 5.0, {}), (sell_c, 1.0, {})], st, sess, _adr0337_mutex_working_snapshot_REG)
    sells = [a for a in res.actions if isinstance(a, SellBench)]
    assert sells, '变异(去登记)后 SELL X 应通过守卫——变异生效前提'
    assert '银枝' not in sess.v2_round_bought
    v = check_no_same_round_buy_sell([_exec_ledger(st, res.actions)])
    assert v and '银枝' in v[0], \
        f'去守卫变异必须涌现违规(守卫=唯一闸门):{v}'


# --- ③ W81 违规 seed 确定性重放零违规 ------------------------------------


def test_w81_violation_seeds_replay_zero() -> None:
    """ADR-0337 回归锁:W81 全窗复验钉死的违规 seed(259/304/342)
    确定性重放(同 seed 同池 snapshot),no_same_round_buy_sell 零违规
    ——修复在真实 sim 决策链上生效(与 ADR-0328 锁⑥同式)。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    for seed in (259, 304, 342):
        res = simulate_p1(seed, pool='snapshot', strategy=strat)
        v = check_no_same_round_buy_sell(res.ledger)
        assert not v, f'seed {seed} 残留同轮买卖(ADR-0337): {v[:3]}'


# ==================== adr0283_sim_bench_guard ====================

class _GreedyBuyStub:
    """无脑买桩:每段返回 12 张买(逼 bench 满,验证守卫跳过)。"""

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_shop_screen(self, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import BuyCard, ShopCard
        name = next(n for n in CHARACTERS if CHARACTERS[n].cost == 1)
        card = ShopCard(x=100, faction='?', name=name, cost=1)
        return [BuyCard(card=card, reason='stub') for _ in range(12)]


def test_sim_bench_capacity_guard() -> None:
    """⑤ bench 满(BENCH_CAPACITY=9)后买被跳过:容量不变式 + 计数披露。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    from sr_od.application.currency_war.kernel.cw_state import BENCH_CAPACITY
    res = simulate_p1(1, pool='fallback', strategy=_GreedyBuyStub())
    skips = 0
    for row in res.ledger:
        st = row.get('state') or {}
        assert len(st.get('bench') or []) <= BENCH_CAPACITY, \
            f"r{row.get('round_num')} bench 超容(批⑰ F6 回归)"
        skips += (row.get('sim') or {}).get('bench_full_skipped_buys', 0)
    assert skips > 0, '满仓买确实发生且被守卫拦截(桩逼出超容场景)'


def test_sim_batch_discloses_guard_count() -> None:
    """批量报告披露 bench_full_skipped_buys(计数口径存在且 ≥0)。"""

    from sr_od.application.currency_war.sim.runner import simulate_p1_batch
    rep = simulate_p1_batch(10, pool='fallback', seed_base=500,
                            ledger=False, checks=False)
    assert rep['bench_full_skipped_buys'] >= 0


# ==================== action_v2 ====================

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

from sr_od.application.currency_war.sim.checks.ledger import check_comp_tx_atomicity, check_skip_fence_pairing
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    CompTransaction,
    FillSpec,
    GameState,
    SellDeployed,
    ShopCard,
    SwapDeploy,
    _recount_board,
    deployed_occupied,
    iter_occupied_deployed,
    mutate_bench_deployed,
    sell_refund,
    simulate,
)


def _char(name: str, slot: int = 0, row: str = 'back') -> BenchChar:
    """注册表真值构造 BenchChar(faction/cost 单一源)。"""
    c = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row)


def _xianzhou_trio() -> list[BenchChar]:
    """仙舟铁三角(= cw_line_defs._CORE_TRIO;注册表真值)。"""
    from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
    return [_char(n, slot=i) for i, n in enumerate(sorted(_CORE_TRIO))]


def _old_line_deployed(n: int = 3) -> list[BenchChar]:
    """旧档(DOT 过渡占位):非仙舟阵营角色若干(贝洛伯格系)。"""
    names = [n for n, c in CHARACTERS.items()
             if (c.factions or [''])[0] == '贝洛伯格'][:n]
    assert len(names) == n, '测试假设:贝洛伯格系 ≥3 人(注册表)'
    return [_char(nm, slot=i) for i, nm in enumerate(names)]


def _tx_state() -> GameState:
    """DOT2 在场 + 仙舟铁三角 bench 齐 的单帧(验收1 构造)。"""
    # ADR-0392:构造器入参 → __post_init__ pad 槽位表(与 simulate 出态同形)
    st = GameState(gold=20, level=8,
                   deployed=_old_line_deployed(3),
                   bench=_xianzhou_trio() + [_char('青雀', slot=3)])
    st.board = _recount_board(st.deployed)
    return st


# ---------- 1. DOT2 → 仙舟3 整档替换(无半档) ----------

def test_comp_transaction_full_swap_no_half_state():
    st = _tx_state()
    old_names = [c.char_id for c in iter_occupied_deployed(st.deployed)]
    _income = sum(sell_refund(
        c.star, CHARACTERS[c.char_id].cost)
        for c in iter_occupied_deployed(st.deployed)) \
        + sell_refund(1, CHARACTERS['青雀'].cost)
    tx = CompTransaction(
        deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
        undeploy=[],
        # 旧档整档直接卖出 + 新档换位余料(青雀)卖出:一次敲定无残留
        sell=[(0, 'deployed'), (1, 'deployed'), (2, 'deployed'),
              (3, 'bench')],
        fill=None,
        reason='evolve:DOT2→仙舟3')
    out = simulate(st, tx)
    # 旧档 0 人在场:deployed 全为铁三角
    trio = {c.char_id for c in iter_occupied_deployed(out.deployed)}
    from sr_od.application.currency_war.kernel.cw_line_defs import _CORE_TRIO
    assert trio == set(_CORE_TRIO)
    assert deployed_occupied(out.deployed) == 3   # ADR-0392 占用数
    # 新档全员在场:仙舟 3(ADR-0312 W50 全集口径——board 另含铁三角的
    # 流派/副阵营键,精确等值由下行 _recount_board 一致性锁辖)
    assert out.board.get('仙舟') == 3
    # 无半档:board 与 deployed 聚合一致;旧档/余料不在 bench 不在场上
    # (ADR-0316 槽位表:全空=bench_occupied==0,len(bench) 恒 9)
    assert out.board == _recount_board(out.deployed)
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out.bench) == 0
    assert all(n not in {b.char_id for b in out.bench if b is not None}
               for n in old_names)
    # 卖出回金入账(旧档 3 人 + 青雀)
    assert out.gold == 20 + _income
    # 原状态不被改(simulate 纯函数)
    assert deployed_occupied(st.deployed) == 3 \
        and bench_occupied(st.bench) == 4
    assert out.action_log[-1] == {'action': 'CompTransaction',
                                  'result': 'applied',
                                  'reason': 'evolve:DOT2→仙舟3',
                                  'income': _income,
                                  'fill_cost': 0}


# ---------- 2. 原子性:任一子步资源不足 → 整体拒绝 ----------

def test_comp_transaction_rejected_gold_short_no_partial_apply():
    st = _tx_state()
    st.gold = 0
    st.shop = [ShopCard(x=0, faction='仙舟', name='符玄', cost=3)]
    tx = CompTransaction(
        deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
        undeploy=[0, 1, 2],
        sell=[(3, 'bench')],
        fill=[FillSpec(source='shop', idx=0, row='back')],
        reason='evolve+fill')
    out = simulate(st, tx)
    # 整体拒绝:状态与原状态完全一致(无任何部分应用痕迹)
    out.action_log = []   # 唯一允许的差异 = 拒绝记录本身
    st.action_log = []
    # ADR-0316:simulate 入口 pad bench 到定长 9,原子性对照只看占用内容
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out.bench) == bench_occupied(st.bench)
    assert [c.char_id for c in out.bench if c] \
        == [c.char_id for c in st.bench if c]
    assert out.deployed == st.deployed and out.gold == st.gold
    # 拒绝记录进账本(checks 可见)
    assert simulate(st, tx).action_log[-1]['result'] == 'rejected'
    assert 'gold_short' in simulate(st, tx).action_log[-1]['reason']


def test_comp_transaction_rejected_cap_and_overlap():
    st = _tx_state()
    st.level = 3   # cap=3:终态 deployed 3+4=7 > cap → 拒绝
    tx = CompTransaction(deploy=[(0, 'front'), (1, 'back'), (2, 'back'),
                                 (3, 'back')],
                         undeploy=[], sell=[], reason='cap')
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'rejected'
    assert 'deploy_cap_exceeded' in out.action_log[-1]['reason']
    assert deployed_occupied(out.deployed) == 3   # 未动(ADR-0392 占用数)
    # deploy 与 sell 指向同 bench 槽 → 拒绝
    tx2 = CompTransaction(deploy=[(0, 'front')], undeploy=[],
                          sell=[(0, 'bench')], reason='overlap')
    assert 'overlap' in simulate(st, tx2).action_log[-1]['reason']


# ---------- 3. deployed 生命周期:SellDeployed / SwapDeploy ----------

def test_sell_deployed_lifecycle():
    st = _tx_state()
    sold = st.deployed[1]
    sold.equips = ['虚构装备']
    out = simulate(st, SellDeployed(1, reason='evict_replaced'))
    assert deployed_occupied(out.deployed) == 2   # ADR-0392 占用数
    assert all(c is not sold for c in iter_occupied_deployed(out.deployed))
    assert out.board == _recount_board(out.deployed)
    assert out.gold == 20 + sell_refund(
        sold.star, CHARACTERS[sold.char_id].cost)
    assert out.equips == ['虚构装备']   # 装备回收进 owned(守恒假设)
    assert out.action_log[-1]['result'] == 'applied'
    # 越界 → 拒绝 + 状态不变
    out2 = simulate(st, SellDeployed(99))
    assert out2.action_log[-1]['result'] == 'rejected'
    out2.action_log = []
    st.action_log = []
    from sr_od.application.currency_war.kernel.cw_state import bench_occupied
    assert bench_occupied(out2.bench) == bench_occupied(st.bench)
    assert out2.deployed == st.deployed and out2.gold == st.gold


def test_swap_deploy_equips_follow_char():
    st = _tx_state()
    in_char, out_char = st.bench[0], st.deployed[0]
    in_char.equips = ['铁三角专属件']
    out = simulate(st, SwapDeploy(0, 0, reason='swap'))
    assert out.deployed[0].char_id == in_char.char_id
    assert out.deployed[0].equips == ['铁三角专属件']   # 装备随人走
    assert out.deployed[0].position_pref == out_char.position_pref  # 继承排
    assert out.bench[0].char_id == out_char.char_id
    assert out.board == _recount_board(out.deployed)
    # 越界 → 拒绝
    assert simulate(st, SwapDeploy(0, 99)).action_log[-1]['result'] \
        == 'rejected'


def test_mutate_bench_deployed_v2_actions():
    from sr_od.application.currency_war.kernel.cw_state import (
        bench_occupied,
        pad_bench,
    )
    bench = pad_bench(_xianzhou_trio() + [_char('青雀', slot=3)])
    deployed = _old_line_deployed(3)
    n0 = (bench_occupied(bench), deployed_occupied(deployed))
    mutate_bench_deployed(bench, deployed, SellDeployed(0))
    assert deployed_occupied(deployed) == n0[1] - 1   # ADR-0392 置 None
    mutate_bench_deployed(bench, deployed, SwapDeploy(0, 0))
    assert bench_occupied(bench) == n0[0] \
        and deployed_occupied(deployed) == n0[1] - 1
    # 事务部分:重建干净 fixture(上面两步已移动槽位)
    bench = pad_bench(_xianzhou_trio() + [_char('青雀', slot=3)])
    deployed = _old_line_deployed(3)
    tx = CompTransaction(deploy=[(0, 'front'), (1, 'back'), (2, 'back')],
                         undeploy=[0, 1, 2], sell=[(3, 'bench')],
                         reason='evolve')
    mutate_bench_deployed(bench, deployed, tx)
    assert {c.char_id for c in iter_occupied_deployed(deployed)} == {
        c.char_id for c in _xianzhou_trio()}
    assert bench_occupied(bench) == 3   # 旧档下场进 bench(转移语义;卖出走生产侧)
    # 拒绝路径:越界事务整体不动
    tx_bad = CompTransaction(deploy=[(99, 'front')], undeploy=[],
                             sell=[], reason='bad')
    b2, d2 = list(bench), list(deployed)
    mutate_bench_deployed(b2, d2, tx_bad)
    assert [(c.char_id, c.slot) for c in b2 if c is not None] == \
        [(c.char_id, c.slot) for c in bench if c is not None]
    assert deployed_occupied(d2) == deployed_occupied(deployed)


# ---------- 4. checks 渗透(含变异探针:去门必须涌现违规) ----------

def _agg(dep: list[dict]) -> dict[str, int]:
    """账本行 deployed 的羁绊全集聚合(ADR-0312 W50;unit_bond_tags 同源)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_bond_equips import unit_bond_tags
    out: dict[str, int] = {}
    for d in dep:
        ns = SimpleNamespace(
            char_id=d.get('char_id') or '',
            position_pref=d.get('position_pref') or 'back',
            faction=d.get('faction') or '',
            equips=d.get('equips') or [])
        tags = unit_bond_tags(ns)
        if tags:
            for t in tags:
                out[t] = out.get(t, 0) + 1
            continue
        f = d.get('faction')
        if f and f != '?':
            out[f] = out.get(f, 0) + 1
    return out


def _row(actions: list[dict], board: dict | None = None,
         deployed: list[dict] | None = None) -> dict:
    dep = deployed if deployed is not None else [
        {'char_id': '藿藿', 'faction': '仙舟', 'slot': 0,
         'position_pref': 'back'}]
    return {'plane': 1, 'round_num': 3, 'state': {
        'board': board if board is not None else _agg(dep),
        'deployed': dep}, 'actions': actions, 'sim': {}}


def test_check_comp_tx_atomicity_locks():
    ok = _row([
        {'__type__': 'CompTransaction', 'result': 'applied',
         'reason': 'evolve'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    assert check_comp_tx_atomicity([ok]) == []
    # 变异①:board 与 deployed 聚合不一致(半档残留)→ 涌现违规
    bad = _row(ok['actions'], board={'仙舟': 2})
    v = check_comp_tx_atomicity([bad])
    assert v and '不一致' in v[0]
    # 变异②:拒绝记录缺 reject_reason → 涌现违规
    rej = _row([{'__type__': 'CompTransaction', 'result': 'rejected'}])
    v = check_comp_tx_atomicity([rej])
    assert v and 'reject_reason' in v[0]
    # 拒绝动作不触发 board 一致性分支(拒绝轮状态未变,不检查)
    rej2 = _row([{'__type__': 'CompTransaction', 'result': 'rejected',
                  'reject_reason': 'gold_short:0+1-3<0'}],
                board={})
    assert check_comp_tx_atomicity([rej2]) == []


def test_check_skip_fence_pairing_locks():
    paired = _row([
        {'__type__': 'SellDeployed', 'result': 'applied'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    assert check_skip_fence_pairing([paired]) == []
    # 变异①:显式动作无 skip_fence(围栏静默跳过)→ 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SellDeployed', 'result': 'applied'}])])
    assert v and '未配对' in v[0]
    # 变异②:skip_fence 无显式动作(误记)→ 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'skip_fence', 'reason': 'x'}])])
    assert v and '误记' in v[0]
    # 变异③:skip_fence 缺 reason → 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SwapDeploy', 'result': 'applied'},
              {'__type__': 'skip_fence', 'reason': ''}])])
    assert v and 'reason' in v[0]
    # 变异④:同轮多条 skip_fence → 违规
    v = check_skip_fence_pairing([
        _row([{'__type__': 'SwapDeploy', 'result': 'applied'},
              {'__type__': 'skip_fence', 'reason': 'x'},
              {'__type__': 'skip_fence', 'reason': 'x'}])])
    assert v and '多条' in v[0]
    # W65/ADR-0323:rejected 显式动作**不**占显式通道(被拒不消耗围栏,
    # 同轮围栏照跑)→ 不要求配对;被拒轮记 skip_fence = 误记
    rej = _row([{'__type__': 'CompTransaction', 'result': 'rejected',
                 'reject_reason': 'duplicate_on_board:万敌'}])
    assert check_skip_fence_pairing([rej]) == [], \
        '被拒事务不要求 skip_fence 配对(W65:被拒不跳围栏)'
    rej_skip = _row([
        {'__type__': 'CompTransaction', 'result': 'rejected',
         'reject_reason': 'duplicate_on_board:万敌'},
        {'__type__': 'skip_fence', 'reason': 'explicit_action_v2'}])
    v = check_skip_fence_pairing([rej_skip])
    assert v and '误记' in v[0], \
        '被拒轮记 skip_fence = 误记(围栏没跳却记账)'


# ---------- 5. 开关联动:显式动作轮围栏跳过(sim 集成) ----------

class _ExplicitStub:
    """测试桩策略:首次见 deployed 非空时发一笔 SellDeployed(其余轮空)。"""

    def __init__(self) -> None:
        self.fired = False

    def update_target(self, st, sess, screen) -> None:   # noqa: ARG002
        pass

    def decide_shop_screen(self, sess, screen):   # noqa: ARG002
        # ADR-0392:槽位表滤 None;SellDeployed 打占用槽(空槽会拒)
        st = sess.shop_state_frame
        occ = [i for i, d in enumerate(st.deployed) if d is not None]
        if not self.fired and occ:
            self.fired = True
            return [SellDeployed(occ[0], reason='plugin_recycle')]
        return []


def test_sim_explicit_action_skips_fence_with_ledger():
    stub = _ExplicitStub()
    res = simulate_p1(7, strategy=stub, pool='fallback')
    assert stub.fired, '桩应在首轮部署后点火'
    assert res.fence_skips == 1
    assert res.explicit_action_rejects == 0
    # 发出轮:SellDeployed applied + skip_fence 同轮配对 + board 一致
    fired_rows = [row for row in res.ledger
                  if any(a.get('__type__') == 'SellDeployed'
                         for a in row.get('actions') or [])]
    assert len(fired_rows) == 1
    row = fired_rows[0]
    types = [a.get('__type__') for a in row['actions']]
    assert 'skip_fence' in types
    assert (row.get('sim') or {}).get('fence_skipped') is True
    # board 一致(ADR-0312 W50 全集口径;_agg 与 unit_bond_tags 同源)
    assert _agg((row.get('state') or {}).get('deployed') or []) \
        == dict((row.get('state') or {}).get('board') or {})
    # 其余轮无 skip_fence(围栏照常)
    assert sum(1 for row in res.ledger
               if any(a.get('__type__') == 'skip_fence'
                      for a in row.get('actions') or [])) == 1
    # 基线不变式:bench 容量/金非负由既有检查网辖,此处冒烟
    assert all(len(r.get('state', {}).get('bench', [])) <= BENCH_CAPACITY
               for r in res.ledger)


# ==================== w666_replay_context_freeze ====================

import inspect

from sr_od.application.currency_war.kernel import cw_deploy_logic

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

# W652 取证的两帧所在局(修前 HEAD 版重放对这两局 r6 各判 lag=2)
_SEEDS = (630027, 630035)


def _lag_frames(seed: int) -> list[tuple[int, int]]:
    """跑一局,返回逐轮 (round_num, deploy_lag_units)。"""
    res = simulate_p1(seed, pool='snapshot', planes=1)
    return [(int(row.get('round_num') or 0),
             int((row.get('sim') or {}).get('deploy_lag_units') or 0))
            for row in res.ledger]


def test_replay_context_freezed_lag_zero() -> None:
    """修后绿锁:取证两局全部轮 deploy_lag_units 恒 0。

    冻结后重放趟与真趟行动语境同判据——真趟围栏已认可的件已上场,
    残余件在行动语境下是合法 held,不再产生口径过判红。
    """
    for seed in _SEEDS:
        frames = _lag_frames(seed)
        assert all(n == 0 for _, n in frames), (seed, frames)


def test_not_deploying_mutation_still_red(monkeypatch) -> None:
    """变异锁:注入「真部署趟不部署」,检查必须仍能抓出(防修成恒 0)。

    注意:decision_v2(candidates/scoring)也调 select_deployments,
    变异只对来自 cw_sim 的调用生效,且真趟吞掉后紧随的同轮重放趟
    放行原逻辑(重放趟在冻结语境下会把真趟本应上场的件判为残留)。
    """
    orig = cw_deploy_logic.select_deployments
    state = {'replay_next': False}

    def wrapped(bench, **kw):
        caller = inspect.currentframe().f_back
        from_cw_sim = (caller is not None
                       and caller.f_globals.get('__name__', '').endswith('engine_p1'))
        if from_cw_sim:
            if state['replay_next']:
                state['replay_next'] = False
                return orig(bench, **kw)
            state['replay_next'] = True
            return [], list(range(len(bench)))
        return orig(bench, **kw)

    monkeypatch.setattr(cw_deploy_logic, 'select_deployments', wrapped)
    for seed in _SEEDS:
        state['replay_next'] = False
        frames = _lag_frames(seed)
        assert any(n > 0 for _, n in frames), (seed, frames)

