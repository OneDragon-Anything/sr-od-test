# -*- coding: utf-8 -*-
"""r383b 开局轮同名副本放行测(口述[1][15];局58/61 对照)。

锁:开局轮(r≤2)已拥有同名卡时,该卡的 1 费副本可买(3合1 素材+
压缩牌库);线外**非同名**仍拒(局49 病不回归)。副本上限仍归
_buy_guards(copies<3),本门只判「有同名」。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _st(round_num: int = 1) -> GameState:
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    return st


def _sess():
    class _S:
        locked_line = None
        bridge_id = None
        v2_state = None
    return _S()


def _card(name: str, faction: str) -> ShopCard:
    return ShopCard(x=0, name=name, faction=faction, cost=1)


def test_opening_same_name_copy_allowed() -> None:
    """开局轮已有 飞霄(bench)→ 店里飞霄放行(副本素材)。"""
    st = _st(1)
    st.bench = [BenchChar(char_id='飞霄', faction='狼狩', slot=1)]
    strat = LineStrategy()
    assert strat._pair_wants(_card('飞霄', '狼狩'), st, _sess()) is True


def test_opening_offline_nonsame_still_blocked() -> None:
    """开局轮线外非同名(阿格莱雅,owned 无昼之半神)仍拒(局49/53 病)。"""
    st = _st(1)
    st.bench = [BenchChar(char_id='飞霄', faction='狼狩', slot=1)]
    strat = LineStrategy()
    assert strat._pair_wants(_card('阿格莱雅', '昼之半神'), st, _sess()) is False


def test_deployed_same_name_also_counts() -> None:
    """deployed 同名也算副本真(上场后店里同名仍可买,合成素材)。"""
    st = _st(2)
    st.deployed = [BenchChar(char_id='椒丘', faction='减益', slot=1)]
    strat = LineStrategy()
    assert strat._pair_wants(_card('椒丘', '减益'), st, _sess()) is True


def test_beyond_opening_unaffected() -> None:
    """r>2 不走本门(原 owned 阵营门语义不变,回归锚)。

    r5 无方向(locked/bridge None)→ 走 owned 阵营门:卡芙卡
    (星核猎手)不在 owned={狼狩} → False(与 r383b 无关的原语义)。
    """
    st = _st(5)
    st.bench = [BenchChar(char_id='飞霄', faction='狼狩', slot=1)]
    strat = LineStrategy()
    assert strat._pair_wants(_card('卡芙卡', '星核猎手'), st, _sess()) is False
