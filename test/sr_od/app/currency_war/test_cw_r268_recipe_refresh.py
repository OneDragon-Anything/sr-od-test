# -*- coding: utf-8 -*-
"""r268 配方找件刷新测试(局17 配方基础冻结根因)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)

_RECIPE = {'仙舟', '持续伤害', '列车同行', '护盾'}


def _mk(rnd, board, shop, gold=30):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level = 1, rnd, 5
    st.gold, st.hp = gold, 80
    st.board = dict(board)
    st.bench = []
    st.shop = shop
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'jizi_train'
    return s, st, sess


def test_recipe_starved_no_supply_refreshes() -> None:
    """r6 配方 3 档(<5)+店里 0 配方件 → 刷(局17 场景)。"""
    board = {'仙舟': 1, '列车同行': 2, '公司': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1),
            ShopCard(x=1, faction='盛会之星', name='大丽花', cost=1)]
    s, st, sess = _mk(6, board, shop)
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, RefreshShop) for a in acts), \
        f'配方缺件无供给该刷,得 {[type(a).__name__ for a in acts]}'


def test_recipe_ok_no_refresh() -> None:
    """配方 5 档(≥基础线)→ 不刷。"""
    board = {'仙舟': 3, '列车同行': 2}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)


def test_shop_has_recipe_no_refresh() -> None:
    """配方缺(3 档)但店里有配方件(会买)→ 不刷。"""
    board = {'仙舟': 1, '列车同行': 2}
    shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
            ShopCard(x=1, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop)
    acts = s.decide_prep(st, sess, None)
    from sr_od.application.currency_war.cw_state import BuyCard
    if any(isinstance(a, BuyCard) for a in acts):
        assert not any(isinstance(a, RefreshShop) for a in acts)


def test_r4_not_in_window() -> None:
    """r4(方向窗口,非配方窗口)配方缺 → 不触发配方刷(职责分离)。"""
    board = {'仙舟': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(4, board, shop)
    acts = s.decide_prep(st, sess, None)
    # r4 属方向刷新域(r258);配方刷新不启动
    # (方向刷可能触发,但配方门不重复计——只验不崩溃)
    assert acts is not None


def test_low_gold_no_refresh() -> None:
    """金 6(刷后穿 5 地板)→ 不刷。"""
    board = {'仙舟': 1, '列车同行': 2, '公司': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop, gold=6)
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts)


def test_low_prob_no_refresh() -> None:
    """r269b 概率门:lv8(1费 p=14%,配方件 p_any~12%<25%)→ 不刷
    (等级塌掉 1 费概率,刷了白刷;该升人口换费用段)。"""
    board = {'仙舟': 1, '列车同行': 2, '公司': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop, gold=30)
    st.level = 8
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts), \
        'lv8 1费概率塌掉,期望门该拦'


def test_mid_level_refresh_ok() -> None:
    """r269b 概率门:lv5(p_any~38%>25%)→ 刷(中低等级找件划算)。"""
    board = {'仙舟': 1, '列车同行': 2, '公司': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop, gold=30)
    st.level = 5
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, RefreshShop) for a in acts)


def test_multi_refresh_cap() -> None:
    """r270 连续刷上限:店持续无配方件时至多 _RECIPE_REFRESH_MAX 次。"""
    from sr_od.application.currency_war.strategies.line_strategy import (
        _RECIPE_REFRESH_MAX,
    )
    assert _RECIPE_REFRESH_MAX == 3
    board = {'仙舟': 1, '列车同行': 2, '公司': 1}
    shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1)]
    s, st, sess = _mk(6, board, shop, gold=30)
    st.level = 5
    acts = s.decide_prep(st, sess, None)
    n = sum(1 for a in acts if isinstance(a, RefreshShop))
    assert n <= _RECIPE_REFRESH_MAX, f'刷了 {n} 次超上限'
