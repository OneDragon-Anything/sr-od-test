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
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from sr_od.operations.equip_list_recognizer import (
    LightConeReplaceRecognizer,
    RelicReplaceRecognizer,
    _superimpose_templates,
)
from test.conftest import SrTestContext

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'
_CONE_FIXTURE = Path(__file__).parent / 'equip_light_cone' / 'replace_target_row0_col0.webp'


def _fake_ctx(test_context: SrTestContext, list_rect: Rect) -> SimpleNamespace:
    """mock ctx:screen_loader 按名返回列表区与部位筛选 tab 区 rect;ocr 用真实例;
    template_loader 用真实例(叠影 rank 识别读分档模板)。"""
    areas = {
        '区域-遗器列表': list_rect,
        '区域-光锥列表': list_rect,
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
    # 卡1(行列解耦:固定列中心167.5/行带cy=343 → 卡矩形 97,197-236,352)
    card1 = by_cell.get((97, 197, 236, 352))
    assert card1 is not None, f'卡1 应入清单,实际 keys={list(by_cell)[:4]}'
    assert card1['cone'] == '行于流逝的岸'
    assert card1['path_cn'] == '虚无'
    assert card1['level'] == 80
    assert card1['owner'] == '黄泉'


def test_superimpose_templates_exist(test_context: SrTestContext) -> None:
    """叠影模板资产在盘且走 TemplateLoader 规范(1/1_dark/2_dark/5 四档已采样;
    III/IV 候采样补档)。"""
    templates = _superimpose_templates(test_context.template_loader)
    for tid in ('1', '1_dark', '2_dark', '5'):
        assert tid in templates, f'叠影模板 {tid} 缺失'


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
    """轮廓补充卡的网格吸附过滤:同行有锚的真卡保留、离列且离行的间隙误检
    丢弃、贴边且在列上的形态保留(裁切卡;实机 (416,197) 形假卡由 IoU 去重
    这第一道防线兜住,网格吸附是第二道)。(实机三帧证据形态复刻)"""
    rec = _relic_recognizer()
    # 锚点卡:列1 行2 / 列2 行3 / 列2 行5(中心 y: 408 / 557 / 854)
    anchors = [Rect(39, 328, 159, 488), Rect(162, 477, 282, 637), Rect(162, 774, 282, 934)]
    contours = [
        Rect(39, 497, 161, 607),    # 中心 (100,552):列1✓ 行3 带(557)✓ → 漏锚真卡,保留
        Rect(416, 197, 536, 309),   # 中心 (476,253):列4(468)✓ 且贴上边 → 按裁切卡保留
        Rect(500, 640, 620, 760),   # 中心 (560,700):离列4(468)92px → 丢弃
        Rect(162, 640, 282, 760),   # 中心 (222,700):列2✓ 但离行3(557)/行5(854)均>70 → 丢弃
    ]
    kept = rec._filter_contour_offgrid(contours, anchors, _LIST_RECT)
    assert Rect(39, 497, 161, 607) in kept, '同行有锚的漏锚真卡应保留'
    assert Rect(416, 197, 536, 309) in kept, '贴边且在列上的形态按裁切卡保留'
    assert Rect(500, 640, 620, 760) not in kept, '离列的误检应丢弃'
    assert Rect(162, 640, 282, 760) not in kept, '在列但离锚行带的误检应丢弃'


def test_contour_filter_no_anchor_keeps_all() -> None:
    """无锚点(OCR 全空,如极端滚动位)时轮廓是唯一信息源:全部保留。"""
    rec = _relic_recognizer()
    contours = [Rect(416, 197, 536, 309), Rect(289, 345, 411, 458)]
    assert rec._filter_contour_offgrid(contours, [], _LIST_RECT) == contours


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
    from sr_od.operations.equip_list_recognizer import (
        _relic_piece_templates,
        _relic_piece_templates_for_pos,
    )
    full = _relic_piece_templates()
    for pos in (1, 6):
        subset = _relic_piece_templates_for_pos(pos)
        assert set(subset) <= set(full)
        assert subset, f'部位 {pos} 子集不应为空'
        for name in subset:
            piece = _lookup_piece(name)
            assert piece.pos == pos, f'{name} 应属部位 {RELIC_POS_CN[pos]}'


def _lookup_piece(name: str):
    from sr_od.mys.sr_relic_sets import PIECE_TO_SET
    set_def = PIECE_TO_SET[name]
    return next(p for p in set_def.pieces if p.name == name)
