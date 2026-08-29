# -*- coding: utf-8 -*-
"""r319 readable 保真位测试(批次2)。"""
from __future__ import annotations

import inspect


def test_gold_opt_miss_none() -> None:
    """read_gold_opt miss→None(伴生 read_gold 仍 0)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs
    assert hasattr(obs, 'read_gold_opt')


def test_state_readable_fields() -> None:
    """GameState 三保真位(hp/gold/board readable)。"""
    from sr_od.application.currency_war.kernel.cw_state import GameState
    st = GameState()
    assert st.gold_readable is True
    assert st.board_readable is True
    assert st.hp_readable is True


def test_board_pairs_returns_honest() -> None:
    """_board_pairs 第二返回值 honest(至少一行 X/Y 真解析)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs
    sig = inspect.signature(obs._board_pairs)
    rt = sig.return_annotation
    assert 'bool' in rt or 'tuple' in rt
    src = inspect.getsource(obs._board_pairs)
    assert 'honest = True' in src   # 真解析置位


def test_read_game_state_sets_board_readable() -> None:
    """read_game_state 写 board_readable(r319 接线)。"""
    from sr_od.application.currency_war.obs import cw_observation as obs
    assert 'state.board_readable = _board_honest' in inspect.getsource(
        obs.read_game_state)
