# -*- coding: utf-8 -*-
"""r258/r260 模拟发现 → 单帧固化(方法论:模拟找情况,单帧锁行为)。

模拟器批量跑时发现的情况,逐个构造同款 GameState 断言确定行为:
1. 散店+无方向+金够 → 刷新(方向刷新通道);
2. 深夜金边(金 6 刷后穿地板)→ 不刷。

(节点分层零战力/遭遇更难的模拟器不变量锁在 test_cw_sim.py 的
test_reward_node_no_damage / test_encounter_harder_than_battle——
2026-08 精简审计去重,本文件只留决策单帧锁。)
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
    本帧锁定触发条件本身。
    r353 语义更新:狼狩入引擎阵营(hunt3 桥)——原「散店」
    场景(含飞霄)现在有引擎件,正确行为=**买**(引擎件优于刷);
    判据改非引擎散店(公司+盛会,狼狩件移除后无种子不刷则误)。"""
    s, st, sess = _mk(round_num=2, gold=20)
    st.shop = [ShopCard(x=0, faction='公司', name='翡翠', cost=1),
               ShopCard(x=1, faction='盛会之星', name='大丽花', cost=1),
               ShopCard(x=2, faction='欢愉', name='花火', cost=2)]
    acts = s.decide_prep(st, sess, None)
    assert any(isinstance(a, RefreshShop) for a in acts), \
        f'真散店(无引擎无种子)该刷,得 {[type(a).__name__ for a in acts]}'

    # 引擎件在场(狼狩=r353 起)→ 买优先于刷
    s2, st2, sess2 = _mk(round_num=2, gold=20)
    st2.shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1),
                ShopCard(x=1, faction='公司', name='翡翠', cost=1),
                ShopCard(x=2, faction='盛会之星', name='大丽花', cost=1)]
    acts2 = s2.decide_prep(st2, sess2, None)
    assert not any(isinstance(a, RefreshShop) for a in acts2), \
        f'有引擎件(狼狩)该买不该刷,得 {[type(a).__name__ for a in acts2]}'


def test_low_gold_edge_no_refresh() -> None:
    """模拟发现④(边界):金 6 → 刷后 4 穿 5 地板 → 不刷。"""
    s, st, sess = _mk(round_num=2, gold=6)
    st.shop = [ShopCard(x=0, faction='狼狩', name='飞霄', cost=1)]
    acts = s.decide_prep(st, sess, None)
    assert not any(isinstance(a, RefreshShop) for a in acts), \
        '低位金不刷(保命优先)'
