"""商店开态识别器 extras 接线测试(refresh_free_count 字段)。

锁的设计约定(recognizers/shop_open_recognizer.py):
- extras 含 refresh_free_count,三态映射 = 按钮态读数直映
  (_free_count_from_button:免费态→次数;付费域→0;判不出→None);
- 消费契约(与观察写端 gs.free_refresh_left 同源口径):付费态语义 = 0
  (游戏规则免费余量恒 0),判不出/失读 = None 不猜(禁当 0 用);
- 识别器其余商店域字段(shop_cards/refresh_probs)接线不回退。

识别链依赖打桩(monkeypatch):本测试锁接线与映射,不锁识别本体
(读数真值由 test_cw_shop_refresh_obs 真帧测试与 test_cw_observation
商店牌测试分头锁定)。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.recognizers.shop_open_recognizer import (
    ShopOpenRecognizer,
    _free_count_from_button,
)


def test_free_count_mapping_pure() -> None:
    """三态映射纯函数:免费态→次数(含失读 None)/付费域→0/判不出→None。"""
    assert _free_count_from_button(True, 4) == 4
    assert _free_count_from_button(True, None) is None   # 免费态次数失读
    assert _free_count_from_button(False, None) == 0     # 付费域余量恒 0
    assert _free_count_from_button(None, None) is None   # 整帧判出不猜


@pytest.mark.parametrize(
    'free, remaining, want',
    [(True, 4, 4), (False, None, 0), (None, None, None)],
    ids=['免费态', '付费态', '判不出'],
)
def test_recognize_exposes_refresh_free_count(
        monkeypatch, free, remaining, want) -> None:
    """recognize 端到端(打桩识别链):extras 带出 refresh_free_count 映射。"""
    import types

    import sr_od.application.currency_war.obs.recognizers.shop_open_recognizer as mod

    monkeypatch.setattr(mod, 'read_prep_extras',
                        lambda ctx, image, full_read=False: {'gold': 53})
    monkeypatch.setattr(mod, 'read_shop_cards', lambda ctx, image: None)
    monkeypatch.setattr(mod, 'read_refresh_probs', lambda ctx, image: None)

    captured: dict = {}

    def _fake_button(ctx, image):
        captured['called'] = True
        return types.SimpleNamespace(free=free, free_remaining=remaining,
                                     price=None, affordable=None)

    monkeypatch.setattr(mod, 'read_shop_refresh_button', _fake_button)
    rec = ShopOpenRecognizer()
    data = rec.recognize(ctx=object(), image=object(), screen_info=None)
    assert captured.get('called') is True
    assert data['refresh_free_count'] == want
    # 既有商店域字段接线不回退
    assert data['gold'] == 53
    assert data['shop_cards'] is None
    assert data['refresh_probs'] is None
    # extras_doc 声明与字段同步(消费方以 doc 为契约面)
    assert 'refresh_free_count' in rec.extras_doc
