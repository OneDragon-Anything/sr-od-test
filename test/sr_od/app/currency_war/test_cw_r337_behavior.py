# -*- coding: utf-8 -*-
"""observe_full 行为锁(r337;替代旧 getsource 弱锁——review
第16 条:st_gold_reread_semantics 空壳 return True 零效力)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_observe_full import observe_full


def _stub(of_mod, gold_seq: list[int]):
    """打桩 read_game_state 依序返 gold 序列;其余 reader 空。"""
    from sr_od.application.currency_war.cw_state import GameState
    _i = {'n': 0}

    def _gs(ctx, frame):
        g = gold_seq[min(_i['n'], len(gold_seq) - 1)]
        _i['n'] += 1
        return GameState(gold=g)
    _orig = (of_mod.read_game_state, of_mod.ensure_portrait_templates,
             of_mod.read_node_sequence, of_mod.read_shop_cards)
    of_mod.read_game_state = _gs
    of_mod.ensure_portrait_templates = lambda ctx: None
    of_mod.read_node_sequence = lambda ctx, s: None
    of_mod.read_shop_cards = lambda ctx, s: []
    return _orig


def _restore(of_mod, orig) -> None:
    (of_mod.read_game_state, of_mod.ensure_portrait_templates,
     of_mod.read_node_sequence, of_mod.read_shop_cards) = orig


class _Shot55:
    """op 桩:重截图返一个哑帧(gold 真值由 read_game_state 桩给)。"""
    shots = 0

    def screenshot(self):
        type(self).shots += 1
        return None


def test_gold_reread_swaps_state_when_second_read_positive() -> None:
    """MED-2 行为锁:开态 gold 0 → 重读 55 → state.gold==55。"""
    import sr_od.application.currency_war.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0, 55])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=_Shot55(), shop_open=True)
        assert out['state'].gold == 55, '重读真值应换入'
        assert out['gold_reread'] is True
    finally:
        _restore(of_mod, _orig)


def test_gold_reread_keeps_zero_when_all_reads_zero() -> None:
    """MED-2 行为锁:连读 0 → 维持 0(gold_reread=False)。"""
    import sr_od.application.currency_war.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0, 0, 0, 0])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=_Shot55(), shop_open=True)
        assert out['state'].gold == 0
        assert out['gold_reread'] is False
    finally:
        _restore(of_mod, _orig)


def test_offline_op_none_skips_reread() -> None:
    """离线契约:op=None 不重读(单次 read_game_state)。"""
    import sr_od.application.currency_war.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=None, shop_open=True)
        assert out['state'].gold == 0
        assert out['gold_reread'] is False
    finally:
        _restore(of_mod, _orig)
