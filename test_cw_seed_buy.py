"""r234 首局场景回归:散板期引擎种子件必须被买(桥种子修复)。"""
from sr_od.application.currency_war.cw_state import (
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int = 5):
    s = LineStrategy()
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 3, gold, 100
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def test_buys_engine_seed_low_gold():
    """首局 r1 场景:金 3,店有藿藿(仙舟桥 fixed)+万敌 →
    都买(r234 六轮零买 + r236 钱没花完的双重回归锁:
    低位金零息,花到买不起为止)。"""
    s, st, sess = _mk(gold=3)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='夜之半神', name='万敌', cost=1)]
    acts = s.decide_prep(st, sess, None)
    names = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '藿藿' in names
    # 万敌:非种子非凑对(board/bench 空)→ 仍不买(乱买守卫)


def test_spends_mid_gold_to_interest_tier():
    """金 23:floor=3(保 20 息档)→ 三张 1 费种子全买
    (23-3=20 预算;档内零息随便花的锁定)。"""
    s, st, sess = _mk(gold=23)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=2, faction='仙舟', name='丹恒·饮月', cost=1)]
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)]
    assert len(buys) == 3


def test_buys_train_and_dot_seeds():
    """三月七(列车 fixed)/艾丝妲(DOT core)同店 → 都买。"""
    s, st, sess = _mk(gold=20)
    st.shop = [ShopCard(x=0, faction='列车同行', name='三月七', cost=1),
               ShopCard(x=1, faction='持续伤害', name='艾丝妲', cost=1)]
    acts = s.decide_prep(st, sess, None)
    names = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert '三月七' in names and '艾丝妲' in names


def test_no_seed_spending_above_floor():
    """满息期地板仍守:金 50,floor=50 → 种子件也不买。"""
    s, st, sess = _mk(gold=50)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1)]
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, BuyCard)]


def test_non_seed_non_pair_not_bought():
    """非种子非凑对的高费卡不买(乱买守卫)。
    (原用例希儿 r353[8add6d5e]入 dot_belog fixed=桥种子件,
    r400 四体系定稿又确认希儿系为过渡方向件——现行为=意图;
    换真线外件黑塔锁守卫语义。)"""
    s, st, sess = _mk(gold=30)
    st.shop = [ShopCard(x=0, faction='银河学者', name='黑塔', cost=3)]
    st.board = {}    # 无同阵营
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, BuyCard)]
