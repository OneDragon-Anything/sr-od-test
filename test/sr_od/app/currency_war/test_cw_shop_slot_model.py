# -*- coding: utf-8 -*-
"""T-189 批1(3.5)锁面三件:定长不变量 / 三态判据买光 / 失读窗收店。

- 定长不变量:ShopPayload.cards 恒 5(转移函数置换与 synthesize 按槽映射
  后仍定长;买光=[empty×5] 而非 None——用户三态裁定 2026-09-13);
- 三态判据:买光 fixture → 全决策链降级 CloseShop(T-181 买空店崩溃循环
  的回归锁);失读形态:unknown 槽在场 → 花钱禁发射,终结集仅 CloseShop
  (shop-slot-model §5.1 失读窗收紧)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    ShopCard,
    ShopPayload,
    ShopSlot,
    apply_shop_action_logic,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BuyCard,
    CloseShop,
    RefreshShop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    decide_shop_action,
)

_SIG = ChannelSig(family='logic_action', actor='MandateV1Strategy',
                  mode='compute')


def _payload(*cards: ShopCard | None) -> ShopPayload:
    """构造定长 payload:位置参数按槽序;None=empty;不足 5 槽补 empty。"""
    slots = [ShopSlot(kind='content', card=c) if c is not None
             else ShopSlot(kind='empty') for c in cards]
    while len(slots) < 5:
        slots.append(ShopSlot(kind='empty'))
    return ShopPayload(cards=slots)


def _card(name: str, cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟', cost=cost, star=1,
                    cost_source='roster', slot=0)


def _bs_with(payload: ShopPayload):
    bs = board_state_of(None)
    bs.observe(bs.shop, payload,
               evidence='sim:test', sig=ChannelSig(
                   family='obs', actor='MandateV1Strategy',
                   mode='synthesized', group_id='t'))
    return bs


def test_slot_invariant_fixed_five() -> None:
    """定长不变量:置换/合成都不定长;买光=[empty×5] 而非 None。"""
    bs = _bs_with(_payload(_card('银枝'), _card('黑塔'), _card('刃')))
    a = BuyCard(card=_card('银枝'), reason='test')
    out = apply_shop_action_logic(bs, a, produced_by='MandateV1Strategy',
                                  sig=_SIG)
    assert out.applied
    payload = bs.shop.value
    assert payload is not None and len(payload.cards) == 5
    # 槽几何:被买槽(下标 0)置 empty,其余 content 原位保留
    assert payload.cards[0].kind == 'empty'
    assert [s.card.name for s in payload.cards[1:3]] == ['黑塔', '刃']
    # 买光:逐张买空 → [empty×5],payload 仍非 None
    for _ in range(2):
        nxt = next(s.card for s in bs.shop.value.cards
                   if s.kind == 'content')
        apply_shop_action_logic(bs, BuyCard(card=nxt, reason='test'),
                                produced_by='MandateV1Strategy', sig=_SIG)
    assert bs.shop.value is not None
    assert len(bs.shop.value.cards) == 5
    assert all(s.kind == 'empty' for s in bs.shop.value.cards)


def test_bought_out_fixture_close_shop() -> None:
    """三态判据锁(买光形态):[empty×5] → 决策链降级 CloseShop 不崩。"""
    bs = _bs_with(_payload())   # [empty×5]
    action = decide_shop_action(bs, SimpleNamespace(strategy_state=None),
                                config=SimpleNamespace())
    assert isinstance(action, CloseShop)


@pytest.mark.parametrize('unknown_at', [0, 4])
def test_unknown_window_suppress_spend(unknown_at: int) -> None:
    """失读形态锁:unknown 槽在场 → 花钱禁发射,终结仅 CloseShop。"""
    slots = [_card('银枝'), _card('黑塔'), None, None, None]
    slots[unknown_at] = 'unknown'
    cards = [ShopSlot(kind='unknown') if s == 'unknown'
             else (ShopSlot(kind='content', card=s) if s is not None
                   else ShopSlot(kind='empty')) for s in slots]
    bs = _bs_with(ShopPayload(cards=cards))
    action = decide_shop_action(bs, SimpleNamespace(strategy_state=None),
                                config=SimpleNamespace())
    assert isinstance(action, CloseShop)
    assert not isinstance(action, (BuyCard, RefreshShop))


def test_bought_out_end_to_end_shape() -> None:
    """买光店端到端形状锁(fixture 喂入):帧真值→容器→转移买空→决策
    降级→引擎离屏,四段走真实管线(打回失败 2 的回归锁:买光店单跑
    正常 CloseShop 收工,容器面不再出现 payload=None 假离屏)。"""
    from types import SimpleNamespace as NS
    from sr_od.application.currency_war.kernel.cw_game_state import (
        synthesize_from_game_state,
    )

    def _frame_card(name: str, x: int) -> NS:
        return NS(name=name, faction='仙舟', cost=1, star=1,
                  cost_source='roster', slot=x + 1, x=x,
                  merge_preview=None)

    # 帧真值:店开 3 张(x=0/1/2;买光后帧紧缩表 = 残余 0 张)
    class _Frame:
        """最小帧桩:未设域 __getattr__ 缺省 None(synthesize 可选域全跳过)。"""
        def __init__(self, **kw):
            self.__dict__.update(kw)

        def __getattr__(self, name):
            return None

    frame = _Frame(shop=[_frame_card('银枝', 0), _frame_card('黑塔', 1),
                         _frame_card('刃', 2)],
                   refresh_probs=None)
    bs = board_state_of(None)
    # 段入口:synthesize 按槽映射(店开显式位)
    synthesize_from_game_state(bs, frame, shop_open=True)
    assert len(bs.shop.value.cards) == 5
    assert [s.kind for s in bs.shop.value.cards] == [
        'content', 'content', 'content', 'empty', 'empty']
    # 转移买空:逐张买 → [empty×5]
    for _ in range(3):
        nxt = next(s.card for s in bs.shop.value.cards
                   if s.kind == 'content')
        out = apply_shop_action_logic(bs, BuyCard(card=nxt, reason='test'),
                                      produced_by='MandateV1Strategy',
                                      sig=_SIG)
        assert out.applied
    assert all(s.kind == 'empty' for s in bs.shop.value.cards)
    assert bs.shop.value is not None          # 买光 ≠ 离屏
    # 决策降级:买光牌面 → CloseShop
    action = decide_shop_action(bs, NS(strategy_state=None),
                                config=NS())
    assert isinstance(action, CloseShop)
    # 引擎 CloseShop 腿:leave_screen,payload None = 真离屏
    out = apply_shop_action_logic(bs, CloseShop(),
                                  produced_by='MandateV1Strategy',
                                  sig=_SIG)
    assert out.applied and bs.shop.value is None


def test_real_bought_out_frame_judgment() -> None:
    """真实买光帧 fixture 锁(实机三败现场帧):真实帧 + screen_info 槽
    rect → 逐槽亮度判定必产 [empty×5](买光真值;read_shop_cards 判定表
    的离线可测腿,rect 单一源直读 yml,不经 ctx)。"""
    from pathlib import Path as _P
    import cv2
    import yaml

    frame_path = _P(__file__).parent / 'fixtures' / 'shop_bought_out_frame.png'
    screen = cv2.imdecode(
        __import__('numpy').fromfile(str(frame_path), dtype='uint8'),
        cv2.IMREAD_COLOR)
    assert screen is not None, 'fixture 帧缺失'
    yml = (_P(__import__('sr_od').__file__).parents[2] / 'assets'
           / 'game_data' / 'screen_info'
           / 'currency_war_battle_prep_shop_open.yml')
    doc = yaml.safe_load(yml.read_text(encoding='utf-8'))
    areas = doc.get('area_list') if isinstance(doc, dict) else doc
    kinds = []
    for i in range(1, 6):
        a = next(x for x in areas
                 if x.get('area_name') == f'商店牌-{i}')
        x1, y1, x2, y2 = a['pc_rect']
        crop = screen[y1:y2, x1:x2]
        kinds.append('empty' if float(crop.mean()) < 50 else 'non-empty')
    assert kinds == ['empty'] * 5, kinds


def test_real_bought_out_frames_both_judged() -> None:
    """双实机买光帧 fixture 锁(两败现场帧):同一判定表对两帧均产
    [empty×5](实机失败 1/2 的直接回归锁)。"""
    from pathlib import Path as _P
    import cv2
    import yaml

    yml = (_P(__import__('sr_od').__file__).parents[2] / 'assets'
           / 'game_data' / 'screen_info'
           / 'currency_war_battle_prep_shop_open.yml')
    doc = yaml.safe_load(yml.read_text(encoding='utf-8'))
    areas = doc.get('area_list') if isinstance(doc, dict) else doc
    rects = {a['area_name']: a['pc_rect'] for a in areas
             if str(a.get('area_name', '')).startswith('商店牌-')}
    for fname in ('shop_bought_out_frame.png',
                  'shop_bought_out_frame2.png'):
        fp = _P(__file__).parent / 'fixtures' / fname
        screen = cv2.imdecode(
            __import__('numpy').fromfile(str(fp), dtype='uint8'),
            cv2.IMREAD_COLOR)
        assert screen is not None, fname
        kinds = []
        for i in range(1, 6):
            x1, y1, x2, y2 = rects[f'商店牌-{i}']
            crop = screen[y1:y2, x1:x2]
            kinds.append('empty' if float(crop.mean()) < 50 else 'non-empty')
        assert kinds == ['empty'] * 5, (fname, kinds)


def test_anchor_binary_detectability() -> None:
    """锚二值可检锁(实机三败现场帧):按钮-收起 rect 裁剪二值化后
    白字像素在场(二值化锚门 find_area_in_screen_binary 的 OCR-able
    前提;暗态渲染下原彩色 OCR 拒识的根治判据)。"""
    from pathlib import Path as _P
    import cv2
    import yaml

    yml = (_P(__import__('sr_od').__file__).parents[2] / 'assets'
           / 'game_data' / 'screen_info'
           / 'currency_war_battle_prep_shop_open.yml')
    doc = yaml.safe_load(yml.read_text(encoding='utf-8'))
    areas = doc.get('area_list') if isinstance(doc, dict) else doc
    rect = next(a['pc_rect'] for a in areas
                if a.get('area_name') == '按钮-收起')
    for fname in ('shop_bought_out_frame.png',
                  'shop_bought_out_frame2.png'):
        fp = _P(__file__).parent / 'fixtures' / fname
        screen = cv2.imdecode(
            __import__('numpy').fromfile(str(fp), dtype='uint8'),
            cv2.IMREAD_COLOR)
        x1, y1, x2, y2 = rect
        crop = screen[y1:y2, x1:x2]
        from one_dragon.utils import cv2_utils
        binary = cv2_utils.to_binary(crop, threshold=127)
        assert binary.ndim in (2, 3)
        if binary.ndim == 2:
            import cv2 as _cv2
            binary = _cv2.cvtColor(binary, _cv2.COLOR_GRAY2BGR)
        assert binary.shape[2] == 3   # 门内产物须 3 通道(实机四败回归位)
        gray = cv2.cvtColor(binary, cv2.COLOR_BGR2GRAY)
        white = float((gray > 0).mean())
        assert white > 0.02, (fname, white)


def test_ev_candidates_physical_slot_idx(monkeypatch) -> None:
    """产生端物理槽锁:中段空位帧的 EV 候选 slot_idx = 数组下标
    (物理槽-1;紧缩序分叉回归锁——实机打回切片 1 审计点)。
    U_X 标定门 stub 掉(候选几何为本锁唯一标的)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
        buy as _buy_mod,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria.buy import (
        ev_buy_candidates,
    )

    class _Prov:
        @staticmethod
        def is_none(_key: str) -> bool:
            return False

    monkeypatch.setattr(_buy_mod, 'provisional', _Prov())

    def _slot(name: str | None) -> ShopSlot:
        return (ShopSlot(kind='content', card=_card(name, 1))
                if name else ShopSlot(kind='empty'))

    # 布局:槽0 空、槽1=甲、槽2 空、槽3=乙(中段空位=分叉形态)
    slots = [_slot(None), _slot('甲'), _slot(None), _slot('乙'),
             _slot(None)]
    cands, _key = ev_buy_candidates(
        99, 0, slots, k_members=(), level=1,
        window=frozenset({1}), counters=None)
    got = sorted(c.slot_idx for c in cands)
    assert got == [1, 3], got   # 物理下标;紧缩序会是 [0, 1]


def test_deployed_unknown_defect_recorded(monkeypatch) -> None:
    """unknown 显态锁(T-191 批1):亮度≥50 的识别失败 → 缺陷台账
    槽级 unknown;<50 确证空位不留痕(防刷屏判据与 shop 表同源)。"""
    from types import SimpleNamespace as NS
    import numpy as np
    from sr_od.application.currency_war.obs import cw_identity_obs as io_mod
    from sr_od.application.currency_war.kernel import cw_telemetry_exit

    captured: list[tuple] = []
    monkeypatch.setattr(cw_telemetry_exit, 'record_defect',
                        lambda *a, **k: captured.append(a))
    monkeypatch.setattr(io_mod, 'identify_character', lambda *a, **k: (None, 0))

    class _Rect:
        x1, y1, x2, y2 = 0, 0, 40, 40

    for bright, expect_defect in ((60, True), (30, False)):
        captured.clear()
        screen = np.full((40, 40, 3), bright, dtype='uint8')
        io_mod.identify_slots(screen, templates=None,
                              slots=[(1, _Rect)], row='back')
        assert bool(captured) is expect_defect, (bright, captured)


def test_deployed_rows_slot_number_semantics() -> None:
    """行几何锁:槽表→行表的行内槽号语义(前排 i+1/后排 i-3,1 基信息位;
    缺席=None 不占行序——§7.2 表示不变的确定性不变量)。roundtrip 面
    (unit_rows_to_deployed)契约另审,不入本锁。"""
    from types import SimpleNamespace as NS
    from sr_od.application.currency_war.kernel.cw_game_state import (
        deployed_slots_to_rows,
    )

    def _u(name: str, slot: int) -> NS:
        return NS(char_id=name, star=1, equips=[], slot=slot)

    slots = [None, _u('桑博', 2), None, _u('刃', 4),
             None, _u('银枝', 2), None, None, None, None]
    front, back = deployed_slots_to_rows(slots)
    assert [(u.char_id, u.slot) for u in front] == [('桑博', 2), ('刃', 4)]
    assert [(u.char_id, u.slot) for u in back] == [('银枝', 2)]
    assert (front[0].char_id, front[0].equips) == ('桑博', [])
