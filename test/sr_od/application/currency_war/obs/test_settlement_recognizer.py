"""货币战争结算画面胜负标识三态帧复放(``SettlementRecognizer`` + 画面档标题 area 同契约)。

锁的设计约定:
- 画面档「货币战争-结算」标题区两个单一语义 area 互斥:胜局帧只命中「标识-挑战成功」,
  败局(结束)帧只命中「标识-挑战结束」——area 名即胜负,读 analyze ``areas[]`` 不必再看 matched_text。
  故障形态(故障样本 = ended 帧):标题 area 若按默认 lcs 0.5 匹配,「挑战结束」与「挑战成功」
  共享 2 字前缀(2/4=0.5 恰过阈)会命中胜局 area,area 名与实况相反。
- 识别器 extras ``verdict`` 三态真帧真值:win / ended / failed;``is_failed`` 由 verdict 派生。
- 团灭屏「货币战争-挑战失败」标题「挑战失败」不得串中「货币战争-结算」的任一标题 area。

帧来源(测试仓中央归档,真值由建档人工确认):
- 货币战争-结算/win.webp:普通胜利(小队生命值 20)
- 货币战争-结算/ended.webp:1-9 首领战败、小队生命值 1,对局未终(仍有「继续挑战」)
- 货币战争-挑战失败/failed.webp:团灭终局
一帧一次 OCR(内容哈希 memo 跨调用复用),area 命中与识别器断言共用;缺帧 skip。
"""
from __future__ import annotations

import pytest
from test.conftest import SrTestContext

from one_dragon.base.screen.screen_match import find_area_with_detail
from sr_od.application.currency_war.obs.cw_settlement_obs import (
    parse_settlement_verdict,
)
from sr_od.application.currency_war.obs.recognizers.settlement_recognizer import (
    SettlementRecognizer,
)

#: 普通结算屏(识别器注册屏;两个标题 area 所在屏)
_SETTLE_SCREEN: str = '货币战争-结算'
#: 团灭屏(自带「标识-挑战失败」;本屏无识别器注册,verdict 由同一纯函数映射锁定)
_FAILED_SCREEN: str = '货币战争-挑战失败'

#: (帧屏, 帧态, 应命中 area 所属屏, 应命中 area, 应命中 matched_text, 应 miss 的结算屏标题 area, verdict, is_failed, hp_after)
_CASES: list[tuple[str, str, str, str, str, list[str], str, bool, int | None]] = [
    (_SETTLE_SCREEN, 'win', _SETTLE_SCREEN, '标识-挑战成功', '挑战成功',
     ['标识-挑战结束'], 'win', False, 20),
    # 故障样本:修前此帧命中「标识-挑战成功」(matched_text=挑战结束)= 误判为胜
    (_SETTLE_SCREEN, 'ended', _SETTLE_SCREEN, '标识-挑战结束', '挑战结束',
     ['标识-挑战成功'], 'ended', False, 1),
    (_FAILED_SCREEN, 'failed', _FAILED_SCREEN, '标识-挑战失败', '挑战失败',
     ['标识-挑战成功', '标识-挑战结束'], 'failed', True, 0),
]


@pytest.mark.parametrize(
    ('frame_screen', 'state', 'hit_screen', 'hit_area', 'hit_text',
     'miss_areas', 'verdict', 'is_failed', 'hp_after'),
    _CASES,
)
def test_settle_verdict_three_states_frame_replay(
    test_context: SrTestContext,
    frame_screen: str, state: str,
    hit_screen: str, hit_area: str, hit_text: str,
    miss_areas: list[str], verdict: str, is_failed: bool, hp_after: int | None,
) -> None:
    """三态各一帧:area 命中组合互斥 + 纯函数 verdict + 识别器 extras 三字段。"""
    if not test_context.has_screen(frame_screen, state):
        pytest.skip(f'存档截图缺失:screens/{frame_screen}/{state}.webp')
    img = test_context.load_screen(frame_screen, state)

    # ① 画面档标题 area:应命中者命中且 matched_text 全等;应 miss 者不命中(兄弟词不互串)
    detail = find_area_with_detail(
        test_context, img, test_context.screen_loader.get_area(hit_screen, hit_area))
    assert detail is not None, f'{state}: 「{hit_area}」应命中'
    assert detail.matched_text == hit_text, f'{state}: matched_text={detail.matched_text!r}'
    for miss in miss_areas:
        assert find_area_with_detail(
            test_context, img, test_context.screen_loader.get_area(_SETTLE_SCREEN, miss)) is None, \
            f'{state}: 「{miss}」不应命中(兄弟标题词互串)'

    # ② 纯函数三态 + ③ 识别器 extras(同一帧;OCR 命中内容哈希 memo 不重复推理)
    texts = [r.data for r in test_context.ocr_service.get_ocr_result_list(
        image=img, rect=None, crop_first=False)]
    assert parse_settlement_verdict(texts) == verdict
    extras = SettlementRecognizer().recognize(ctx=test_context, image=img, screen_info=None)
    assert extras == {'hp_after': hp_after, 'is_failed': is_failed, 'verdict': verdict}
