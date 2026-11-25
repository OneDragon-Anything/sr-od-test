"""合成确认浮层识别纯函数测试(``obs/cw_synthesis_overlay_obs.py``)。

锁的设计约定。样本 = ``sr-od-test/screens/`` 下三张实机浮层帧(覆盖浮层的三个纵向
档位)、一张干净备战帧、一张合成的「目标装备在装备行最末一行」帧:

- 三档浮层帧各恰一对,✓ 点击坐标落在本档按钮的对照框内;框内装备格的名字与过不过
  线的结论 = 已知答案(测试仓三张浮层样本帧标定)。最高档帧的产物预览格不作门——那
  一件装备的图标模板还没入库,读数跟着模板库组成走。分数不锁(模板库随版本适配增长)。
- 「同一颗按钮内的峰合并」由上一条锁住:真按钮内有多个过阈值的相邻点,不合并就会
  配出多对、判成歧义。
- 匹配范围向下外扩一个模板高、搜索矩形只过滤峰的位置:最末一行的合成帧在场;峰的
  左上角落在矩形下沿以外的不算候选。
- 干净帧与别类帧不出候选;非有限分数丢弃。
- 只有一颗按钮的候选 = 有候选但配不成对;两对 = 歧义。
- 入参缺失抛异常、不判「不在场」;装备图标模板库缺席时三槽未识别、观察照常成功。
- 三张浮层帧经对局中画面全集识别得到的屏名不落别的备战系画面。
"""

from __future__ import annotations

import logging
from functools import cache
from pathlib import Path

import pytest
from test import conftest as test_conftest
from test.conftest import SrTestContext

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.template_info import TemplateInfo
from one_dragon.utils import cv2_utils
from one_dragon.utils.file_utils import get_project_root
from sr_od.application.currency_war.obs import cw_synthesis_overlay_obs as overlay_mod
from sr_od.application.currency_war.obs.cw_equipment import load_equip_tm_grays

_PREP: str = '货币战争-备战'
_OVERLAY_DIR: str = '货币战争-备战-合成确认'
# 装备栏搜索矩形 = 备战画面档「区域-道具装备」的现值
_SEARCH_RECT: Rect = Rect(1620, 90, 1918, 710)
_PREP_FAMILY_SCREENS: set[str] = {_PREP, '货币战争-备战-选择主角'}
_SLOT_KEYS: set[str] = {'name', 'conf', 'cx', 'cy'}
_NOT_GATED = object()   # 这一带不断言读数

# 三档已知答案:(帧目录, 帧名, ✓ 按钮外框 [x1,y1,x2,y2], 原料 1, 原料 2, 产物预览)。
# 名字是门;按钮外框 = 实机帧上 ✓ 按钮的位置。最高档帧的产物预览格不作门。
_KNOWN_ANSWERS: list[tuple] = [
    (_PREP, 'rail_badge_absent_r2', (1770, 298, 1875, 355), '轮滑鞋', '光能电池', _NOT_GATED),
    (_OVERLAY_DIR, '合成确认浮层', (1769, 375, 1874, 431), '轮滑鞋', '折叠小刀', '火力风暴潮'),
    (_OVERLAY_DIR, '合成确认浮层-局B', (1769, 452, 1874, 508), '轮滑鞋', '折叠小刀', '火力风暴潮'),
]
# 已知答案里作门的四件装备:它们的模板必须在库,否则红的原因是库缺件而不是识别坏了
_GATED_TEMPLATE_NAMES: set[str] = {'轮滑鞋', '光能电池', '折叠小刀', '火力风暴潮'}
# ✕ 按钮中心:在 ✓ 左侧 114 像素、同一行(三张实机帧实测)
_CANCEL_CENTER_DX: int = 114

# 干净帧与别类帧:不出候选。前三张是备战画面同一目录下两颗按钮分数最高的非浮层帧
# (全样本扫描实测,至多 0.39),末张是商店面板展开、装备栏右列可见的帧。
_ABSENT_FRAMES: list[tuple[str, str]] = [
    (_PREP, 'deployed_2star'),
    (_PREP, 'equipped_front1_feixiao_synth'),
    (_PREP, '后排9槽-cap7lv4-b'),
    ('货币战争-备战-开商店', 'shop_open_preview_star'),
]


def _screens_dir() -> Path:
    """中央归档库 ``screens/``(与 ``test/conftest.py`` 的 ``load_screen`` 同一个定位)。"""
    return Path(test_conftest.__file__).resolve().parent.parent / 'screens'


@cache
def _frame(screen_dir: str, name: str) -> object:
    """读一张样本帧(RGB,1080p);缺帧跳过而不是报错。"""
    path = _screens_dir() / screen_dir / f'{name}.webp'
    if not path.is_file():
        pytest.skip(f'存档截图缺失:{path}')
    return cv2_utils.read_image(str(path))


@cache
def _ok_template() -> TemplateInfo:
    return TemplateInfo(overlay_mod.OK_TEMPLATE_DIR, overlay_mod.OK_TEMPLATE_DIR)


@cache
def _cancel_template() -> TemplateInfo:
    return TemplateInfo(overlay_mod.CANCEL_TEMPLATE_DIR, overlay_mod.CANCEL_TEMPLATE_DIR)


@cache
def _equip_grays() -> dict:
    """装备图标灰度模板库(入库的那一份),全文件只加载一次。"""
    return load_equip_tm_grays(get_project_root() / 'assets' / 'template' / 'currency_war' / 'equip_plaza')


def _read(frame: object, equip_grays: dict | None = None,
          search_rect: Rect | None = None) -> overlay_mod.SynthesisOverlayResult:
    """对一帧跑一次完整识别(贵计算,调用方一次读取、逐条断言)。"""
    return overlay_mod.read_synthesis_overlay(
        frame, _ok_template(), _cancel_template(),
        _SEARCH_RECT if search_rect is None else search_rect,
        _equip_grays() if equip_grays is None else equip_grays)


def _paste_buttons(frame: object, ok_xy: tuple[int, int],
                   cancel_xy: tuple[int, int] | None = None) -> object:
    """在内存里把按钮模板贴到帧上的指定左上角(只贴掩码内的像素),返回新帧。"""
    out = frame.copy()
    jobs = [(_ok_template(), ok_xy)]
    if cancel_xy is not None:
        jobs.append((_cancel_template(), cancel_xy))
    for template, (x, y) in jobs:
        keep = template.mask > 0
        region = out[y:y + template.raw.shape[0], x:x + template.raw.shape[1]]
        region[keep] = template.raw[keep]
    return out


def test_three_tiers_present_with_known_answers() -> None:
    """三档浮层帧:各恰一对、点击坐标在本档按钮内、框内装备格读数 = 已知答案。"""
    assert set(_equip_grays()) >= _GATED_TEMPLATE_NAMES
    for screen_dir, name, (x1, y1, x2, y2), want_in1, want_in2, want_product in _KNOWN_ANSWERS:
        result = _read(_frame(screen_dir, name))
        assert result.state == overlay_mod.STATE_PRESENT, (name, result.candidates_detail())
        # 恰一对 = 两颗按钮各只剩一个候选峰(同钮平台期已合并)
        assert (len(result.ok_candidates), len(result.cancel_candidates), len(result.pairs)) == (1, 1, 1), (
            name, result.candidates_detail())
        reading = result.reading
        ok_x, ok_y = reading['ok_xy']
        assert x1 <= ok_x <= x2 and y1 <= ok_y <= y2, (name, reading['ok_xy'])
        assert reading['cancel_xy'] == (ok_x - _CANCEL_CENTER_DX, ok_y)
        inputs, product = reading['inputs'], reading['product']
        assert [set(slot) for slot in inputs] == [_SLOT_KEYS, _SLOT_KEYS] and set(product) == _SLOT_KEYS
        assert [slot['name'] for slot in inputs] == [want_in1, want_in2], name
        if want_product is _NOT_GATED:
            continue
        assert product['name'] == want_product, name


def test_last_row_frame_present_and_rect_only_filters_peaks() -> None:
    """最末一行的合成帧在场(匹配范围向下外扩);峰的左上角落在矩形下沿以外的不算候选。"""
    last_row = _read(_frame(_PREP, 'synthesis_overlay_last_row_synth'))
    assert last_row.state == overlay_mod.STATE_PRESENT, last_row.candidates_detail()
    assert last_row.reading['ok_xy'] == (1821, 711)

    # 中档实机帧的 ✓ 左上角纵坐标 = 374:矩形下沿 374 时峰在矩形外,375 时在矩形内;
    # 两种矩形的匹配范围都完整盖住按钮(下沿 = 矩形下沿 + 模板高)
    mid = _frame(_OVERLAY_DIR, '合成确认浮层')
    outside = _read(mid, search_rect=Rect(1620, 90, 1918, 374))
    assert outside.state == overlay_mod.STATE_ABSENT, outside.candidates_detail()
    inside = _read(mid, search_rect=Rect(1620, 90, 1918, 375))
    assert inside.state == overlay_mod.STATE_PRESENT and inside.reading['ok_xy'] == (1821, 402)


@pytest.mark.parametrize('screen_dir,name', _ABSENT_FRAMES, ids=[n for _, n in _ABSENT_FRAMES])
def test_clean_and_other_frames_have_no_candidate(screen_dir: str, name: str) -> None:
    """干净帧与别类帧:不在场,两颗按钮都没有候选。"""
    result = _read(_frame(screen_dir, name))
    assert result.state == overlay_mod.STATE_ABSENT, result.candidates_detail()
    assert result.ok_candidates == () and result.cancel_candidates == () and result.reading is None


def test_non_finite_scores_are_dropped() -> None:
    """带掩码匹配在近纯色区会得到正无穷,那样的点不是命中。大厅帧的装备栏对应区域上
    两颗按钮模板各有几个无穷大分数点(全部样本帧里出现无穷大分数的只有大厅两张):
    丢弃后不在场、两颗按钮都没有候选。"""
    result = _read(_frame('货币战争-大厅', 'lobby'))
    assert result.state == overlay_mod.STATE_ABSENT, result.candidates_detail()
    assert result.ok_candidates == () and result.cancel_candidates == ()


def test_single_button_is_unpaired_and_two_pairs_are_ambiguous() -> None:
    """只有一颗按钮的候选 = 有候选但配不成对;两对 = 歧义。两种都没有读数结构。"""
    clean = _frame(_PREP, 'deployed_2star')
    only_ok = _read(_paste_buttons(clean, (1772, 374)))
    assert only_ok.state == overlay_mod.STATE_UNPAIRED, only_ok.candidates_detail()
    assert len(only_ok.ok_candidates) == 1 and only_ok.cancel_candidates == ()
    assert only_ok.pairs == () and only_ok.reading is None

    both_rows = _paste_buttons(_paste_buttons(clean, (1772, 297), (1657, 297)), (1772, 374), (1657, 374))
    ambiguous = _read(both_rows)
    assert ambiguous.state == overlay_mod.STATE_AMBIGUOUS, ambiguous.candidates_detail()
    assert len(ambiguous.pairs) == 2 and ambiguous.reading is None
    # 失败文案用的候选明细带上每一对的位置
    assert '(1657,297)' in ambiguous.candidates_detail() and '(1772,374)' in ambiguous.candidates_detail()


@pytest.mark.parametrize('missing', ['ok_template', 'cancel_template', 'search_rect'])
def test_missing_inputs_raise_instead_of_absent(missing: str) -> None:
    """按钮模板或搜索矩形取不到时抛异常,不判「不在场」。"""
    frame = _frame(_PREP, 'rail_badge_absent_r2')
    args = {'ok_template': _ok_template(), 'cancel_template': _cancel_template(),
            'search_rect': _SEARCH_RECT, 'equip_grays': _equip_grays()}
    args[missing] = None
    with pytest.raises(overlay_mod.SynthesisOverlayInputError):
        overlay_mod.read_synthesis_overlay(frame, **args)


def test_equip_library_missing_still_reads_overlay(
        caplog: pytest.LogCaptureFixture) -> None:
    """装备图标模板库缺席:浮层照常定位(配对定位不依赖这个库),三槽未识别、分数 0,
    记一条警告;浮层不在场的帧不记(否则每张干净帧都刷一条)。"""
    present = _frame(_OVERLAY_DIR, '合成确认浮层')
    with caplog.at_level(logging.WARNING, logger='OneDragon'):
        result = _read(present, equip_grays={})
    assert result.state == overlay_mod.STATE_PRESENT and result.reading['ok_xy'] == (1821, 402)
    for slot in (*result.reading['inputs'], result.reading['product']):
        assert slot['name'] is None and slot['conf'] == 0.0
    assert len([r for r in caplog.records
                if r.levelno >= logging.WARNING and '装备图标模板库缺席' in r.getMessage()]) == 1

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger='OneDragon'):
        absent = _read(_frame(_PREP, 'deployed_2star'), equip_grays={})
    assert absent.state == overlay_mod.STATE_ABSENT
    assert '装备图标模板库缺席' not in caplog.text


def test_overlay_frames_match_prep_family_screens(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """三张浮层帧的全集识别屏名 ∈ {货币战争-备战, 货币战争-备战-选择主角}:不被认成
    角色详情等别的备战系画面(浮层在场的帧照样认得出是备战)。"""
    monkeypatch.setattr(test_context.screen_loader, 'current_screen_name', None)
    monkeypatch.setattr(test_context.screen_loader, 'last_screen_name', None)
    for screen_dir, name, *_ in _KNOWN_ANSWERS:
        matched = screen_utils.get_match_screen_name(test_context, _frame(screen_dir, name))
        assert matched in _PREP_FAMILY_SCREENS, (name, matched)
