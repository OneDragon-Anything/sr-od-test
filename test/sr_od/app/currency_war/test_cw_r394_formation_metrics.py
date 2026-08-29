# -*- coding: utf-8 -*-
"""r394 锁:过渡阵容成型指标(_first_tier_round/_first_trio_round/
_board_factions_of 纯函数语义)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim import (
    _board_factions_of,
    _first_tier_round,
    _first_trio_round,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar


class _R:
    def __init__(self, rows):
        self.ledger = rows


def _row(rn: int, deployed: list) -> dict:
    return {'round_num': rn,
            'state': {'deployed': [{'char_id': d} for d in deployed],
                      'board_factions': _board_factions_of(
                          [BenchChar(char_id=d, faction='', slot=1)
                           for d in deployed])}}


def test_board_factions_counts_flows() -> None:
    """阵营计数含 flows(生产 board 口径)。"""
    dep = [BenchChar(char_id='爻光', faction='', slot=1)]
    bf = _board_factions_of(dep)
    assert bf.get('仙舟', 0) >= 1   # 爻光=仙舟(注册表)


def test_first_tier_round_found() -> None:
    """配方档位总和(recipe_tier=配方阵营档位和)首达轮。"""
    # 三月七(列车同行):r3 两张=2 档;r5 三张=3 档(含 flows 计入
    # 的口径以函数输出为准——锁「轮次查询语义」不锁档位算法)。
    r = _R([_row(3, ['三月七', '三月七']),
            _row(5, ['三月七', '三月七', '三月七'])])
    got3 = _first_tier_round(r, 3)
    assert got3 is not None and got3 >= 3, '首达轮 ≥ 出现轮'
    got2 = _first_tier_round(r, 2)
    assert got2 == 3, '2 档 r3 即达'


def test_first_trio_round_semantics() -> None:
    r = _R([_row(4, ['爻光', '藿藿']),
            _row(6, ['爻光', '藿藿', '丹恒·饮月'])])
    assert _first_trio_round(r, 3) == 6   # 三人到齐在 r6
    assert _first_trio_round(r, 2) == 4   # 两人(功能链双枢)在 r4


def test_engines_count_lego_model() -> None:
    """r399 过渡四体系(仙舟3/列车2/DOT2/希儿系)计数。"""
    from sr_od.application.currency_war.kernel.cw_battle_calib import _engines_count
    assert _engines_count({'持续伤害': 2, '列车同行': 1}) == 1   # 仅 DOT2
    assert _engines_count({'持续伤害': 2, '列车同行': 2}) == 2   # DOT2+列车2
    assert _engines_count({'仙舟': 3, '欢愉': 5}) == 1           # 仙舟3(欢愉非过渡体系)
    assert _engines_count({'仙舟': 2}) == 0                       # 仙舟差 1 人未点火


def test_engines_count_seele_system() -> None:
    """r399 希儿系:希儿在场+量2/贝2=第四体系;无希儿不算。"""
    from sr_od.application.currency_war.kernel.cw_battle_calib import _engines_count
    assert _engines_count({'量子同频': 2}, frozenset({'希儿'})) == 1
    assert _engines_count({'贝洛伯格': 2}, frozenset({'希儿'})) == 1
    assert _engines_count({'量子同频': 2}, frozenset()) == 0, \
        '无希儿时量子/贝是放大器不独立成体系(28 帖全部含希儿)'
    assert _engines_count({'量子同频': 3, '贝洛伯格': 2},
                          frozenset({'希儿'})) == 1, '希儿系内量/贝同开算一个体系'
    assert _engines_count({'列车同行': 2, '量子同频': 2},
                          frozenset({'希儿'})) == 2, '列车2+希儿系(13 帖实证)'


def test_transition_formed_pair_of_three() -> None:
    """r399:过渡成型=四体系两两组合(通用羁绊不算)。"""
    from sr_od.application.currency_war.kernel.cw_battle_calib import _transition_formed
    assert _transition_formed({'持续伤害': 2, '列车同行': 2})    # DOT2+列车2
    assert _transition_formed({'仙舟': 3, '持续伤害': 2})        # 仙舟+DOT(主流 84 帖)
    assert _transition_formed({'仙舟': 3, '列车同行': 2})        # 仙舟+列车
    assert _transition_formed({'列车同行': 2, '量子同频': 2},
                              frozenset({'希儿'}))               # 列车+希儿系
    assert not _transition_formed({'贝洛伯格': 2, '减益': 2}), \
        '通用羁绊组合不算过渡成型(49 帖直通线无一是通用羁绊组合)'
    assert not _transition_formed({'量子同频': 2}), '单放大器无希儿不成体系'
    assert not _transition_formed({'列车同行': 2}), '单体系=过渡的过渡,不算成型'


def test_first_engines_round() -> None:
    from sr_od.application.currency_war.kernel.cw_battle_calib import _first_engines_round
    rows = [
        {'round_num': 3, 'state': {'board_factions': {'持续伤害': 2}}},
        {'round_num': 5, 'state': {'board_factions':
                                   {'持续伤害': 2, '列车同行': 2}}},
    ]

    class _R2:
        ledger = rows
    assert _first_engines_round(_R2(), 2) == 5   # 第二引擎 r5 点火
    assert _first_engines_round(_R2(), 1) == 3   # 首引擎 r3
