"""ADR-0305 锁(件2 rung 统计口径)。

锁定对象:rung 统计口径(cw_sim._battles_before_engines)——首达 e2
前的战斗类结算计数(battle/encounter/boss,round < e2 轮),奖励
不计;未达 e2 → None——0304「30 vs 10」未定义口径误读的防再犯。

(件1 金充裕买偏置已被 A/B 定谳否决,三字段与 scoring 消费块已随
ADR-0305 增补清理节删除,其锁随批移除;清理后语义守卫另见
test_cw_dead_arm_cleanup_locks.py。)
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_sim import (
    _battles_before_engines,
    _first_engines_round,
)

# --- rung 统计口径 ---------------------------------------------------------


def _fake_res() -> SimpleNamespace:
    """最小 ledger/hp_events 载体:r1 仙舟1 → r2 仙舟3 → r4 双体系。"""
    return SimpleNamespace(
        ledger=[
            {'round_num': 1,
             'state': {'board_factions': {'仙舟': 1}, 'deployed': []}},
            {'round_num': 2,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 3,
             'state': {'board_factions': {'仙舟': 3}, 'deployed': []}},
            {'round_num': 4, 'state': {
                'board_factions': {'仙舟': 3, '列车同行': 2},
                'deployed': []}},
        ],
        hp_events=[
            (1, 'battle', -5, False),
            (2, 'reward', 2, False),
            (3, 'encounter', -4, False),
            (4, 'boss', -8, False),
        ],
    )


def test_battles_before_e2_metric_semantics() -> None:
    """e2 首达 r4(仙舟3+列车2):此前战斗类 = r1 battle + r3 encounter
    = 2(r2 reward 不计;r4 当轮不计,< 严格)。"""
    res = _fake_res()
    assert _first_engines_round(res, 2) == 4
    assert _battles_before_engines(res, 2) == 2


def test_battles_before_e2_none_when_never() -> None:
    """未达 e2 → None(与 _first_engines_round 同 None 语义;
    批报告均值只对达成局算)。"""
    res = _fake_res()
    assert _first_engines_round(res, 3) is None
    assert _battles_before_engines(res, 3) is None
