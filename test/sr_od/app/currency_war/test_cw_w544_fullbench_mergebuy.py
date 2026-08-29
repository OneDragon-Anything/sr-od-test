# -*- coding: utf-8 -*-
"""W544 满栏合成买(ADR-0453)锁测试。

语义规格唯一源 = docs/game/currency_war/research/merge_mechanics.md §2.5
(满栏例外:点击能触发合成的牌满栏也买得进,自动多买 k = min(店内张数,
3−已有数 mod 3),全款 k×单价,绝不多买);裁决出处 = 用户权威裁决
「备战满时,触发合成的购买应该被支持,否则被迫卖有用角色」(ADR-0453)。

锁面:
① k 公式单一源(cw_state.merge_buy_k/merge_buy_completes);
② 满栏购买门(arbiter bench_capacity)合成触发放行/非合成兜底拒;
③ 金账 k×单价(arbiter._cost_of k-aware);
④ simulate 满栏多买执行(金 k×、店 k 张下架、合成落点);
⑤ carry_gate 满栏合成买不腾位卖(不满足合成条件原腾位链不动)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
    merge_buy_completes,
    merge_buy_k,
    same_star_count,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, x: int = 0, cost: int = 2,
          star: int = 1) -> ShopCard:
    return ShopCard(x=x, name=name, faction='仙舟', cost=cost, star=star)


def _bench(name: str, slot: int, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot + 1, char_id=name, faction='仙舟', star=star)


def _full_bench(own_names: list[str]) -> list[BenchChar | None]:
    """9 槽满员(own_names 之外用垫件 F* 填)。"""
    names = own_names + [f'F{i}' for i in range(BENCH_CAPACITY
                                                - len(own_names))]
    return [_bench(n, i) for i, n in enumerate(names)]


def _state(bench, shop, gold=50, deployed=None) -> GameState:
    return GameState(plane=1, round_num=4, gold=gold, level=5,
                     board={}, bench=bench, deployed=deployed or [],
                     shop=shop, hp=80, xp_progress=(0, 4))


# --- ① k 公式单一源 ------------------------------------------------------------


def test_merge_buy_k_formula() -> None:
    """k = min(店内张数, 3−已有数 mod 3)(merge_mechanics §2.5)。

    - 已有 1 份、店内 2 张 → k=2(一次点击自动多买 2 张凑合成);
    - 已有 1 份、店内 1 张 → k=1 但不完成合成(买进也无槽 → 拒);
    - 已有 2 份、店内 1 张 → k=1(旧 S3/ADR-0325 特例的一般式重现);
    - 店内 3 张超额不买:缺 2 张时店里 3 张只买 2(§2.5 绝不多买);
    - 不同星不计数(分组键 = 同名同星,与 _merge_bench 同口径)。
    """
    dep = [_bench('D', 0)]
    # 已有 1 份 X,店内 3 张 X:只买 3−1=2
    bench = _full_bench(['X'])
    shop = [_card('X', x=i) for i in range(3)]
    assert merge_buy_k('X', 1, bench, dep, shop) == 2
    assert merge_buy_completes('X', 1, bench, dep, shop) is True
    # 已有 1 份,店内 1 张:不完成合成
    assert merge_buy_completes('X', 1, bench, dep, [_card('X')]) is False
    # 已有 2 份,店内 1 张:k=1 完成
    bench2 = _full_bench(['X', 'X'])
    assert merge_buy_k('X', 1, bench2, dep, [_card('X')]) == 1
    assert merge_buy_completes('X', 1, bench2, dep, [_card('X')]) is True
    # 星级不同不计数:已有 2 份 1★,买 2★ 不合成
    assert merge_buy_completes('X', 2, bench2, dep, [_card('X', star=2)]) \
        is False
    # deploy 计入全场域:场上 1 份 + 店内 2 张 → k=2
    assert merge_buy_k('D', 1, _full_bench([]), dep,
                       [_card('D', x=0), _card('D', x=1)]) == 2
    # same_star_count 与 _merge_bench 分组键同域(bench∪deployed)
    assert same_star_count('D', 1, _full_bench([]), dep) == 1


# --- ② 满栏购买门(arbiter bench_capacity)--------------------------------------


def _bc_verdict(st: GameState, card: ShopCard):
    from sr_od.application.currency_war.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _check_constraint,
    )
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=BuyCard(card), tag='line_opportunistic',
                     source='shop')
    return _check_constraint('bench_capacity', cand, st, st,
                             StrategySession(), _REG)


def test_gate_allows_merge_buy_at_full_bench() -> None:
    """满栏 + 触发合成(own=1 + 店 2 张,k=2)→ 放行(ADR-0453 主升级面;
    旧门 own≠2 一律拒,用户裁决:被迫卖有用角色不可接受)。"""
    st = _state(_full_bench(['X']),
                [_card('X', x=0), _card('X', x=1), _card('Y', x=2)])
    assert _bc_verdict(st, _card('X')) is None, 'k=2 合成买应放行'


def test_gate_rejects_non_merge_at_full_bench() -> None:
    """满栏 + 不触发合成 → 仍拒(ADR-0283 守卫语义保留为兜底):
    ①未持有且店仅 1 张;②已有 1 份但店仅 1 张(k=1 凑不满 3)。"""
    st = _state(_full_bench(['X']),
                [_card('Z', x=0), _card('X', x=1)])
    reason = _bc_verdict(st, _card('Z'))
    assert reason is not None and reason.resource == 'bench'
    reason2 = _bc_verdict(st, _card('X'))
    assert reason2 is not None and reason2.resource == 'bench'


def test_gate_k1_case_unchanged() -> None:
    """旧 S3(ADR-0325)k=1 特例(own=2 + 店 1 张)行为不变(零漂移)。"""
    st = _state(_full_bench(['X', 'X']), [_card('X', x=0)])
    assert _bc_verdict(st, _card('X')) is None


# --- ③ 金账 k×单价 ---------------------------------------------------------------


def test_cost_of_charges_k_times_unit_cost() -> None:
    """满栏合成买金校验按 k×单价(§2.5 无价格优惠);非满栏恒 1×
    (arbiter._cost_of,gold_floor/interest_rule 同源取数)。"""
    from sr_od.application.currency_war.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision_v2.arbiter import _cost_of
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    cand = Candidate(action=BuyCard(_card('X', cost=2)),
                     tag='line_opportunistic', source='shop')
    st_full = _state(_full_bench(['X']),
                     [_card('X', x=0), _card('X', x=1)])
    assert _cost_of(cand, st_full) == 4, 'k=2 × 单价 2'
    st_open = _state([_bench('F', 0)], [_card('X', x=0)])
    assert _cost_of(cand, st_open) == 2, '非满栏 1×(零漂移)'


# --- ④ simulate 满栏多买执行 ------------------------------------------------------


def test_simulate_full_bench_multi_buy() -> None:
    """执行层:金扣 k×单价、店 k 张下架、合成产物落位、bench 恒 9 槽。"""
    bench = _full_bench(['X'])
    shop = [_card('X', x=1, cost=2), _card('X', x=2, cost=2),
            _card('Y', x=3, cost=1)]
    st = _state(bench, shop, gold=50)
    st2 = GameState.copy(st)
    from sr_od.application.currency_war.kernel.cw_state import (
        bench_occupied,
        simulate,
    )
    out = simulate(st2, BuyCard(shop[0]))
    assert out.gold == 50 - 4, 'k=2 × 单价 2 = 全款 4'
    assert bench_occupied(out.bench) == BENCH_CAPACITY, '满栏买入后仍满'
    assert len(out.bench) == BENCH_CAPACITY, '临时尾槽截回定长 9'
    two_star = [b for b in out.bench
                if b is not None and b.char_id == 'X' and b.star == 2]
    assert len(two_star) == 1, '3×1★ 合成 1×2★(落 bench,三张全备战栏)'
    assert [(c.name, c.x) for c in out.shop] == [('Y', 3)], \
        '店内 2 张同身份牌全部下架(自动多买)'


def test_simulate_full_bench_non_merge_noop() -> None:
    """执行层兜底:不触发合成 → 整动作 no-op(金不扣/牌不下架)。"""
    from sr_od.application.currency_war.kernel.cw_state import simulate
    bench = _full_bench(['X'])
    shop = [_card('Z', x=1, cost=2)]
    st = _state(bench, shop, gold=50)
    out = simulate(st, BuyCard(shop[0]))
    assert out.gold == 50
    assert [c.x for c in out.shop] == [1]


# --- ⑤ carry_gate:满栏合成买不腾位 ------------------------------------------------


def _locked_sess():
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    from sr_od.application.currency_war.cw_strategy import StrategySession
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    s.v3_intention = ist
    return s


def _carry_fixture(shop_cards: list[ShopCard]) -> GameState:
    """carry_gate 可达态(引 test_cw_w35 既有夹具口径):bench 满=全保护
    件(7 互异+2 重复份,重复份加权≥2 是 3合1 素材不进卖序),意向
    核心=姬子·启行 未持有、在店。"""
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    sess_bench_names = ['三月七', '花火', '瓦尔特', '丹恒·饮月', '希儿',
                        '爻光', '藿藿', '花火', '三月七']
    bench = [BenchChar(slot=i + 1, char_id=n, faction='列车同行', star=1)
             for i, n in enumerate(sess_bench_names)]
    st = _state(bench, shop_cards, gold=50)
    return st


def _locked_carry_sess():
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
    sess = _locked_sess()
    sess.v3_hoard = HoardTarget(frozenset({'姬子·启行', '三月七', '花火',
                                           '瓦尔特'}), frozenset(), 'locked')
    sess.v3_core_names = {'姬子·启行'}
    sess.v2_round_key = (1, 4)
    return sess


def test_carry_gate_mergebuy_skips_forced_sell() -> None:
    """意向核心未持有、店内 3 张(own=0 → k=3 完成合成)且 bench 满 →
    不卖任何件直接买(ADR-0453;裁决=「否则被迫卖有用角色」)。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        carry_gate_actions,
    )
    sess = _locked_carry_sess()
    shop = [_card('姬子·启行', x=i, cost=4) for i in range(3)]
    st = _carry_fixture(shop)
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 1 and isinstance(acts[0], BuyCard), \
        '合成触发买直达,无 SellBench'
    assert acts[0].card.name == '姬子·启行'


def test_carry_gate_non_merge_keeps_sell_chain() -> None:
    """不满足合成条件(own=0 + 店 1 张)→ 原腾位链逐位不动(零漂移):
    [SellBench(最弱保护件), BuyCard(核心)]。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        carry_gate_actions,
    )
    sess = _locked_carry_sess()
    st = _carry_fixture([_card('姬子·启行', x=0, cost=4)])
    acts = carry_gate_actions(st, sess, _REG)
    assert len(acts) == 2, '原语义:腾位卖 + 买核心'
