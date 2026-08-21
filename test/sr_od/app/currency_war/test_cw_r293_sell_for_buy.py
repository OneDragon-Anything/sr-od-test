# -*- coding: utf-8 -*-
"""r293 破息窗卖腾位测试(局27:bench 8 满 → 买 0)。"""
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


def test_full_bench_still_buys() -> None:
    """r6 bench 8(满)店有仙舟件 → 卖散腾位后买入(局27 实锤
    反演:旧版容量守卫拒第 1 张,只 LvUp 买 0)。
    r354 语义更新:LevelUp 走总成本门(金 31 升级 20 ≤budget 21
    → 先升满),剩余预算(卖腾位回补后)买线内件——断言改
    「买了牌」(三月七 1 费进预算;丹恒 2 费被预算拒是真实约束)。"""
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num, st.level, st.gold, st.hp = 1, 6, 5, 31, 60
    st.board = {'仙舟': 1, '列车同行': 2, '护盾': 2}
    st.bench = [BenchChar(slot=i + 1, char_id=n, faction=f)
                for i, (n, f) in enumerate([
                    ('阮·梅', '银河学者'), ('翡翠', '公司'),
                    ('艾丝妲', '银河学者'), ('停云', '仙舟'),
                    ('乱破', '巡海游侠'), ('黑塔', '银河学者'),
                    ('希儿', '贝洛伯格'), ('椒丘', '狼狩')])]
    st.shop = [ShopCard(x=0, faction='仙舟', name='丹恒·饮月', cost=2),
               ShopCard(x=1, faction='列车同行', name='三月七', cost=1)]
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    sess.locked_line = 'jizi_train'
    sess.last_state = st
    acts = s.decide_prep(st, sess, None)
    buys = [a.card.name for a in acts if isinstance(a, BuyCard)]
    assert buys, f'满 bench 该腾位买入(线内件预算内),得 {buys}'
