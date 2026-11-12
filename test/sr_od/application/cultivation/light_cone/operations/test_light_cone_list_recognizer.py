"""光锥替换列表画面识别器测试(等级文本锚点定位 + 逐卡绑定识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader/ocr_service;不连真游戏)。拆分自 test_equip_list_recognizer
(批次B 遗器/光锥分家,遗器侧见 test_relic_list_recognizer)。锁的内容
(出处 ``src/sr_od/application/cultivation/light_cone/light_cone_list_recognizer.py``):

- **等级文本锚点定位**:列表每卡底部的「等级N」徽章文本 OCR 命中即卡位锚点,
  滚动 / 命途分组头天然免疫;锚点换算的卡矩形与实机标定值一致(光锥 139×155);
- **光锥绑定识别**:光锥名(170 件图标 masked TM)+ 命途 + 等级 + 占用者
  + 叠影。

识别精度基线:角标匹配阈值与实测分数见本模块 ``match_owner`` docstring;
TM 身份层的拒答门槛 = ``_TM_GATE``,实机真值卡彩色 NCC ≥ 0.95(3 星卡下限,
4-5 星 ≥0.98;选中卡白框档由 ``_TM_CASCADE_GATE`` 级联救回)。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cv2
from test.conftest import SrTestContext

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.light_cone.light_cone_list_recognizer import (
    LightConeReplaceRecognizer,
    _superimpose_templates,
)

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
    # 卡1(行列解耦:固定列中心167.5/行带cy=340 → 卡矩形 97,197-236,352;
    # 该卡为选中态白框卡,身份由主档 0.927 级联救回选中档 0.987)
    card1 = by_cell.get((97, 197, 236, 352))
    assert card1 is not None, f'卡1 应入清单,实际 keys={list(by_cell)[:4]}'
    assert card1['cone'] == '行于流逝的岸'
    assert card1['path_cn'] == '虚无'
    assert card1['level'] == 80
    assert card1['owner'] == '黄泉'
    # 邻卡判名互异:行0列2 为不同款(晚安与睡颜),防整行同名串扰
    assert by_cell[(236, 197, 375, 352)]['cone'] == '晚安与睡颜'


def test_superimpose_templates_exist(test_context: SrTestContext) -> None:
    """叠影模板资产在盘且走 TemplateLoader 规范(单模板/档,底色差异由归一化
    相关系数+滑动匹配吸收;III/IV 候采样补档)。"""
    templates = _superimpose_templates(test_context.template_loader)
    for tid in ('1', '2', '5'):
        assert tid in templates, f'叠影模板 {tid} 缺失'


#------------------- 网格插值补卡(锚点漏采样的网格拓扑补全) -------------------#

_ANCHOR_LIST_RECT = Rect(95, 130, 1420, 985)
_CONE_COL_CENTERS = [95 + 72.5 + 139 * i for i in range(9)]


def _anchor(text: str, col_cx: float, cy: float) -> SimpleNamespace:
    return SimpleNamespace(data=text, rect=Rect(col_cx - 20, cy - 8, col_cx + 20, cy + 8))


def test_grid_fill_missing_cols_in_band() -> None:
    """行带内补列:同一行带锚点数 < 列数时,缺列入补位候选清单(标定帧行3列6
    锚点文本带尾点 OCR 噪声被锚点正则拒绝、整列漏锚实证);补位是否出卡由
    调用方按内容证据取舍(分组列表组末行常不满,纯函数只分拣不判定)。"""
    import sr_od.application.cultivation.light_cone.light_cone_list_recognizer as lclr
    ocr = [
        _anchor('等级80', 168, 340),   # 行1 列1
        _anchor('等级80', 446, 340),   # 行1 列3(其余列锚点漏采样)
        _anchor('等级80', 168, 512),   # 行2 列1
        _anchor('等级1', 307, 512),    # 行2 列2
    ]
    evid, interp = lclr.detect_card_anchors(ocr, _ANCHOR_LIST_RECT, _CONE_COL_CENTERS)
    # 锚点位 4,补位候选 = 2 行带 × 9 列 - 4 锚点位 = 14
    assert len(evid) == 4, f'锚点位应 4 张,实际 {len(evid)}'
    assert len(interp) == 14, f'补位候选应 14 张,实际 {len(interp)}'
    # 列2 无锚点 → 补位候选(卡 139×155)
    assert Rect(236, 197, 375, 352) in interp, '列2 缺锚卡应入补位候选'


def test_grid_interpolate_missing_row() -> None:
    """行带间插行:相邻行带间距 = 2×标准行距(344)时,中间补出整行漏锚卡候选;
    间距非标准行距整数倍时不乱插。"""
    import sr_od.application.cultivation.light_cone.light_cone_list_recognizer as lclr
    # 行带 340 → 684(间距 344 = 2×172),中间应插出 ≈512 行带
    ocr = [
        _anchor('等级80', 168, 340), _anchor('等级1', 307, 340),
        _anchor('等级80', 168, 684), _anchor('等级1', 446, 684),
    ]
    evid, interp = lclr.detect_card_anchors(ocr, _ANCHOR_LIST_RECT, _CONE_COL_CENTERS)
    assert len(evid) == 4, f'锚点位应 4 张,实际 {len(evid)}'
    assert len(evid) + len(interp) == 27, f'3 行 × 9 列应 27 张,实际 {len(evid) + len(interp)}'
    mid_band = [r for r in interp if 430 < r.y2 < 600]
    assert len(mid_band) == 9, f'插值行带应 9 张候选,实际 {len(mid_band)}'

    # 间距 250(非 172 整数倍,超容差)→ 不插,仅两行带 18 张
    ocr2 = [
        _anchor('等级80', 168, 340), _anchor('等级1', 307, 340),
        _anchor('等级80', 168, 590), _anchor('等级1', 446, 590),
    ]
    evid2, interp2 = lclr.detect_card_anchors(ocr2, _ANCHOR_LIST_RECT, _CONE_COL_CENTERS)
    assert len(evid2) + len(interp2) == 18, f'异常间距不应插行,实际 {len(evid2) + len(interp2)} 张'


def test_phantom_empty_slots_dropped(test_context: SrTestContext) -> None:
    """组末不满行的空格守卫(实机滚动帧):命途相符组末行 28 = 3 满行 + 1,
    行4 列2-9 为纯星空空格——插值补位候选须过轮廓/等级文本证据,全数丢弃
    (旧版无条件补位把空格当卡,TM 出 0.90-0.95 幻影条目实证;边缘像素数
    阈值判据因星空闪烁动画逐帧漂移已废弃)。"""
    import sr_od.application.cultivation.light_cone.light_cone_list_recognizer as lclr
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_scrolled_groups.webp'))
    assert img is not None
    list_rect = Rect(95, 130, 1420, 960)
    col_centers = [list_rect.x1 + 72.5 + 139 * i for i in range(9)]
    ocr = test_context.ocr_service.get_ocr_result_list(image=img, crop_first=False)
    evid, interp = lclr.detect_card_anchors(ocr, list_rect, col_centers)
    assert len(evid) == 28, f'锚点位应 28 张(27 满行 + 智库),实际 {len(evid)}'
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    contours = lclr.detect_card_rects_contours(gray, list_rect)
    kept = lclr.LightConeReplaceRecognizer._keep_evidenced_interps(
        lclr.LightConeReplaceRecognizer(), list(evid), interp, contours, ocr)
    # 行4 列2-9 的空格补位候选全数丢弃:存活补位不含该行带(y1∈[560,760])
    survivors = [r for r in kept if 560 <= r.y1 <= 760]
    assert not survivors, f'空格补位应全数丢弃,实际存活 {survivors}'
