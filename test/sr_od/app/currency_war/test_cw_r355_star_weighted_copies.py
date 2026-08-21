# -*- coding: utf-8 -*-
"""r355(局44 判读):_buy_guards copies 星级加权。

局44 实证:四买飞霄(r1-r4 各一张)——3合1 后 2★在场,copies
按名字数 1 → 第 4 张 1★ 仍放行 = 冗余浪费(2★ 已含 2 份原料)。
锁:①2★在场+bench 0 → 第 2 张 1★ 拒(2+1=3 达上限,第 3 张拒);
②1★×2 在 bench → 第 3 张放(凑 3合1 正确);
③3★ 在场 → 任何同名拒(3/3 满)。"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _card():
    return SimpleNamespace(name='飞霄', faction='狼狩', cost=1)


def _st(bench=None, deployed=None):
    return GameState(plane=1, round_num=3, gold=20, level=4,
                     board={'狼狩': 1},
                     bench=bench or [], deployed=deployed or [])


def test_star2_blocks_third_copy() -> None:
    """2★ 在场(=2 份)+ bench 1★×1:再买 → 2+1+1=4 份超 3 → 拒。
    (裸 2★+0 副本时买第 1 张 1★ 是合法攒件——留路径。)"""
    dep = [SimpleNamespace(char_id='飞霄', star=2, faction='狼狩')]
    bench = [BenchChar(slot=1, char_id='飞霄', faction='狼狩', star=1)]
    ok = LineStrategy._buy_guards(_card(), _st(bench=bench, deployed=dep), 0)
    assert not ok, '2★+1★副本=3 份满,再买第 4 份必须拒(r355)'


def test_two_star1_allows_third() -> None:
    """1★×2 在 bench:第 3 张放行(3合1 正确凑齐)。"""
    bench = [BenchChar(slot=1, char_id='飞霄', faction='狼狩', star=1),
             BenchChar(slot=2, char_id='飞霄', faction='狼狩', star=1)]
    ok = LineStrategy._buy_guards(_card(), _st(bench=bench), 0)
    assert ok, '1★×2+买第 3 张=3合1 凑齐,必须放行'


def test_star3_blocks_all() -> None:
    """3★ 在场(=3 份满):任何同名买入拒。"""
    dep = [SimpleNamespace(char_id='飞霄', star=3, faction='狼狩')]
    ok = LineStrategy._buy_guards(_card(), _st(deployed=dep), 0)
    assert not ok, '3★ 已满(3/3 份)必须拒'
