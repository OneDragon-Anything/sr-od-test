# -*- coding: utf-8 -*-
"""r354(局43 判读):破息窗 LevelUp 总成本门。

局43 实锤:r8 备战金 28,LevelUp 提案按单击价(4)过门 → 执行侧
循环点经验 12 击金尽停 → 等级没升(差太多)+ 金全灭 → boss 裸奔
-36。半吊子点经验是最差结局(钱花了等级没变战力没买)。
锁:①升不完级(总成本>预算)不提案 LevelUp,金留给买牌;
②升得完(总成本≤预算)正常提案。"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _state(gold: int, level: int = 6, xp_progress=None):
    return GameState(plane=1, round_num=9, gold=gold, level=level, hp=75,
                     board={'仙舟': 3, '狼狩': 2}, bench=[],
                     shop=[], xp_progress=xp_progress)


def _sess():
    s = StrategySession()
    s.locked_line = 'jizi_train'
    s.node_type_current = 'boss'
    return s


def test_levelup_total_cost_gate_blocks_insufficient() -> None:
    """局43 场景复刻:金 28,lv6 需 12+ 击(48 金)才升级——
    不提案 LevelUp(半吊子点经验=最差结局),金留给买牌。"""
    strat = LineStrategy()
    st = _state(gold=28, level=6, xp_progress=(0, 48))  # 需 12 击
    acts = strat._boss_breaker_actions(st, _sess())
    lvs = [a for a in acts if type(a).__name__ == 'LevelUp']
    assert not lvs, f'升不完级不得提案 LevelUp: {[type(a).__name__ for a in acts]}'


def test_levelup_total_cost_gate_allows_sufficient() -> None:
    """金够升完(差 1 击=4 金)→ 正常提案。

    r406(ADR-0266)语义修正:金 30 从未满息时新息引擎门会拒
    (30-4=26<50)——「升得完就升」的前提补上息引擎已立。锁改用
    金 55(花完 51≥50,双门皆过):总成本门语义(r354)不变,
    息引擎维度的锁见 test_cw_r406_levelup_engine_gate.py。"""
    strat = LineStrategy()
    st = _state(gold=55, level=6, xp_progress=(44, 48))  # 差 1 击
    acts = strat._boss_breaker_actions(st, _sess())
    lvs = [a for a in acts if type(a).__name__ == 'LevelUp']
    assert lvs, '升得完级必须提案(人口是板深杠杆)'
