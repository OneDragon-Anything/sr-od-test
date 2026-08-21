# -*- coding: utf-8 -*-
"""r264 买优先级单帧固化(模拟枚举审计 120+36 局面零违规)。

牌库压缩视角(用户定调):bench 乱无所谓(买=离池),
关键 = 买优先级。枚举发现的行为逐帧锁定:
① 配方件 > 散件;② 未锁线:种子 > 散件;③ 凑星+新件都买;
④ war 态低金不买(floor 30 语义:战力≠panic,all-in 归 emergency);
⑤ carry 可负担时必买。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(locked, bench, gold, rnd=3, mode='economy'):
    # rnd 默认 3(r285 起 r5+ 进破息窗,优先级帧留在 economy 域测)
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, rnd, 5, gold, 80
    st.bench = [BenchChar(slot=i + 1, char_id=n, faction='仙舟')
                for i, n in enumerate(bench)]
    sess = StrategySession()
    sess.v2_state = (mode, False, False, 0, 0, 0, 0, 0)
    sess.locked_line = locked
    sess.bridge_id = None
    return s, st, sess


def _buys(acts):
    return [a.card.name for a in acts if isinstance(a, BuyCard)]


def test_recipe_beats_scatter() -> None:
    """① 配方件与散件同店,金够 → 买配方不买散。"""
    s, st, sess = _mk('jizi_train', ['藿藿'], 25)
    st.shop = [ShopCard(x=0, faction='列车同行', name='三月七', cost=1),
               ShopCard(x=1, faction='盛会之星', name='大丽花', cost=1)]
    got = _buys(s.decide_prep(st, sess, None))
    assert '三月七' in got
    assert '大丽花' not in got, f'散件不该被买,得 {got}'


def test_seed_beats_scatter_unlocked() -> None:
    """② 未锁线:桥种子(藿藿)与散件同店 → 种子被买。"""
    s, st, sess = _mk(None, [], 25)
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='盛会之星', name='大丽花', cost=1)]
    got = _buys(s.decide_prep(st, sess, None))
    assert '藿藿' in got, f'种子该买,得 {got}'


def test_star3rd_and_new_component_both() -> None:
    """③ 凑星第 3 张与新配方件同店(都便宜)→ 都买。"""
    s, st, sess = _mk('jizi_train', ['藿藿', '藿藿'], 12)
    st.shop = [ShopCard(x=0, faction='仙舟', name='爻光', cost=1),
               ShopCard(x=1, faction='列车同行', name='三月七', cost=1)]
    got = _buys(s.decide_prep(st, sess, None))
    assert '爻光' in got and '三月七' in got, f'该都买,得 {got}'


def test_war_low_gold_buys_nothing() -> None:
    """④ war 态金 6:地板 5 语义下藿藿(1费)买后 5=地板 → 可买;
    椒丘同费也可。r274 语义变更(原 floor 30 冻结 → 低金降级 5):
    局19 实锤 war 低金整轮冻结买0 = 板面不长流血到死。
    金 6 买 1 张 1 费(6-1=5≥5)——验证降级地板生效且不穿 5。"""
    s, st, sess = _mk('jizi_train', [], 6, mode='war')
    st.shop = [ShopCard(x=0, faction='仙舟', name='藿藿', cost=1),
               ShopCard(x=1, faction='狼狩', name='椒丘', cost=1)]
    got = _buys(s.decide_prep(st, sess, None))
    # r274 降级语义:可买但不穿 5 地板(金6 买1 张1费 后 5)
    assert st.gold - 1 * len(got) >= 5, f'穿 5 地板:{got}'
    assert len(got) <= 1, f'金 6 买 {len(got)} 张超预算'


def test_carry_bought_when_affordable() -> None:
    """⑤ carry(姬子)在店且买得起 → 必买(线内最高优先)。"""
    s, st, sess = _mk('jizi_train', [], 45)
    st.shop = [ShopCard(x=0, faction='列车同行', name='姬子·启行', cost=3),
               ShopCard(x=1, faction='盛会之星', name='大丽花', cost=1)]
    got = _buys(s.decide_prep(st, sess, None))
    assert '姬子·启行' in got, f'carry 必买,得 {got}'
