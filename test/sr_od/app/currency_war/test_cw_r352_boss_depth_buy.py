# -*- coding: utf-8 -*-
"""r352(局38/40 双局实锤):boss 段板面集中买。

金滞留证据:局38 r9 g=44 买 0 / 局40 r9 g=77 买 0(店有 ★彦卿
等板面阵营件被锁线门拒);深 12 进 boss 双局同 -34。
锁:①板面阵营件在 boss 决战被追加购买;②线外非板面阵营仍拒;
③预算/容量守卫生效。"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _shop():
    return [
        SimpleNamespace(name='彦卿', faction='仙舟', cost=4),
        SimpleNamespace(name='真理医生', faction='银河学者', cost=3),
        SimpleNamespace(name='海瑟音', faction='昼之半神', cost=4),
    ]


def _state(gold=77, board=None, bench=None):
    return GameState(plane=1, round_num=9, gold=gold, level=6, hp=68,
                     board=board or {'列车同行': 3, '银河学者': 2},
                     bench=bench or [], shop=_shop())


def _sess():
    s = StrategySession()
    s.locked_line = 'jizi_train'
    s.node_type_current = 'boss'
    return s


def test_boss_depth_buy_board_faction() -> None:
    """r352 主锁:板面已有阵营(银河学者×2)的线外件被追加购买
    (局40 r9 真理医生场景复刻——旧代码买 0 金 77 全滞留)。"""
    strat = LineStrategy()
    acts = strat._boss_breaker_actions(_state(), _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '真理医生' in buys, f'板面阵营件必须买(板深杠杆): {buys}'


def test_boss_depth_buy_rejects_nonboard_faction() -> None:
    """线外且非板面阵营(昼之半神)仍拒——r352 只放板面集中,
    不重开散买(局38 艾丝妲教训,r350 语义保持)。"""
    strat = LineStrategy()
    acts = strat._boss_breaker_actions(_state(), _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '海瑟音' not in buys, f'非板面阵营线外件必须拒: {buys}'


def test_boss_depth_buy_budget_guard() -> None:
    """预算守卫:金不足(地板后预算 0)不硬买。"""
    strat = LineStrategy()
    acts = strat._boss_breaker_actions(_state(gold=12), _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert not buys, f'预算内无件可买(金 12-地板 10): {buys}'


def test_boss_depth_buy_tier_gap_priority() -> None:
    """r352b(局41 判读):板面 8 阵营散面下,集中买按档位接近度
    排序——2 人阵营的件优先于 1 人阵营(2→3 档跃迁 > 新开档)。"""
    strat = LineStrategy()
    # 板面:仙舟2(缺口1) 银河学者1(缺口2);店里两个阵营都有件
    st = GameState(plane=1, round_num=9, gold=50, level=6, hp=68,
                   board={'仙舟': 2, '银河学者': 1}, bench=[],
                   shop=[SimpleNamespace(name='真理医生', faction='银河学者', cost=3),
                         SimpleNamespace(name='彦卿', faction='仙舟', cost=4)])
    acts = strat._boss_breaker_actions(st, _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert buys and buys[0] == '彦卿', \
        f'档位缺口小者(仙舟2→3)必须先买:{buys}'


def test_boss_depth_buy_skips_unaffordable_not_break() -> None:
    """r352c(review H):首张买不起 continue 而非 break——排序键
    跨组无价格序,break 会跳过同组更便宜卡与后续组可买卡
    (金滞留复发)。场景:仙舟2 档的 4 费卡买不起,但银河学者
    1 档的 3 费卡买得起 → 两张都该进。"""
    strat = LineStrategy()
    st = GameState(plane=1, round_num=9, gold=24, level=6, hp=68,
                   board={'仙舟': 2, '银河学者': 1}, bench=[],
                   shop=[SimpleNamespace(name='彦卿', faction='仙舟', cost=4),
                         SimpleNamespace(name='真理医生', faction='银河学者', cost=3)])
    acts = strat._boss_breaker_actions(st, _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '真理医生' in buys, \
        f'买不起贵卡不得跳过便宜可买卡(review-H): {buys}'


def _card(faction: str, name: str = '') -> object:
    from types import SimpleNamespace as _SN
    return _SN(name=name or '测试', faction=faction, cost=1)


def _sess(line: str = 'jizi_train'):
    s = StrategySession()
    s.locked_line = line
    s.node_type_current = 'boss'
    return s


def test_locked_line_unknown_falls_back_engine_gate() -> None:
    """r352c(review M2):locked_line 查不到 line(理论态)回退
    引擎门而非空集——空集=挂件通道全锁死。"""
    st = GameState(plane=1, round_num=7, gold=30, level=5,
                   board={'银河学者': 1}, bench=[])
    ok = LineStrategy._pair_wants(
        _card('银河学者', '艾丝妲'), st,
        _sess(line='no_such_line_id'))
    assert ok, 'line 查不到必须回退引擎门(DOT flow 放行),不得锁死'
