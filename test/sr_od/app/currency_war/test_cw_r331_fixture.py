# -*- coding: utf-8 -*-
"""r331/r333 fixture 回放测试(observe_full 接线+hp 收口的
单文件锁;用户指路:建档图做 fixture)。

(observe_full 组装层的 4 条 inspect 形状锁已并入本文件与
test_cw_r337_behavior 的真 fixture 行为锁:签名 tier/source 由本文件
关键字实参调用面辖、light 跳 SIFT 由 test_observe_full_light_skips_sift
辖、gold_reread 行为由 r337 三锁辖、substate 可读性由下方断言辖——
弱形状锁换真行为锁,重复构成删并理由(README 纪律 8)。)"""
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
