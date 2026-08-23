# -*- coding: utf-8 -*-
"""r352(局38/40 双局实锤):boss 段板面集中买。

金滞留证据:局38 r9 g=44 买 0 / 局40 r9 g=77 买 0(店有
★彦卿/★卡芙卡/真理医生等,被 r350 锁线门正确拒绝——但 boss
决战质量期线形态不是唯一价值);深 12 进 boss 双局同 -34。
r356 注:集中买加配方围栏(recipe_tier<RECIPE_BASE 时只买
RECIPE_FACTIONS∩板面)——锁场景的板面均为配方满 5 档
(列车3+护盾2),围栏不生效验证原语义。"""
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
        SimpleNamespace(name='砂金', faction='护盾', cost=2),
        SimpleNamespace(name='海瑟音', faction='昼之半神', cost=4),
    ]


def _state(gold=77, board=None, bench=None):
    return GameState(plane=1, round_num=9, gold=gold, level=6, hp=68,
                     board=board or {'列车同行': 3, '护盾': 2},
                     bench=bench or [], shop=_shop())


def _sess():
    s = StrategySession()
    s.locked_line = 'jizi_train'
    s.node_type_current = 'boss'
    return s


def test_boss_depth_buy_board_faction() -> None:
    """r352 主锁(配方满面):板面配方阵营(护盾2)的线外件被追加
    购买——旧代码买 0 金 77 全滞留。"""
    strat = LineStrategy()
    acts = strat._boss_breaker_actions(_state(), _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '砂金' in buys, f'板面配方阵营件必须买(板深杠杆): {buys}'


def test_boss_depth_buy_rejects_nonboard_faction() -> None:
    """线外且非板面阵营仍拒——r352 只放板面集中,不重开散买
    (局38 艾丝妲教训,r350 语义保持)。
    ADR-0260 注:原用例海瑟音(昼之半神/持续伤害 flow)已被
    engine_seed 通道合法放行(过渡体系 bonds 含 flow,与 deploy
    侧 ignition 同口径)——拒买锁改用真线外件阿格莱雅(昼之半神,
    无过渡羁绊)。"""
    strat = LineStrategy()
    st = _state()
    st.shop = [SimpleNamespace(name='彦卿', faction='仙舟', cost=4),
               SimpleNamespace(name='砂金', faction='护盾', cost=2),
               SimpleNamespace(name='阿格莱雅', faction='昼之半神',
                               cost=4)]
    acts = strat._boss_breaker_actions(st, _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '阿格莱雅' not in buys, f'非板面阵营线外件必须拒: {buys}'


def test_boss_depth_buy_budget_guard() -> None:
    """预算守卫:金不足(地板后预算 1 < 最便宜件 2 费)不硬买。"""
    strat = LineStrategy()
    acts = strat._boss_breaker_actions(_state(gold=11), _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert not buys, f'预算内无件可买(金 11-地板 10=1 < 2费): {buys}'


def test_boss_depth_buy_tier_gap_priority() -> None:
    """r352b(局41 判读):集中买按档位接近度排序——2 人阵营的件
    优先于 1 人阵营(2→3 档跃迁 > 新开档)。
    r354 注:xp_progress 满条排除 LevelUp 分食;
    r356 注:板面配方满 5 档(仙舟3+护盾2? 用仙舟2+护盾3)
    ——围栏内两阵营都有件,缺口序 仙舟2(缺1)>护盾3(满)。"""
    strat = LineStrategy()
    st = GameState(plane=1, round_num=9, gold=50, level=6, hp=68,
                   board={'仙舟': 2, '护盾': 2, '列车同行': 1}, bench=[],
                   shop=[SimpleNamespace(name='砂金', faction='护盾', cost=2),
                         SimpleNamespace(name='彦卿', faction='仙舟', cost=4)],
                   xp_progress=(48, 48))
    acts = strat._boss_breaker_actions(st, _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '彦卿' in buys and '砂金' in buys, \
        f'两阵营件都该进(线内砂金先+集中买彦卿):{buys}'


def test_boss_depth_buy_skips_unaffordable_not_break() -> None:
    """r352c(review H):首张买不起 continue 而非 break——排序键
    跨组无价格序,break 会跳过同组更便宜卡与后续组可买卡。
    场景(配方满):仙舟2 档 4 费买不起,护盾 2 档 2 费买得起。"""
    strat = LineStrategy()
    st = GameState(plane=1, round_num=9, gold=24, level=6, hp=68,
                   board={'仙舟': 2, '护盾': 2, '列车同行': 1}, bench=[],
                   shop=[SimpleNamespace(name='彦卿', faction='仙舟', cost=4),
                         SimpleNamespace(name='砂金', faction='护盾', cost=2)],
                   xp_progress=(48, 48))
    acts = strat._boss_breaker_actions(st, _sess())
    buys = [a.card.name for a in acts if type(a).__name__ == 'BuyCard']
    assert '砂金' in buys, \
        f'买不起贵卡不得跳过便宜可买卡(review-H): {buys}'


def _card(faction: str, name: str = '') -> object:
    from types import SimpleNamespace as _SN
    return _SN(name=name or '测试', faction=faction, cost=1)


def _sess_line(line: str = 'jizi_train'):
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
        _sess_line(line='no_such_line_id'))
    assert ok, 'line 查不到必须回退引擎门(DOT flow 放行),不得锁死'
