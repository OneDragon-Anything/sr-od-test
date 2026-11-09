"""装备替换列表画面识别器测试(等级文本锚点定位 + 逐卡绑定识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader/ocr_service;不连真游戏)。锁的内容(出处
``src/sr_od/operations/equip_list_recognizer.py``):

- **等级文本锚点定位**:列表每卡底部的等级徽章文本(光锥「等级N」/遗器「+N」)
  OCR 命中即卡位锚点,滚动 / 命途分组头天然免疫;锚点换算的卡矩形与实机标定
  值一致(光锥 139×155 / 遗器 120×160);
- **遗器绑定识别**:件名(192 件部件图 SIFT)+ 套装 + 部位 + 强化等级(+15 OCR)
  + 占用者(角标头像匹配,黄泉 = 黄泉);
- **光锥绑定识别**:光锥名(170 件图标 SIFT)+ 命途 + 等级 + 占用者。

识别精度基线:角标匹配阈值与实测分数见 ``equip_owner_match.match_owner``;
SIFT 全库身份识别的票数下限 = ``identify_cells`` min_votes。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.operations.equip_list_recognizer import (
    LightConeReplaceRecognizer,
    RelicReplaceRecognizer,
)
from test.conftest import SrTestContext

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'
_CONE_FIXTURE = Path(__file__).parent / 'equip_light_cone' / 'replace_target_row0_col0.webp'


def _fake_ctx(test_context: SrTestContext, list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader 返回固定列表区 rect;ocr_service 用真实例。"""
    return SimpleNamespace(
        screen_loader=SimpleNamespace(
            get_area=lambda screen_name, area_name: SimpleNamespace(rect=list_rect)),
        ocr_service=test_context.ocr_service)


def test_relic_recognizer(test_context: SrTestContext) -> None:
    """遗器列表:已装备件识别完整绑定(件名+套装+部位+强化等级+占用者)。"""
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_head_row0.webp'))
    assert img is not None
    out = RelicReplaceRecognizer().recognize(
        _fake_ctx(test_context, Rect(33, 195, 536, 960)), img, None)

    assert out is not None
    # 锚点定位:「+15」文本每卡一个,fixture 可见 4 行的已强化卡均应定位
    assert out['total_cards'] >= 4
    by_cell = {tuple(item['cell']): item for item in out['items']}
    # 卡1(锚点 cx=99,cy=318 → 卡矩形 39,180-159,340)
    card1 = by_cell.get((39, 180, 159, 340))
    assert card1 is not None, f'卡1 应入清单,实际 keys={list(by_cell)[:4]}'
    assert card1['piece'] == '先驱的绝热围壳'
    assert card1['set'] == '死水深潜的先驱'
    assert card1['pos_cn'] == '头部'
    assert card1['level'] == 15
    assert card1['owner'] == '黄泉'
    # 其他格的角标是别的角色:不得误配为黄泉
    for cell, item in by_cell.items():
        if cell != (39, 180, 159, 340):
            assert item['owner'] != '黄泉', f'非黄泉角标误配: {cell} -> {item}'


def test_cone_recognizer(test_context: SrTestContext) -> None:
    """光锥列表:完整绑定(光锥名+命途+等级+占用者)逐卡识别。"""
    img = cv2_utils.read_image(str(_CONE_FIXTURE))
    assert img is not None
    out = LightConeReplaceRecognizer().recognize(
        _fake_ctx(test_context, Rect(95, 130, 1420, 960)), img, None)

    assert out is not None
    # 锚点定位:「等级N」文本(列表卡区域,排除右侧详情的 等级80/80)
    assert out['total_cards'] >= 4
    by_cell = {tuple(item['cell']): item for item in out['items']}
    # 卡1(锚点「等级80」cx=166,cy=343 → 卡矩形 96,200-235,355)
    card1 = by_cell.get((96, 200, 235, 355))
    assert card1 is not None, f'卡1 应入清单,实际 keys={list(by_cell)[:4]}'
    assert card1['cone'] == '行于流逝的岸'
    assert card1['path_cn'] == '虚无'
    assert card1['level'] == 80
    assert card1['owner'] == '黄泉'
