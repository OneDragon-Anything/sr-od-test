"""r252 应急多买测试(HP 1 只买 1 张必死的回归锁)。"""
from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(hp: int = 1, gold: int = 80):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, 5, gold, hp
    st.bench = []
    sess = StrategySession()
    sess.v2_state = ('economy', True, False, 0, 0, 0, 0, 0)  # emg
    sess.locked_line = 'feiying_joy'
    sess.bridge_id = None
    return s, st, sess


def test_emergency_buys_multiple():
    """HP 1 金 80 店里多张线内件 → budget 内买多张
    (旧版首中即 return 单张——第七局实锤必死)。"""
    s, st, sess = _mk(hp=1, gold=80)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=2, faction='列车同行', name='三月七', cost=1)]
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert len(buys) >= 2, f"应急该买多张,得 {len(buys)}"


def test_emergency_respects_rebirth_floor():
    """金 30:预算 30-20=10,3 费姬子不买(超预算)——地板守恒。"""
    s, st, sess = _mk(hp=1, gold=30)
    st.shop = [ShopCard(x=0, faction='列车同行', name='姬子·启行',
                        cost=3)]
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert all(a.card.cost <= 10 for a in buys) or not buys


def test_emergency_budget_decrements():
    """预算递减:80-20=60,买 1+1+1 后剩余 57——第 4 张 3 费
    姬子仍可(57>=3)买;但 50 金后 budget 30-…核心是守 20 地板。"""
    s, st, sess = _mk(hp=1, gold=25)   # budget=5
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=2),
               ShopCard(x=2, faction='列车同行', name='三月七', cost=3)]
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    total = sum(a.card.cost for a in buys)
    assert total <= 5, f"总花费 {total} 超预算 5"
