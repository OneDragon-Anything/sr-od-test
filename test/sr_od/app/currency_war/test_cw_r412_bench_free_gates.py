"""件2(ADR-0274,口述[32],局72 r9 实证)腾席链三改锁测试。

- boss 轮(位面末节点)一律禁升级腾席。
- 腾席优先级:先卖杂件(off-target)再考虑升级。
- 升级前置:真缺人口(cap 缺口 ≥1)+ 息引擎门(ADR-0266 同款)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.prep_actions import (
    DeferSpheres,
    LevelUp,
    SellBench,
)
from sr_od.application.currency_war.prep_director import PrepObservation
from sr_od.application.currency_war.strategies.default_strategy import DefaultCwStrategy

S = DefaultCwStrategy()
COMP = get_comp('列车同行')


def _cfg(**overrides) -> SimpleNamespace:
    base = {
        'faction_priority': ['贝洛伯格', '仙舟', '巡海游侠'],
        'character_priority': ['阿格莱雅'],
        'character_build_around': [],
        'strategy_id': 'default',
        'strategy_seed': None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _bc(slot: int, char_id: str, faction: str = '?', star: int = 1,
        pref: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=char_id, faction=faction, star=star,
                     position_pref=pref)


def _obs_worth_bench(**state_kw) -> PrepObservation:
    """板满(cap=lv)+ bench 应上场件(同阵营 count≥2)+ gold 可信 fresh state。"""
    bench = [_bc(1, '甲', '贝洛伯格'), _bc(2, '乙', '贝洛伯格')]
    deployed = [_bc(i, f'd{i}', '仙舟') for i in range(1, 6)]   # lv5 板满
    kw = {'gold': 70, 'round_num': 3}
    kw.update(state_kw)
    st = GameState(level=5, plane=1, deployed=deployed, **kw)
    o = PrepObservation()
    o.spheres = [('gold', None, 40)]
    o.free_bench_slots = 0
    o.deploy_vacancy = 0
    o.bench_chars = bench
    o.shop_open = True
    o.state_gold_trusted = True
    o.state = st
    return o


def _sess_worth(**kw) -> StrategySession:
    bench = [_bc(1, '甲', '贝洛伯格'), _bc(2, '乙', '贝洛伯格')]
    deployed = [_bc(i, f'd{i}', '仙舟') for i in range(1, 6)]
    kw.setdefault('tracked_bench_chars', bench)
    kw.setdefault('tracked_deployed', deployed)
    kw.setdefault('last_level_obs', 5)
    kw.setdefault('last_state', GameState(level=5, plane=1, round_num=3))
    return StrategySession(**kw)


def test_boss_round_rejects_levelup() -> None:
    """锁1:boss 轮(位面末节点)腾席链禁升级——同款 fixture 非轮可 LevelUp,
    boss 轮(node_type 权威源)拒绝,落卖件/留置。"""
    a = S.decide_prep_action(_obs_worth_bench(), _sess_worth(), _cfg())
    assert isinstance(a, LevelUp), '前置自检:非 boss 轮 + 引擎立(latch)应可升级'
    b = S.decide_prep_action(_obs_worth_bench(),
                             _sess_worth(node_type_current='boss'), _cfg())
    assert not isinstance(b, LevelUp), 'boss 轮一律禁升级腾席(口述[32])'
    # r9 先验兜底(supply 例外)同禁
    c = S.decide_prep_action(_obs_worth_bench(round_num=9),
                             _sess_worth(node_type_current='普通战斗'), _cfg())
    assert not isinstance(c, LevelUp), 'r9 位面末先验同禁'


def test_bench_full_junk_sold_before_levelup() -> None:
    """锁2:bench 满且杂件可卖 → 卖不升(a2 卖杂件优先于链 b;判据
    off-target=_card_supports_target False)。"""
    junk = _bc(3, '路人', '?')
    obs = _obs_worth_bench()
    obs.bench_chars = [junk]
    obs.state.bench = [junk]
    sess = _sess_worth(target_comp=COMP)
    sess.tracked_bench_chars = [junk]
    a = S.decide_prep_action(obs, sess, _cfg())
    assert isinstance(a, SellBench) and a.slot == 3, \
        'bench 满有 off-target 杂件 → 卖杂件(ADR-0274 卖件优先于升级)'


def test_no_pop_shortfall_no_levelup() -> None:
    """锁3:cap 缺口 0(板有空位/cap 装得下想上的件)→ 不升(连链 b 都不进,
    不为升级空等 gold 真值)。"""
    obs = _obs_worth_bench()
    obs.state.deployed = [_bc(1, 'd1', '仙舟')]     # cap5 板 1 人 → 空位 4
    sess = _sess_worth()
    sess.tracked_deployed = [_bc(1, 'd1', '仙舟')]
    a = S.decide_prep_action(obs, sess, _cfg())
    assert not isinstance(a, LevelUp), 'cap-deployed 缺口 0 → 不升级(口述[32] 真缺人口前置)'


def test_junk_sold_out_shortfall_engine_ok_allows_levelup() -> None:
    """锁4:杂件卖尽 + 真缺人口 + 息引擎立(latch)→ 允许升级。"""
    # bench 全 on-target(同阵营 count≥2,非杂件)→ a2 返 None
    a = S.decide_prep_action(_obs_worth_bench(), _sess_worth(), _cfg())
    assert isinstance(a, LevelUp), '杂件卖尽+真缺人口+引擎立(latch)→ 允许'


def test_engine_not_established_rejects_levelup() -> None:
    """锁5(ADR-0266 臂):lv≥5 息引擎未立(latch False 且花完 <50)→ 拒升。"""
    obs = _obs_worth_bench(gold=30)      # 30 - 总成本 < 50,引擎未立
    a = S.decide_prep_action(obs, _sess_worth(), _cfg())
    assert not isinstance(a, LevelUp), '息引擎未立的追级腾席升级被拒(ADR-0266/0274)'
    assert isinstance(a, (SellBench, DeferSpheres)), '拒升后落卖件/留置,不死等'
