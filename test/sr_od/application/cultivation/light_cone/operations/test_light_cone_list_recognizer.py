"""光锥替换列表画面识别器测试(等级文本锚点定位 + 逐卡绑定识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader/ocr_service;不连真游戏)。拆分自 test_equip_list_recognizer
(批次B 遗器/光锥分家,遗器侧见 test_relic_list_recognizer)。锁的内容(出处
``src/sr_od/application/cultivation/light_cone/light_cone_list_recognizer.py``):

- **等级文本锚点定位**:列表每卡底部的「等级N」徽章文本 OCR 命中即卡位锚点,
  滚动 / 命途分组头天然免疫;锚点换算的卡矩形与实机标定值一致(光锥 139×155);
- **光锥绑定识别**:光锥名(170 件图标 SIFT)+ 命途 + 等级 + 占用者。

识别精度基线:角标匹配阈值与实测分数见本模块 ``match_owner`` docstring;
SIFT 全库身份识别的票数下限 = ``identify_cells`` min_votes。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.light_cone.light_cone_list_recognizer import (
    LightConeReplaceRecognizer,
    _superimpose_templates,
)
from test.conftest import SrTestContext

_FIXTURE_DIR = Path(__file__).parent / 'equip_light_cone'


def _fake_ctx(test_context: SrTestContext, list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader 按名返回列表区 rect;ocr 用真实例;
    template_loader 用真实例(叠影 rank 识别读分档模板)。"""
    areas = {
        '区域-光锥列表': list_rect,
    }

    def get_area(screen_name: str, area_name: str) -> SimpleNamespace:
        if area_name not in areas:
            raise KeyError(f'unexpected area: {area_name}')
        return SimpleNamespace(rect=areas[area_name])

    return SimpleNamespace(
        screen_loader=SimpleNamespace(get_area=get_area),
        template_loader=TemplateLoader(),
        ocr_service=test_context.ocr_service)


def test_cone_recognizer(test_context: SrTestContext) -> None:
    """光锥列表:完整绑定(光锥名+命途+等级+占用者)逐卡识别。"""
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col0.webp'))
    assert img is not None
    out = LightConeReplaceRecognizer().recognize(
        _fake_ctx(test_context, Rect(95, 130, 1420, 960)), img, None)

    assert out is not None
    # 锚点定位:「等级N」文本(列表卡区域,排除右侧详情的 等级80/80)
    assert out['total_cards'] >= 4
    by_cell = {tuple(item['cell']): item for item in out['items']}
    # 卡1(行列解耦:固定列中心167.5/行带cy=343 → 卡矩形 97,197-236,352)
    card1 = by_cell.get((97, 197, 236, 352))
    assert card1 is not None, f'卡1 应入清单,实际 keys={list(by_cell)[:4]}'
    assert card1['cone'] == '行于流逝的岸'
    assert card1['path_cn'] == '虚无'
    assert card1['level'] == 80
    assert card1['owner'] == '黄泉'


def test_superimpose_templates_exist(test_context: SrTestContext) -> None:
    """叠影模板资产在盘且走 TemplateLoader 规范(单模板/档,底色差异由归一化
    相关系数+滑动匹配吸收;III/IV 候采样补档)。"""
    templates = _superimpose_templates(test_context.template_loader)
    for tid in ('1', '2', '5'):
        assert tid in templates, f'叠影模板 {tid} 缺失'
