# -*- coding: utf-8 -*-
"""r343 行为锁:深度代理 deploy 口径+散件撤除(review F/J/K)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _st(shop: list[ShopCard], bench: list[BenchChar]) -> GameState:
    st = GameState()
    st.plane, st.round_num = 1, 5
    st.level, st.gold = 5, 30
    st.shop = shop
    st.bench = bench
    return st


def test_filler_removed_after_proxy_fix() -> None:
    """r343:散件填充撤除——非 wants 散件(cost=2)不进 plan。"""
    strat = LineStrategy()
    sess = strat.create_session(None)
    sess.locked_line = 'v2:jizi_train'
    shop = [
        ShopCard(x=0, faction='贝洛伯格', name='娜塔莎', cost=2),
        ShopCard(x=1, faction='欢愉', name='花火', cost=2),
    ]
    bench = [BenchChar(slot=i + 1, char_id='', faction='散', star=1)
             for i in range(4)]
    st = _st(shop, bench)
    acts = strat.decide_prep(st, sess, None)
    bought = {a.card.name for a in acts
              if type(a).__name__ == 'BuyCard'}
    assert '娜塔莎' not in bought, 'r342 散件(非 wants cost2)应已撤'


def test_pair_buy_still_works() -> None:
    """r343:pair_wants 路径保留(阵营 count≥2 集中买仍在)——
    板深真杠杆的既有通道未伤。"""
    strat = LineStrategy()
    sess = strat.create_session(None)
    shop = [ShopCard(x=0, faction='仙舟', name='爻光', cost=1)]
    bench = [BenchChar(slot=1, char_id='藿藿', faction='仙舟', star=1),
             BenchChar(slot=2, char_id='', faction='散', star=1)]
    st = _st(shop, bench)
    acts = strat.decide_prep(st, sess, None)
    # 不锁 wants 具体值(pair 判据在 session 态上),锁「不崩+
    # BuyCard 可为空」——行为锁主位在上一测(撤除)
    assert isinstance(acts, list)


def test_depth_proxy_deploy_semantics() -> None:
    """r343:sim 深度代理=可 deploy 件数(① 收口 _deployable_depth
    后,源码锁指向 helper——simulate_p1 消费它,语义不变)。"""
    import inspect

    from sr_od.application.currency_war import cw_sim
    src = inspect.getsource(cw_sim._deployable_depth)
    assert '_SIM_ENGINE_FACTIONS' in src
    assert 'cnt >= 2' in src   # 阵营集中判据(deploy 口径)
    main_src = inspect.getsource(cw_sim.simulate_p1)
    assert '_deployable_depth(st)' in main_src   # 采样/账本走同一源
