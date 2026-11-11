"""遗器替换列表画面识别器测试(等级文本锚点定位 + 逐卡绑定识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader/ocr_service;不连真游戏)。拆分自 test_equip_list_recognizer
(批次B 遗器/光锥分家,光锥侧见 test_light_cone_list_recognizer)。锁的内容
(出处 ``src/sr_od/application/cultivation/relic/relic_list_recognizer.py``):

- **等级文本锚点定位**:列表每卡底部的「+N」徽章文本 OCR 命中即卡位锚点,
  滚动天然免疫;锚点换算的卡矩形与实机标定值一致(遗器 120×160);
- **遗器绑定识别**:件名(196 件部件图 masked TM)+ 套装 + 部位 + 强化等级(+15 OCR)
  + 占用者(角标头像匹配,黄泉 = 黄泉)。

识别精度基线:角标匹配阈值与实测分数见本模块 ``match_owner`` docstring;
TM 身份层的拒答门槛 = ``_TM_GATE``,实机真值卡彩色 NCC ≥ 0.93。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from test.conftest import SrTestContext

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.relic.relic_list_recognizer import (
    RelicReplaceRecognizer,
    _tm_templates_all,
    _tm_templates_for_pos,
)

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'


def _fake_ctx(test_context: SrTestContext, list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader 按名返回列表区与部位筛选 tab 区 rect;ocr 用真实例。"""
    areas = {
        '区域-遗器列表': list_rect,
        '部位TAB-头部': Rect(110, 122, 166, 164),
        '部位TAB-手部': Rect(173, 122, 229, 164),
        '部位TAB-躯干': Rect(236, 122, 292, 164),
        '部位TAB-腿部': Rect(299, 122, 355, 164),
        '部位TAB-位面球': Rect(362, 122, 418, 164),
        '部位TAB-连结绳': Rect(425, 122, 481, 164),
    }

    def get_area(screen_name: str, area_name: str) -> SimpleNamespace:
        if area_name not in areas:
            raise KeyError(f'unexpected area: {area_name}')
        return SimpleNamespace(rect=areas[area_name])

    return SimpleNamespace(
        screen_loader=SimpleNamespace(get_area=get_area),
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


#------------------- 定位层网格吸附过滤(轮廓补充误检防线) -------------------#

_LIST_RECT = Rect(33, 195, 536, 960)


def test_detect_pos_from_tabs(test_context: SrTestContext) -> None:
    """部位筛选 tab 选中态判定(fixture = 头部筛选实机帧):选中 tab 底部白条
    指示器(灰度>180 像素 ≥10)判出 pos=1,未选中格全 0。"""
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_head_row0.webp'))
    assert img is not None
    rec = RelicReplaceRecognizer()
    assert rec._detect_pos_from_tabs(_fake_ctx(test_context, _LIST_RECT), img) == 1


def _relic_recognizer() -> RelicReplaceRecognizer:
    return RelicReplaceRecognizer()


def test_contour_offgrid_filter() -> None:
    """轮廓补充卡的网格吸附过滤:同行有锚的完整真卡保留、可见高度不足的部分
    卡丢弃(图案不全,识别无消费价值)、离列且离行的间隙误检丢弃。
    (判据 = 可见高度,非贴边——网格行1 卡 y1 略超列表区上界属完整卡,
    按贴边会整行误杀,4.7 版本实机脚部帧行1 三卡实证)"""
    rec = _relic_recognizer()
    # 锚点卡:列1 行2 / 列2 行3 / 列2 行5(中心 y: 408 / 557 / 854)
    anchors = [Rect(39, 328, 159, 488), Rect(162, 477, 282, 637), Rect(162, 774, 282, 934)]
    contours = [
        Rect(39, 497, 161, 657),    # 中心 (100,577):列1✓ 行2 带(408)✓ 高160 → 漏锚完整真卡,保留
        Rect(416, 197, 536, 309),   # 中心 (476,253):列4(468)✓ 但高112<140 → 部分卡,丢弃
        Rect(500, 640, 620, 760),   # 中心 (560,700):离列4(468)92px → 丢弃
        Rect(162, 640, 282, 760),   # 中心 (222,700):列2✓ 但离行3(557)/行5(854)均>70 → 丢弃
    ]
    kept = rec._filter_contour_offgrid(contours, anchors, _LIST_RECT)
    assert Rect(39, 497, 161, 657) in kept, '同行有锚的漏锚完整真卡应保留'
    assert Rect(416, 197, 536, 309) not in kept, '高度不足的部分卡信息不全,不识别'
    assert Rect(500, 640, 620, 760) not in kept, '离列的误检应丢弃'
    assert Rect(162, 640, 282, 760) not in kept, '在列但离锚行带的误检应丢弃'


def test_contour_filter_no_anchor_keeps_all() -> None:
    """无锚点(OCR 全空,如极端滚动位)时轮廓是唯一信息源:行检查豁免,但高度
    不足的部分卡与离列误检照常丢弃(丢弃语义与有锚一致)。"""
    rec = _relic_recognizer()
    contours = [Rect(416, 197, 536, 309), Rect(289, 345, 411, 505)]
    kept = rec._filter_contour_offgrid(contours, [], _LIST_RECT)
    assert Rect(289, 345, 411, 505) in kept, '无锚时在列的完整卡保留'
    assert Rect(416, 197, 536, 309) not in kept, '无锚时高度不足的部分卡照常丢弃'


def test_masked_card_detection() -> None:
    """重掷遮罩卡检测:卡矩形内出现「重」开头文本判 masked;卡外文本不误判。"""
    rec = _relic_recognizer()
    card = Rect(149, 180, 269, 340)

    def _ocr(text: str, cx: float, cy: float) -> list:
        return [SimpleNamespace(data=text, rect=Rect(cx - 20, cy - 8, cx + 20, cy + 8))]

    assert rec._is_masked_card(_ocr('重掷中', 209, 250), card) is True
    assert rec._is_masked_card(_ocr('重掷中', 600, 250), card) is False, '卡外文本不误判'
    assert rec._is_masked_card(_ocr('+15', 209, 330), card) is False, '非重掷文本不误判'


#------------------- 网格插值补卡(锚点漏采样的网格拓扑补全) -------------------#

_ANCHOR_LIST_RECT = Rect(33, 175, 536, 965)


def _anchor(text: str, col_cx: float, cy: float) -> SimpleNamespace:
    return SimpleNamespace(data=text, rect=Rect(col_cx - 20, cy - 8, col_cx + 20, cy + 8))


def test_grid_fill_missing_cols_in_band() -> None:
    """行带内补列:非末行带恒满(列表连续无分组),缺列按固定列先验补出
    (4.7 实机脚部帧行1 单锚点确立行带、列1/3/4 漏锚实证);最后一个行带
    只出锚点位(该行可能不满,空格与漏锚卡不可分,宁缺不猜)。"""
    import sr_od.application.cultivation.relic.relic_list_recognizer as rlr
    ocr = [
        _anchor('+15', 99, 318),   # 行1 列1
        _anchor('+0', 345, 318),   # 行1 列3(列2/列4 锚点漏采样)
        _anchor('+15', 99, 466),   # 行2(末行带) 列1
        _anchor('+0', 222, 466),   # 行2(末行带) 列2
    ]
    rects = rlr.detect_card_anchors(ocr, _ANCHOR_LIST_RECT, [99, 222, 345, 468])
    # 行1(非末行带,恒满)补齐全 4 列;行2(末行带)只出 2 个锚点位
    assert len(rects) == 6, f'非末行 4 列 + 末行锚点位 2 应为 6 张卡,实际 {len(rects)}'
    band1 = [r for r in rects if r.y2 <= 470]
    cols1 = sorted(r.x1 for r in band1)
    assert cols1 == [39, 162, 285, 408], f'行1 应补齐全 4 列,实际 x1={cols1}'
    band2 = [r for r in rects if r.y2 > 470]
    cols2 = sorted(r.x1 for r in band2)
    assert cols2 == [39, 162], f'末行带应只出锚点位,实际 x1={cols2}'


def test_grid_interpolate_missing_row() -> None:
    """行带间插行:相邻行带间距 = 2×标准行距(298)时,中间补出整行漏锚卡;
    间距非标准行距整数倍时不乱插。插值行夹在证实行带之间属连续区间内部,
    恒满照常全列补出;末行带只出锚点位。"""
    import sr_od.application.cultivation.relic.relic_list_recognizer as rlr
    # 行带 318 → 616(间距 298 = 2×149),中间应插出 ≈467 行带
    ocr = [
        _anchor('+15', 99, 318), _anchor('+0', 222, 318),
        _anchor('+15', 99, 616), _anchor('+0', 345, 616),
    ]
    rects = rlr.detect_card_anchors(ocr, _ANCHOR_LIST_RECT, [99, 222, 345, 468])
    # 行1(非末行带)4 列 + 插值行(内部,恒满)4 列 + 末行带锚点位 2 = 10
    assert len(rects) == 10, f'4+4+2 应为 10 张卡,实际 {len(rects)}'
    mid_band = [r for r in rects if 380 < r.y2 < 560]
    assert len(mid_band) == 4, f'插值行带应有 4 张卡,实际 {len(mid_band)}'

    # 间距 250(非 149 整数倍,超容差)→ 不插,首行 4 + 末行锚点位 2 = 6
    ocr2 = [
        _anchor('+15', 99, 318), _anchor('+0', 222, 318),
        _anchor('+15', 99, 568), _anchor('+0', 345, 568),
    ]
    rects2 = rlr.detect_card_anchors(ocr2, _ANCHOR_LIST_RECT, [99, 222, 345, 468])
    assert len(rects2) == 6, f'异常间距不应插行,实际 {len(rects2)} 张'


def test_pos_template_subset() -> None:
    """部位先验模板子集:pos=1 全部为头部件、pos=6 全部为连结绳(双档同名多条目),
    且为全库子集。"""
    from sr_od.mys.sr_codes import RELIC_POS_CN
    full = _tm_templates_all()
    for pos in (1, 6):
        subset_main, subset_sel = _tm_templates_for_pos(pos)
        names = {name for name, _tpl, _mask in subset_main}
        assert names <= set(full), '部位子集应为全库子集'
        assert names, f'部位 {pos} 子集不应为空'
        for name in names:
            piece = _lookup_piece(name)
            assert piece.pos == pos, f'{name} 应属部位 {RELIC_POS_CN[pos]}'
        if pos == 6:
            # 连结绳双档:同名多条目(列表常态 + 选中卡放大)
            rope_entries = [e for e in subset_main + subset_sel if e[0] == '茨冈尼亚的轮回纽结']
            assert len(rope_entries) >= 2, '连结绳应有多档模板'
            assert subset_sel, 'pos6 应有选中档模板'


def _lookup_piece(name: str):
    from sr_od.mys.sr_relic_sets import PIECE_TO_SET
    set_def = PIECE_TO_SET[name]
    return next(p for p in set_def.pieces if p.name == name)
