"""遗器替换列表画面识别器测试(等级文本锚点定位 + 逐卡绑定识别)。

测试层级声明:实机 fixture 直测 recognizer(``recognize`` 只依赖 fixture 图 +
mock screen_loader/ocr_service;不连真游戏)。拆分自 test_equip_list_recognizer
(批次B 遗器/光锥分家,光锥侧见 test_light_cone_list_recognizer)。锁的内容
(出处 ``src/sr_od/application/cultivation/relic/relic_list_recognizer.py``):

- **等级文本锚点定位**:列表每卡底部的「+N」徽章文本 OCR 命中即卡位锚点,
  滚动天然免疫;锚点换算的卡矩形与实机标定值一致(遗器 120×160);
- **遗器绑定识别**:件名(192 件部件图 SIFT)+ 套装 + 部位 + 强化等级(+15 OCR)
  + 占用者(角标头像匹配,黄泉 = 黄泉)。

识别精度基线:角标匹配阈值与实测分数见本模块 ``match_owner`` docstring;
SIFT 全库身份识别的票数下限 = ``identify_cells`` min_votes。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.relic.relic_list_recognizer import (
    RelicReplaceRecognizer,
    _relic_piece_templates,
    _relic_piece_templates_for_pos,
)
from test.conftest import SrTestContext

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'
_CROP_REGRESSION = Path(__file__).parent / 'equip_relic' / 'crop_regression.webp'


def _fake_ctx(test_context: SrTestContext, list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader 按名返回列表区与部位筛选 tab 区 rect;ocr 用真实例;
    template_loader 用真实例(卡面裁片库按 sub_dir 从盘加载)。"""
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
        template_loader=TemplateLoader(),
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
    """轮廓补充卡的网格吸附过滤:同行有锚的真卡保留、贴列表边缘的滚动裁切卡
    丢弃(等级文本滚出、图案不全,识别无消费价值——用户裁定)、离列且离行的
    间隙误检丢弃。(实机三帧证据形态复刻)"""
    rec = _relic_recognizer()
    # 锚点卡:列1 行2 / 列2 行3 / 列2 行5(中心 y: 408 / 557 / 854)
    anchors = [Rect(39, 328, 159, 488), Rect(162, 477, 282, 637), Rect(162, 774, 282, 934)]
    contours = [
        Rect(39, 497, 161, 607),    # 中心 (100,552):列1✓ 行3 带(557)✓ → 漏锚真卡,保留
        Rect(416, 197, 536, 309),   # 中心 (476,253):列4(468)✓ 且贴上边 → 裁切卡,丢弃
        Rect(500, 640, 620, 760),   # 中心 (560,700):离列4(468)92px → 丢弃
        Rect(162, 640, 282, 760),   # 中心 (222,700):列2✓ 但离行3(557)/行5(854)均>70 → 丢弃
    ]
    kept = rec._filter_contour_offgrid(contours, anchors, _LIST_RECT)
    assert Rect(39, 497, 161, 607) in kept, '同行有锚的漏锚真卡应保留'
    assert Rect(416, 197, 536, 309) not in kept, '贴边裁切卡信息不全,不识别'
    assert Rect(500, 640, 620, 760) not in kept, '离列的误检应丢弃'
    assert Rect(162, 640, 282, 760) not in kept, '在列但离锚行带的误检应丢弃'


def test_contour_filter_no_anchor_keeps_all() -> None:
    """无锚点(OCR 全空,如极端滚动位)时轮廓是唯一信息源:行检查豁免,但贴边
    裁切卡与离列误检照常丢弃(裁切卡丢弃语义与有锚一致)。"""
    rec = _relic_recognizer()
    contours = [Rect(416, 197, 536, 309), Rect(289, 345, 411, 458)]
    kept = rec._filter_contour_offgrid(contours, [], _LIST_RECT)
    assert Rect(289, 345, 411, 458) in kept, '无锚时在列的非贴边卡保留'
    assert Rect(416, 197, 536, 309) not in kept, '无锚时贴边裁切卡照常丢弃'


def test_masked_card_detection() -> None:
    """重掷遮罩卡检测:卡矩形内出现「重」开头文本判 masked;卡外文本不误判。"""
    rec = _relic_recognizer()
    card = Rect(149, 180, 269, 340)

    def _ocr(text: str, cx: float, cy: float) -> list:
        return [SimpleNamespace(data=text, rect=Rect(cx - 20, cy - 8, cx + 20, cy + 8))]

    assert rec._is_masked_card(_ocr('重掷中', 209, 250), card) is True
    assert rec._is_masked_card(_ocr('重掷中', 600, 250), card) is False, '卡外文本不误判'
    assert rec._is_masked_card(_ocr('+15', 209, 330), card) is False, '非重掷文本不误判'


def test_pos_template_subset() -> None:
    """部位先验模板子集:pos=1 全部为头部件、pos=6 全部为连结绳,且为全库子集。"""
    from sr_od.mys.sr_codes import RELIC_POS_CN
    full = _relic_piece_templates()
    for pos in (1, 6):
        subset = _relic_piece_templates_for_pos(pos)
        assert set(subset) <= set(full)
        assert subset, f'部位 {pos} 子集不应为空'
        for name in subset:
            piece = _lookup_piece(name)
            assert piece.pos == pos, f'{name} 应属部位 {RELIC_POS_CN[pos]}'


def test_weak_piece_crop_channel(test_context: SrTestContext) -> None:
    """弱匹配件卡面裁片通道:黑牛仔帽图案(快枪手的野穗毡帽)的官方部件图与
    卡面渲染特征同源性弱(单对匹配仅 5 聚簇),官方图兜底 argmax 恒被无关件
    压过(诗人花冠/登程风帽)→目标件名永不出现→漏检。裁片同源模板(实机帧
    图案区裁片,TemplateLoader relic_card_face 库)以合并统一 argmax 根治——
    同源聚簇 21/27 vs 官方图最佳 10/13。

    锁(出处 relic_list_recognizer 裁片通道注释):
    - 两张黑帽卡判「快枪手的野穗毡帽」且 identity=crop(竞争胜出来源);
    - 负样本卡不被裁片低簇噪声误检(官方图高分反压:莳萝花冠 25 簇 fallback)。
    fixture = 识别器失败现场整屏帧(2.5MB webp,整屏识别 >2s,登记 slow_marks)。"""
    img = cv2_utils.read_image(str(_CROP_REGRESSION))
    assert img is not None
    out = RelicReplaceRecognizer().recognize_for_pos(
        _fake_ctx(test_context, Rect(33, 195, 536, 960)), img, 1)
    assert out is not None
    by_cell = {tuple(item['cell']): item for item in out['items']}
    hat_a = by_cell.get((162, 328, 282, 488))
    hat_b = by_cell.get((285, 328, 405, 488))
    assert hat_a is not None and hat_b is not None, '两张黑帽卡应入清单'
    assert hat_a['piece'] == '快枪手的野穗毡帽', f"黑帽A 应判野穗毡帽,实际 {hat_a['piece']}"
    assert hat_a['identity'].startswith('crop'), f"黑帽A 应走裁片通道,实际 {hat_a['identity']}"
    assert hat_b['piece'] == '快枪手的野穗毡帽', f"黑帽B 应判野穗毡帽,实际 {hat_b['piece']}"
    assert hat_b['identity'].startswith('crop'), f"黑帽B 应走裁片通道,实际 {hat_b['identity']}"
    # 负样本:白花头环卡(遐蝶角标)官方图 25 簇应反压裁片,不被低簇噪声误检
    flower = by_cell.get((162, 626, 282, 786))
    assert flower is not None
    assert flower['piece'] == '诗人的莳萝花冠', f"白花头环被误检: {flower['piece']}"
    assert flower['identity'].startswith('fallback'), f"白花头环不应走裁片通道: {flower['identity']}"


def _lookup_piece(name: str):
    from sr_od.mys.sr_relic_sets import PIECE_TO_SET
    set_def = PIECE_TO_SET[name]
    return next(p for p in set_def.pieces if p.name == name)
