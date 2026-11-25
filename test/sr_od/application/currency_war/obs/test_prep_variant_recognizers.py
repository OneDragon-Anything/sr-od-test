"""备战变体画面识别器接线测试(recognizers/prep_variant_recognizers.py)。

锁的设计约定(仿开拓商店 test_train_shop_recognizer 手法,识别链打桩):
- 每个备战变体屏(免战 / 选择主角 / 茶歇预告)各有识别器,screen_name 与画面档一致;
- recognize 原样委托 ``read_prep_extras(full_read=True)``(变体 = 备战全量读数,
  不叠加不省略;漏传 ``full_read=True`` 会落成省略态读数);
- extras_doc = 备战读数说明 + ``state_note``(消费方以 doc 为契约面)。

端到端(需完整 SR 数据栈,本地跑):茶歇预告归档帧经框架扫描注册的识别器读出
全量 extras,关键读数与帧上实读一致——锁「变体帧精准命中后有读数」这一接线
(变体没有识别器时读数恒 null)。
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

import sr_od.application.currency_war.obs.recognizers.prep_variant_recognizers as mod
from sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer import (
    PREP_EXTRAS_DOC,
)
from sr_od.application.currency_war.obs.recognizers.prep_variant_recognizers import (
    BattlePrepSelectHeroRecognizer,
    BattlePrepSkipRecognizer,
    BattlePrepTeaNoticeRecognizer,
)
from sr_od.backend.screen_recognizer_scan import scan_recognizers

if TYPE_CHECKING:
    from test.conftest import SrTestContext

    from one_dragon.base.screen.screen_recognizer import ScreenRecognizer

#: (识别器类, 画面名)——画面名 = 画面档 screen_name(analyze 精准命中后按它查表)。
_VARIANTS: list[tuple[type[ScreenRecognizer], str]] = [
    (BattlePrepSkipRecognizer, '货币战争-备战-免战'),
    (BattlePrepSelectHeroRecognizer, '货币战争-备战-选择主角'),
    (BattlePrepTeaNoticeRecognizer, '货币战争-备战-茶歇预告'),
]

_TEA_SCREEN: str = '货币战争-备战-茶歇预告'
_TEA_STATE: str = '茶歇预告态'


@pytest.mark.parametrize(('cls', 'screen_name'), _VARIANTS,
                         ids=[name for _, name in _VARIANTS])
def test_variant_recognizer_delegates_full_read(
    monkeypatch: pytest.MonkeyPatch,
    cls: type[ScreenRecognizer],
    screen_name: str,
) -> None:
    """变体识别器 = 备战全量读数原样委托(打桩识别链)。"""
    sentinel: dict = {'gold': 27, 'phase': [1, 8], 'state_note': '来自备战读数'}
    calls: list[bool] = []

    def fake_read(ctx: object, image: object, full_read: bool = False) -> dict:
        calls.append(full_read)
        return sentinel

    monkeypatch.setattr(mod, 'read_prep_extras', fake_read)

    rec = cls()
    data = rec.recognize(ctx=object(), image=object(), screen_info=None)

    assert rec.screen_name == screen_name
    assert calls == [True], '必须以 full_read=True 委托(全量读数)'
    assert data is sentinel, '返回值应原样透传,不叠加不省略'
    assert set(rec.extras_doc) == set(PREP_EXTRAS_DOC) | {'state_note'}


@pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈(screen_info / 模板 / OCR),CI clean checkout 无;本地有数据则跑',
)
def test_tea_notice_frame_full_extras(test_context: SrTestContext) -> None:
    """茶歇预告归档帧:扫描注册命中 + 读数全量,关键读数与帧上实读一致。

    帧上实读(顶栏「1-8」、部署「4/5」、商店卡金币「27」);读数键集 = 备战
    读数说明全集(``state_note`` 只是说明键,不在读数里)。
    """
    if not test_context.has_screen(_TEA_SCREEN, _TEA_STATE):
        pytest.skip(f'存档截图缺失:screens/{_TEA_SCREEN}/{_TEA_STATE}.webp')

    registry = scan_recognizers(test_context, refresh=True).registry
    rec = registry.get(_TEA_SCREEN)
    assert type(rec).__name__ == 'BattlePrepTeaNoticeRecognizer'

    image = test_context.load_screen(_TEA_SCREEN, _TEA_STATE)
    screen_info = test_context.screen_loader.get_screen(_TEA_SCREEN)
    data = rec.recognize(ctx=test_context, image=image, screen_info=screen_info)

    assert data is not None
    assert set(PREP_EXTRAS_DOC) <= set(data)
    assert tuple(data['phase']) == (1, 8)   # 进程内为二元组(MCP 响应里才转 list)
    assert (data['deploy_count'], data['deploy_cap']) == (4, 5)
    assert data['gold'] == 27
