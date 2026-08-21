# -*- coding: utf-8 -*-
"""r258/r260 模拟发现 → 单帧固化(方法论:模拟找情况,单帧锁行为)。

模拟器批量跑时发现的情况,逐个构造同款 GameState 断言确定行为:
1. 散店+无方向+金够 → 刷新(方向刷新通道);
2. 遭遇/奖励节点的结算分流(node_type 四分类);
3. 深夜金边(金 6 刷后穿地板)→ 不刷。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(round_num: int = 2, gold: int = 20) -> tuple:
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level = 1, round_num, 4
    st.gold, st.hp = gold, 80
    st.bench = []
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s, st, sess


def test_scatter_shop_no_direction_refreshes() -> None:
    """模拟发现①:散店(无桥种子/无引擎)+未锁线 → 该刷找种子。

    模拟分布:r1-r4 方向建立率 关 79% vs 开 86%(+7pp)——
    本帧锁定触发条件本身。"""
    s, st, sess = _mk(round_num=2, gold=20)
    st.shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1),
               ShopCard(x=1, faction='公司', name='翡翠', cost=1),
               ShopCard(x=2, faction='盛会之星', name='大丽花', cost=1)]
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, RefreshShop) for a in acts), \
        f'散店该刷,得 {[type(a).__name__ for a in acts]}'


def test_reward_supply_node_zero_damage() -> None:
    """模拟发现②:奖励/补给节点零战力要求 → 结算不掉血。

    节点分层(node_delta)是模拟校准层;本帧锁定其分流语义。"""
    import random

    from sr_od.application.currency_war.cw_sim import node_delta
    rng = random.Random(7)
    for node in ('reward', 'supply'):
        d = node_delta(node, round_num=7, dir_round=99, rng=rng)
        assert d > 0, f'{node} 零战力节点不应掉血,得 {d}'


def test_encounter_settlement_harder_than_battle() -> None:
    """模拟发现③:遭遇结算强度 > 同期普通战斗(均值)。

    用户口述:遭遇(尤其三四)战力要求高于普通甚至 boss。"""
    import random

    from sr_od.application.currency_war.cw_sim import node_delta
    enc = [node_delta('encounter', 6, 99, random.Random(i))
           for i in range(50)]
    bat = [node_delta('battle', 6, 99, random.Random(i))
           for i in range(50)]
    assert -sum(enc) / 50 > -sum(bat) / 50, '遭遇均值损应大于战斗'


def test_low_gold_edge_no_refresh() -> None:
    """模拟发现④(边界):金 6 → 刷后 4 穿 5 地板 → 不刷。"""
    s, st, sess = _mk(round_num=2, gold=6)
    st.shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1)]
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts), \
        '低位金不刷(保命优先)'
