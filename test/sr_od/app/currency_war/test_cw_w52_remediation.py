"""W52 批锁:「拒绝→补裁决」通用回连机制 + S3/S4/S5 + N1 前置修复。

载体:决策框架 v2 层4 回连(§1-§5 设计稿 W52 r4 + 任务书 AD9 裁决)。
全部单帧锁(构造 GameState → 断言 decide_prep/arbitrate 输出);
**bench 构造按槽位模型**(定长 9,None=空槽——ADR-0316)。

逐链两向锁 + 防环边界锁 + N1 前置锁 + expect 代际锁 + 标签链锁 +
遥测锚点锁;检查网 decision_v2_remedy_loop(连续放弃轮≥3)另行锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_intention import HoardTarget
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    RefreshShop,
    SellBench,
    ShopCard,
    SwapDeploy,
    bench_occupied,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '公司', cost: int = 2) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=cost)


def _bench(name: str, faction: str = '公司', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 4, 'gold': 40, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _locked_sess(**kw) -> StrategySession:
    """意向锁定 session(锁定套=列车同行;hoard=意向线采购集子样)。"""
    from sr_od.application.currency_war.cw_intention import IntentionState
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'   # COMP_LIBRARY v2 套名(姬子列车家族)
    s = _sess(v3_intention=ist, **kw)
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    return s


# --- S3 同星豁免(H3 口径;§2/§7) ----------------------------------------------


def _full_bench_with(names_stars: list) -> GameState:
    """9/9 满员 bench(槽位表;names_stars=[(名, 星), ...] 恰好 9 件)。"""
    assert len(names_stars) == 9
    st = _state(bench=[_bench(n, slot=i, star=s)
                       for i, (n, s) in enumerate(names_stars)])
    assert bench_occupied(st.bench) == 9
    return st


def test_s3_merge_buy_exempt_at_full_bench() -> None:
    """S3 正向(H3 口径):bench 9/9 + 同名**同 1★ 已 2 份** + 店内第 3 张
    1★ → 买被采纳(容量豁免;合并净 −1,不占新槽)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 1), ('X', 1)] + [(f'C{i}', 1) for i in range(7)])
    st.shop = [_card('X', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=True, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert [r['accepted'] for r in res.log] == [True], (
        f'9/9+同 1★ 已 2 份+第 3 张 1★ → 合并买入应容量豁免(净−1):'
        f'{res.log[0]["reject"] if res.log else "无 log"}')


def test_s3_weighted2_star2_not_merge_still_rejected() -> None:
    """S3 反例 A:bench 9/9 + **1 个 2★(加权2)** + 店内第 3 张 1★ →
    仍拒(同星计数=1,不合成交净+1——旧加权判据的误标例)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 2)] + [(f'C{i}', 1) for i in range(8)])
    st.shop = [_card('X', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=False, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['accepted'] is False, \
        '1 个 2★(加权2)+第 3 张 1★ 不合成(同星=1)→ 满员仍拒'
    assert 'bench 满' in (res.log[0]['reject'] or '')


def test_s3_non_merge_buy_still_rejected_at_full() -> None:
    """S3 反例 B:bench 9/9 + 非 merge 买 → 仍拒(容量不豁免普通买)。"""
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([(f'C{i}', 1) for i in range(9)])
    st.shop = [_card('散件', cost=1)]
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         merge=False, source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['accepted'] is False


def test_s3_will_merge_generation_mirror_same_star() -> None:
    """S3 生成侧镜像(candidates.will_merge):2× 同 1★ + 店第 3 张 1★ →
    merge=True;1× 2★ + 店第 3 张 1★ → merge=False(旧加权判据误标例)。"""
    from sr_od.application.currency_war.decision_v2.candidates import (
        generate_candidates,
    )
    # 正向:同 1★ 已 2 份
    st1 = _state(gold=60, bench=[_bench('X', slot=0, star=1),
                                 _bench('X', slot=1, star=1),
                                 _bench('C0', slot=2)],
                 shop=[_card('X', cost=1)])
    sess = _sess()
    sess.v2_round_key = (1, 4)
    m1 = [c for c in generate_candidates(st1, sess, _REG)
          if isinstance(c.action, BuyCard) and c.action.card.name == 'X']
    assert m1 and m1[0].merge, '同 1★ 已 2 份+第 3 张 1★ → merge 候选'
    # 反例:1× 2★(加权2)不是同星 2 份
    st2 = _state(gold=60, bench=[_bench('X', slot=0, star=2),
                                 _bench('C0', slot=1)],
                 shop=[_card('X', cost=1)])
    m2 = [c for c in generate_candidates(st2, sess, _REG)
          if isinstance(c.action, BuyCard) and c.action.card.name == 'X']
    assert m2 and not m2[0].merge, \
        '1× 2★(加权2)不构成同 1★ 2 份 → 非 merge(旧判据误标)'


def test_s3_merge_buy_simulates_net_minus1_at_full() -> None:
    """S3 执行侧:9/9 满员合并买入 simulate 后 bench 占用 8(净 −1),
    新卡不占槽(合成载体留原槽);非合并买在满员时仍 no-op。"""
    from sr_od.application.currency_war.cw_state import simulate
    sess = _sess()
    sess.v2_round_key = (1, 4)
    st = _full_bench_with([('X', 1), ('X', 1)] + [(f'C{i}', 1) for i in range(7)])
    st.gold = 60
    st.shop = [_card('X', cost=1)]
    out = simulate(st, BuyCard(st.shop[0]))
    assert bench_occupied(out.bench) == 8, \
        f'合并买入净 −1(期望 8,实得 {bench_occupied(out.bench)})'
    x2 = [b for b in out.bench if b is not None and b.char_id == 'X']
    assert len(x2) == 1 and x2[0].star == 2
    assert out.gold == 60 - 1
    # 非合并买满员 no-op
    st2 = _full_bench_with([(f'C{i}', 1) for i in range(9)])
    st2.gold = 60
    st2.shop = [_card('散件', cost=1)]
    out2 = simulate(st2, BuyCard(st2.shop[0]))
    assert out2.gold == 60 and bench_occupied(out2.bench) == 9


# --- 补偿骨架锁(§1.1/§1.2;AD9 随批带修) -------------------------------------


def test_rejections_collect_only_resource_type() -> None:
    """rejections 收集面反锁:非资源型拒绝(刷新预算/纪律型)不进
    rejections;资源型拒绝(gold_floor/bench/deploy)进(§1.1 捕获条件
    + 正分闸)。"""
    from dataclasses import replace
    # 非资源型:refresh 被 refresh_budget 拒(金足)→ rejections 空
    reg = replace(_REG, refresh_game_cap=1, levelup_reserve_gold=0)
    sess = _sess()
    sess.v2_round_key = (1, 4)
    sess.v2_refresh_used = 1
    st = _state(round_num=2, gold=60, shop=[_card('甲', cost=1)])
    cands = [
        (Candidate(action=RefreshShop(cost=2), tag='refresh', source='test'),
         2.0, {}),
        (Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                   source='test'), 5.0, {}),
    ]
    res = arbitrate(cands, st, sess, reg)
    # log 序=主循环(买)在前、refresh 收尾在后
    assert [r['accepted'] for r in res.log] == [True, False]
    assert res.rejections == [], \
        '纪律型拒绝(刷新预算)不得进 rejections(§1.1 捕获条件)'
    # 资源型:金不足买被 gold_floor 拒(war 地板 30,金 25 费 4)
    sess2 = _sess(v3_mode='war')
    sess2.v2_round_key = (1, 4)
    st2 = _state(round_num=4, gold=25, shop=[_card('甲', cost=4)])
    scored2 = [(Candidate(action=BuyCard(st2.shop[0]), tag='line_carry',
                          source='test'), 5.0, {})]
    res2 = arbitrate(scored2, st2, sess2, _REG)
    assert len(res2.rejections) == 1
    rj = res2.rejections[0]
    assert rj.reason.resource == 'gold'
    assert rj.reason.shortfall == 30 + 4 - 25
    assert rj.cand.action.card.name == '甲'


def test_reject_log_format_compat() -> None:
    """log 行格式不变(W52 兼容锁):拒绝字段仍是「约束名:人读原因」
    原字符串语义(RejectReason.describe 迁移,判读面零波及)。"""
    sess = _sess(v3_mode='war')
    sess.v2_round_key = (1, 4)
    st = _state(round_num=4, gold=25, shop=[_card('甲', cost=4)])
    scored = [(Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                         source='test'), 5.0, {})]
    res = arbitrate(scored, st, sess, _REG)
    assert res.log[0]['reject'] == 'gold_floor:金<30(地板;现25-费4)', \
        res.log[0]['reject']


# --- N1 前置锁(第 0 步;§0.5) ------------------------------------------------


def test_n1_bench_double_count_two_buys_both_accepted() -> None:
    """N1:同轮两笔买候选(均可采纳)→ **双采纳**。

    构造:bench 7/9 占用 + 金足(60,经济地板 50)+ 两笔 1 费买。
    第二笔检查时 working=8/9(**恰剩 1 空槽**)——修复前
    ``bench_occupied(working)+pending_bench=8+1=9≥9`` 被双计误拒;
    修复后(pending_bench 删除,容量判据=占用计数)8<9 → 采纳。
    """
    sess = _sess()
    sess.v2_round_key = (1, 4)
    bench = [_bench(f'C{i}', slot=i) for i in range(7)]
    st = _state(round_num=4, gold=60, bench=bench,
                shop=[_card('甲', cost=1), _card('乙', cost=1)])
    scored = [
        (Candidate(action=BuyCard(st.shop[0]), tag='line_carry',
                   source='test'), 5.0, {}),
        (Candidate(action=BuyCard(st.shop[1]), tag='line_carry',
                   source='test'), 4.0, {}),
    ]
    res = arbitrate(scored, st, sess, _REG)
    buys = [r for r in res.log if r['tag'] == 'line_carry']
    assert len(buys) == 2
    rejects = [(r['desc'], r['reject']) for r in buys]
    assert all(r['accepted'] for r in buys), (
        f'双买应双采纳(第二笔检查 working=8/9 恰剩 1 空槽,'
        f'不得被 pending_bench 双计误拒):{rejects}')
