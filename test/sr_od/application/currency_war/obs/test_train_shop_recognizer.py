"""开拓商店面板识别器 extras 接线测试(recognizers/train_shop_recognizer.py)。

锁的设计约定(仿金币商店 test_shop_open_recognizer 手法:接线与映射用
打桩,读数真值由 test_cw_trainshop_obs 真帧测试分头锁定):
- recognize 输出 = 面板读数(mode/shop_cards/showcase_card)+ 余额 +
  帕姆进度(dataclass 二元组 → list 的 JSON 化);识别链打桩;
- extras_doc 与输出键集同步(消费方以 doc 为契约面)。
"""

from __future__ import annotations

import sr_od.application.currency_war.obs.recognizers.train_shop_recognizer as mod
from sr_od.application.currency_war.obs.recognizers.train_shop_recognizer import (
    TrainShopPanelRecognizer,
)


def test_recognize_extras_wiring(monkeypatch) -> None:
    """recognize 端到端(打桩识别链):extras 组装 + 帕姆二元组 JSON 化。"""
    monkeypatch.setattr(mod, 'read_trainshop_panel', lambda ctx, image: {
        'mode': 'slots', 'shop_cards': [{'kind': 'refresh', 'card': None}],
        'showcase_card': None})
    monkeypatch.setattr(mod, 'read_trainshop_balance', lambda ctx, image: 20)
    monkeypatch.setattr(mod, 'read_pam_progress', lambda ctx, image: (15, 500))

    rec = TrainShopPanelRecognizer()
    data = rec.recognize(ctx=object(), image=object(), screen_info=None)
    assert data['mode'] == 'slots'
    assert data['shop_cards'] == [{'kind': 'refresh', 'card': None}]
    assert data['showcase_card'] is None
    assert data['balance'] == 20
    assert data['pam_progress'] == [15, 500]   # tuple → JSON list
    assert rec.screen_name == '货币战争-备战-开拓商店'
    # extras_doc 与输出键集同步
    assert set(rec.extras_doc) == {
        'balance', 'mode', 'shop_cards', 'showcase_card', 'pam_progress'}


def test_recognize_extras_none_semantics(monkeypatch) -> None:
    """读不到 → None 透传(不伪造):余额/帕姆/槽带/展示卡四键全 None 形态。"""
    monkeypatch.setattr(mod, 'read_trainshop_panel', lambda ctx, image: {
        'mode': 'unknown', 'shop_cards': None, 'showcase_card': None})
    monkeypatch.setattr(mod, 'read_trainshop_balance', lambda ctx, image: None)
    monkeypatch.setattr(mod, 'read_pam_progress', lambda ctx, image: None)
    rec = TrainShopPanelRecognizer()
    data = rec.recognize(ctx=object(), image=object(), screen_info=None)
    assert data == {'mode': 'unknown', 'shop_cards': None,
                    'showcase_card': None, 'balance': None,
                    'pam_progress': None}
