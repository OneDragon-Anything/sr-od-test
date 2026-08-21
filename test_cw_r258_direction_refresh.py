"""r258 早期方向刷新测试(HP≥60 P1 根因修复)。"""
from sr_od.application.currency_war.cw_state import (
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(round_num=2, gold=20, shop=None, locked=None):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level = 1, round_num, 4
    st.gold, st.hp = gold, 80
    st.bench = []
    st.shop = shop or []
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = locked
    sess.bridge_id = None
    return s, st, sess


def test_scatter_shop_triggers_refresh():
    """P1r2 无锁线,店全是非引擎散件 → 刷(找种子)。"""
    shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1),
            ShopCard(x=1, faction='公司', name='翡翠', cost=1),
            ShopCard(x=2, faction='盛会之星', name='大丽花', cost=1)]
    s, st, sess = _mk(round_num=2, gold=20, shop=shop)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, RefreshShop) for a in acts), \
        f'散店该刷新,得 {[type(a).__name__ for a in acts]}'


def test_direction_shop_no_refresh():
    """店里有 2 张引擎件(仙舟藿藿+椒丘) → 不刷(方向已在)。"""
    shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
            ShopCard(x=1, faction='狼狩', name='椒丘', cost=1),
            ShopCard(x=2, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(round_num=2, gold=20, shop=shop)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)


def test_locked_line_no_refresh():
    """已锁线 → 不刷(方向已立)。"""
    shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1)]
    s, st, sess = _mk(round_num=2, gold=20, shop=shop,
                      locked='jizi_train')
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)


def test_low_gold_no_refresh():
    """金 6(刷后 4 <5 地板)→ 不刷(低位金保命)。"""
    shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1)]
    s, st, sess = _mk(round_num=2, gold=6, shop=shop)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)


def test_late_round_no_refresh():
    """r5(窗口外)→ 不刷。"""
    shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1)]
    s, st, sess = _mk(round_num=5, gold=20, shop=shop)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)
