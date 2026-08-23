"""ADR-0302 危机局修复锁(批㉝ F3 危机囤金 + F4 应急集内容)。

锁定对象(decision_v2 filters/scoring 应急段):
① 危机囤金修复:应急态(hp≤emergency_hp)且金≥囤金线(40)时,
   战力买候选加分差恰为 registry.crisis_buy_bias(score_state 无 hp 项,
   hp 20/40 双态差分=偏置的加性锁);息崖(金 52→49 买)不被
   偏置翻越([18] 不为苟住破息);
② 危机搜牌:危机态 refresh 放行(层2)+ 评分 ≥ refresh_ev−费;
   非囤金应急态(金<40)refresh 仍滤出;
③ 应急集内容:for_gold(卖弱件)/levelup(升级)放行(0291 旧锁
   同步改);pair/copy/bond_fallback/synthesize 滤出;
④ 端到端:批㉝ 5 危机局 seeds(1/25/75/79)检查项
   decision_v2_crisis_gold_hoard 违规=0(5→0 的回归锁)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_sim_checks import (
    check_decision_v2_crisis_gold_hoard,
)
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.filters import (
    crisis_hoard_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 8, 'gold': 72, 'level': 6,
            'board': {'公司': 6},
            'deployed': [_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 20}
    base.update(kw)
    return GameState(**base)


# --- ① 危机囤金买偏置 --------------------------------------------------------


def test_crisis_buy_bias_additive() -> None:
    """危机态战力买加分:hp 20 vs 40 同板差分恰=_CRISIS_BUY_BIAS
    (score_state 无 hp 项,双态唯一差异=偏置);且危机态分>0。"""
    sess = _sess()
    st_crisis = _state(shop=[_card('藿藿')])          # hp=20 金=72
    st_ok = _state(hp=40, shop=[_card('藿藿')])       # 非应急同板
    v = {}
    for key, st in (('crisis', st_crisis), ('ok', st_ok)):
        cands = [c for c in generate_candidates(st, sess, _REG)
                 if c.action.__class__.__name__ == 'BuyCard'
                 and c.action.card.name == '藿藿']
        assert cands, '桥 core 件(无方向)应生成买候选'
        v[key], _ = score_candidate(cands[0], st, sess, _REG)
    assert v['crisis'] - v['ok'] == _REG.crisis_buy_bias, v
    assert v['crisis'] > 0, '危机囤金态战力买应可执行(>0)'


def test_crisis_hoard_gold_gate() -> None:
    """囤金金线:金≥_CRISIS_HOARD_GOLD 才进危机囤金态;金 39 同应急
    hp 不触发(偏置/搜牌解锁都不生效)。"""
    assert crisis_hoard_active(
        _state(gold=_REG.crisis_hoard_gold), _REG)
    assert not crisis_hoard_active(
        _state(gold=_REG.crisis_hoard_gold - 1), _REG)
    assert not crisis_hoard_active(_state(hp=40), _REG)  # 非应急


def test_crisis_buy_bias_does_not_cross_interest_cliff() -> None:
    """息崖保持:金 52 买 3 费(52→49 跌破满息平台,息 EV −25)
    即使危机偏置在也恒负分——[18]「不为苟住破息」。"""
    sess = _sess()
    st = _state(gold=52, shop=[_card('藿藿', cost=3)])
    cands = [c for c in generate_candidates(st, sess, _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert cands
    val, _ = score_candidate(cands[0], st, sess, _REG)
    assert val < 0, f'息崖下危机买应负分(实际 {val})'


# --- ② 危机搜牌 --------------------------------------------------------------


def test_crisis_refresh_unlocked_in_hoard_state() -> None:
    """危机囤金态:refresh 层2 放行 + 评分 ≥ refresh_ev−费(r8 常规
    轮界门外);金<40 应急态 refresh 仍滤出。"""
    sess = _sess()
    st = _state()          # hp20 金72 r8:危机囤金态
    cands = generate_candidates(st, sess, _REG)
    kept, flog = filter_candidates(cands, st, sess, _REG)
    assert any(c.tag == 'refresh' for c in kept), '危机囤金态应放行搜牌'
    rc = next(c for c in cands if c.tag == 'refresh')
    val, _ = score_candidate(rc, st, sess, _REG)
    assert val >= _REG.refresh_ev - (rc.action.cost or 0), val
    # 非囤金应急态(金 30):refresh 滤出
    st2 = _state(gold=30)
    kept2, _f = filter_candidates(generate_candidates(st2, sess, _REG),
                                  st2, sess, _REG)
    assert not any(c.tag == 'refresh' for c in kept2)


# --- ③ 应急集内容 ------------------------------------------------------------


def test_emergency_set_content() -> None:
    """应急集=战力买+卖弱件+升级(+危机囤金态的 refresh);
    经济类候选(pair/copy/bond_fallback/synthesize)滤出。"""
    sess = _sess()
    st = _state(gold=30, bench=[_bench('散件甲', faction='公司')],
                shop=[_card('藿藿'),
                      _card('凑档件', faction='公司', cost=1)])
    cands = generate_candidates(st, sess, _REG)
    kept, flog = filter_candidates(cands, st, sess, _REG)
    kept_tags = {c.tag for c in kept}
    assert {'bridge_core', 'for_gold', 'levelup'} <= kept_tags, kept_tags
    rejected = {e['tag'] for e in flog if not e['kept']}
    # 凑档件被 pair 通道接管(ADR-0300 标签序)——两标签都在应急滤出域
    assert {'refresh', 'pair'} <= rejected, rejected
    assert flog[0]['level'] == 'emergency'


# --- ④ 端到端:检查项 5→0 -----------------------------------------------------


def test_crisis_gold_hoard_check_zero_violations() -> None:
    """批㉝ F3 五危机局(s1/s25/s75/s79;s52 非危机对照)修复后
    decision_v2_crisis_gold_hoard 违规=0(修复前 5/100)。"""
    strat = DecisionV2Strategy()
    ledgers = [simulate_p1(sd, pool='fallback', strategy=strat).ledger
               for sd in (1, 25, 52, 75, 79)]
    chk = check_decision_v2_crisis_gold_hoard(ledgers)
    assert chk['violations'] == 0, chk['detail']
