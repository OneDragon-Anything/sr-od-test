# -*- coding: utf-8 -*-
"""observe_full 组装层主题锁(真 fixture 帧 + gold 重读门族)。

合并出处(2026-09-09 CUT2 合并批④,自 test_cw_gold_reread 整体并入,
断言面原样迁入;D49 在册归并候选消费):r331 真帧两面 + gold_reread
门族四面,全仓无重复锁(grep observe_full 仅本文件):
- heavy 真帧组装烟测(slow 桶在册)、light 跳 SIFT 真帧锁(全仓唯一
  light 路径锁);
- gold_reread 门族:F2 门腿(gold==0 重读只在 shop 开态做——关态读空
  恒 0,白付 3×0.3s+3 次全量 OCR)/ MED-2 行为腿(开态 gold 0 → 重读
  真值换入 state;连读 0 → 维持 0 不换)/ 离线契约腿(op=None 不重读,
  单次 read_game_state)。
历史注:原 4 条 inspect 形状锁已换真行为锁(README 纪律 8);旧头注
「被其他测试文件引用(防断链保留)」经 grep 全测试目录证实零引用,系
死指针,出处改本文件自持。"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.cw_observe_full import observe_full


def test_observe_full_heavy_on_prep_fixture(test_context) -> None:
    """r331:真备战 fixture 帧 → heavy 字段齐(state/board/substate)。"""
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺:货币战争-备战/补给节点.webp')
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    out = observe_full(test_context, frame, tier='heavy',
                       source='test', op=None, shop_open=False)
    assert out['tier'] == 'heavy'
    assert out['state'] is not None
    assert isinstance(out['substate'].get('node_seq'), bool)


def test_observe_full_light_skips_sift(test_context) -> None:
    """r331:轻档跳 SIFT(tier=light 只产 state+空 substate)。"""
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺')
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    out = observe_full(test_context, frame, tier='light', source='test')
    assert 'bench_chars' not in out or out.get('bench_chars') is None
    assert out['substate'] == {}


def test_gold_reread_gated_by_shop_open() -> None:
    """r334(review 第5条):gold==0 重读只在 shop 开态做——
    F2 语义(关态读空恒 0,白付 3×0.3s+3 次全量 OCR)。"""
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
    from sr_od.application.currency_war.kernel.cw_state import GameState

    _calls = {'gs': 0}

    def _fake_gs(ctx, frame):
        _calls['gs'] += 1
        return GameState(gold=0)
    _orig = (of_mod.read_game_state, of_mod.ensure_portrait_templates,
             of_mod.read_node_sequence, of_mod.read_shop_cards)
    of_mod.read_game_state = _fake_gs
    of_mod.ensure_portrait_templates = lambda ctx: None
    of_mod.read_node_sequence = lambda ctx, s: None
    of_mod.read_shop_cards = lambda ctx, s: []
    try:
        # 关态(shop_open=False):不重读
        out = observe_full(None, None, tier='heavy', source='test',
                           op=object(), shop_open=False)
        assert _calls['gs'] == 1, '关态 gold=0 不应触发重读(F2 门)'
        assert out['gold_reread'] is False
        # 开态(shop_open=True):重读(op.screenshot 会炸→break,
        # 但 read_game_state 已被调>1 证明进了循环)
        _calls['gs'] = 0

        class _BoomShot:
            def screenshot(self):
                raise RuntimeError('offline')
        out2 = observe_full(None, None, tier='heavy', source='test',
                            op=_BoomShot(), shop_open=True)
        assert _calls['gs'] >= 1
        assert out2['gold_reread'] is False   # 炸=break 未换值
    finally:
        (of_mod.read_game_state, of_mod.ensure_portrait_templates,
         of_mod.read_node_sequence, of_mod.read_shop_cards) = _orig


# ===== gold_reread 门族(合并批④自 test_cw_gold_reread 迁入,断言原样)=====

def _stub(of_mod, gold_seq: list[int]):
    """打桩 read_game_state 依序返 gold 序列;其余 reader 空。"""
    from sr_od.application.currency_war.kernel.cw_state import GameState
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
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
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
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
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
    import sr_od.application.currency_war.obs.cw_observe_full as of_mod
    _orig = _stub(of_mod, [0])
    try:
        out = observe_full(None, None, tier='heavy', source='test',
                           op=None, shop_open=True)
        assert out['state'].gold == 0
        assert out['gold_reread'] is False
    finally:
        _restore(of_mod, _orig)
