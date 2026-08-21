"""r240 回归:bench 满+金够 → 卖腾容量后必须买(r6 死锁锁)。"""
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def test_bench_full_still_buys_core():
    """r6 场景:bench 9/9 满,金 44,店有姬子(3费)——
    卖散牌腾容量后必须买入(「希儿/姬子不买」死锁回归锁)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, 44, 70
    st.bench = [BenchChar(slot=i, char_id=n, faction=f)
                for i, (n, f) in enumerate([
                    ('三月七', '列车同行'), ('黑塔', '银河学者'),
                    ('飞霄', '狼狩'), ('丹恒·腾荒', '夜之半神'),
                    ('黑塔', '银河学者'), ('赛飞儿', '夜之半神'),
                    ('藿藿', '仙舟'), ('黑塔', '银河学者'),
                    ('刻律德菈', '战技点')])]
    st.deployed = [BenchChar(slot=1, char_id='姬子·启行',
                             faction='列车同行')]
    st.board = {'列车同行': 1}
    st.shop = [ShopCard(x=0, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=1, faction='贝洛伯格', name='希儿', cost=3)]
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert any(a.card.name == '爻光' for a in buys)   # 桥 fixed 买入


def test_sell_count_capped():
    """卖出上限:off-target ≤1 + 凑息 ≤1(v2 侧合计 ≤2;
    r6 腾席链叠加卖了 5 张连爻光都卖——上限锁)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, 44, 70
    st.bench = [BenchChar(slot=i, char_id=n, faction=f)
                for i, (n, f) in enumerate([
                    ('飞霄', '狼狩'), ('黑塔', '银河学者'),
                    ('赛飞儿', '夜之半神'), ('黑塔', '银河学者'),
                    ('飞霄', '狼狩')])]
    st.deployed = [BenchChar(slot=1, char_id='姬子·启行',
                             faction='列车同行')]
    st.board = {'列车同行': 1}
    st.shop = [ShopCard(x=0, faction='仙舟', name='爻光', cost=1)]
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert len(sells) <= 2


def test_protected_never_sold():
    """保护名单(桥 fixed)永不被 v2 卖出(r6 卖爻光回归锁)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, 44, 70
    st.bench = [BenchChar(slot=0, char_id='爻光', faction='仙舟'),
                BenchChar(slot=1, char_id='飞霄', faction='狼狩')]
    st.deployed = [BenchChar(slot=1, char_id='姬子·启行',
                             faction='列车同行')]
    st.board = {'列车同行': 1}
    st.shop = []
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = 'jizi_train'
    sess.bridge_id = None
    acts = s.decide_prep(st, sess, None)
    sells = [a for a in acts if isinstance(a, SellBench)]
    # 爻光是仙舟桥 fixed——不在卖出里(飞霄可以)
    names_sold = []
    for sl in sells:
        idx = sl.bench_idx
        if idx is not None and idx < len(st.bench):
            names_sold.append(st.bench[idx].char_id)
    assert '爻光' not in names_sold
