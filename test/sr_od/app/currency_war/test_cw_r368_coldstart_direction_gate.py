# -*- coding: utf-8 -*-
"""r368 冷启动首购方向门测试(局49:r1 线外全买根因)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import GameState
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


class _Sess:
    locked_line = None
    bridge_id = None


def _card(name: str, faction: str, cost: int = 1):
    from sr_od.application.currency_war.cw_state import ShopCard
    return ShopCard(x=1, name=name, faction=faction, cost=cost)


def _empty_state() -> GameState:
    st = GameState()
    st.plane, st.round_num = 1, 1
    st.board = {}
    st.bench = []
    st.shop = []
    return st


def test_coldstart_bridge_member_allowed() -> None:
    """板面空:桥名单件(椒丘=hunt3 core)放行。"""
    st = _empty_state()
    assert LineStrategy._pair_wants(_card('椒丘', '狼狩'), st, _Sess()) is True


def test_coldstart_engine_faction_allowed() -> None:
    """板面空:引擎阵营件(仙舟/列车/DOT)放行。"""
    st = _empty_state()
    assert LineStrategy._pair_wants(_card('藿藿', '仙舟'), st, _Sess()) is True


def test_coldstart_offline_blocked() -> None:
    """板面空:线外件(大丽花=盛会之星/翡翠=公司)拒——局49 根因。"""
    st = _empty_state()
    assert LineStrategy._pair_wants(_card('大丽花', '盛会之星'), st, _Sess()) is False
    assert LineStrategy._pair_wants(_card('翡翠', '公司'), st, _Sess()) is False


def test_opening_round_with_system_bench() -> None:
    """r371b(局53):开局轮 bench 有系统卡(风堇=昼之半神)时,
    同阵营线外件(阿格莱雅)仍拒——冷启动判据=开局轮而非 owned 空。"""
    st = _empty_state()
    from sr_od.application.currency_war.cw_state import BenchChar
    st.bench = [BenchChar(slot=1, char_id='风堇', faction='昼之半神')]
    assert LineStrategy._pair_wants(
        _card('阿格莱雅', '昼之半神'), st, _Sess()) is False
    # 桥件仍放行
    assert LineStrategy._pair_wants(_card('椒丘', '狼狩'), st, _Sess()) is True


def test_nonempty_board_keeps_old_semantics() -> None:
    """非开局轮(r3+)板面非空:恢复凑对语义(同阵营放行/异阵营拒)。

    r371b:冷启动门扩到开局轮(r≤2)后,凑对语义的回归点在 r3+。
    """
    st = _empty_state()
    st.round_num = 3
    st.board = {'狼狩': 1}
    # 同阵营(狼狩)放行——凑对
    assert LineStrategy._pair_wants(_card('貊泽', '狼狩'), st, _Sess()) is True
    # 异阵营拒(旧尾行语义:card.faction in owned_factions)
    assert LineStrategy._pair_wants(_card('希儿', '贝洛伯格'), st, _Sess()) is False
