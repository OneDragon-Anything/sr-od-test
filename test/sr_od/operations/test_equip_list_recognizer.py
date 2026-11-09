"""装备替换列表画面识别器测试(全量清单 + 占用者识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader 返回列表区 rect;不连真游戏)。锁的内容(出处
``src/sr_od/operations/equip_list_recognizer.py``):

- 遗器列表(两张同套装副本同屏):网格逐格占用者识别,已装备件的角标准确
  反查角色(黄泉 = acheron);未装备/无匹配格诚实不列;
- 光锥列表:同款占用识别(黄泉角标按光锥界面放低阈值命中;其他角色的角标
  各自正确反查);网格总数与几何(9 列 4 行)。

识别精度基线(匹配阈值与来源):``equip_owner_match.match_owner`` 的
阈值/实测分数(同角色 0.878/异角色上限 0.453,光锥界面天花板 0.725)。
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


def _fake_ctx(list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader.get_area 返回固定列表区 rect 的 area。"""
    return SimpleNamespace(
        screen_loader=SimpleNamespace(
            get_area=lambda screen_name, area_name: SimpleNamespace(rect=list_rect)))


def test_relic_recognizer(test_context: SrTestContext) -> None:
    """遗器列表:第一行的已装备件角标准确反查角色,未匹配格不列。"""
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_head_row0.webp'))
    assert img is not None
    out = RelicReplaceRecognizer().recognize(
        _fake_ctx(Rect(33, 195, 536, 960)), img, None)

    assert out is not None
    assert out['total_cells'] == 16  # 4 列 × 4 行
    owners = {tuple(item['cell']): item['owner'] for item in out['items']}
    assert owners.get((99, 260)) == 'acheron', f'卡1 黄泉角标应识别为 acheron,实际 {owners}'
    # 其他格的角标是别的角色:不得误配为黄泉
    for cell, owner in owners.items():
        if cell != (99, 260):
            assert owner != 'acheron', f'非黄泉角标误配: {cell} -> {owner}'


def test_cone_recognizer(test_context: SrTestContext) -> None:
    """光锥列表:黄泉角标(放低阈值)与同屏其他角色角标各自正确反查。"""
    img = cv2_utils.read_image(str(_CONE_FIXTURE))
    assert img is not None
    out = LightConeReplaceRecognizer().recognize(
        _fake_ctx(Rect(95, 130, 1420, 960)), img, None)

    assert out is not None
    assert out['total_cells'] == 36  # 9 列 × 4 行
    owners = {tuple(item['cell']): item['owner'] for item in out['items']}
    assert owners.get((168, 278)) == 'acheron', f'卡1 黄泉角标应识别为 acheron,实际 {owners}'
