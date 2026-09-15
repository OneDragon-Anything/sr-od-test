"""screen_match 框架强化匹配测试。"""
from unittest.mock import MagicMock

import pytest

import one_dragon.base.screen.screen_match as _sm
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.screen_area import ScreenArea
from one_dragon.base.screen.screen_info import ScreenInfo
from one_dragon.base.screen.screen_match import (
    AreaMatchDetail,
    AreaType,
    UnmatchedReason,
    find_area_with_detail,
    find_screen_matches,
)

# (2026-09-03 攻击性排查:原 AreaMatchDetail/ScreenMatch 构造透传断言 ×3
#  删除——逐字段 assert 赋值 = dataclass 行为(纪律 18);字段契约由下方
#  find_area 行为测的断言面超集覆盖。)


def _text_area(text: str = '战斗') -> ScreenArea:
    return ScreenArea(area_name=f'按钮-{text}', pc_rect=Rect(300, 800, 500, 880),
                      text=text, lcs_percent=0.5)


def _template_area() -> ScreenArea:
    return ScreenArea(area_name='邮箱图标', pc_rect=Rect(1700, 40, 1760, 100),
                      template_id='mail', template_sub_dir='menu',
                      template_match_threshold=0.7)


def _plain_area() -> ScreenArea:
    return ScreenArea(area_name='点击区', pc_rect=Rect(0, 0, 100, 100))


@pytest.mark.parametrize('ocr_text,expect', [
    ('战斗', {'confidence': 0.95, 'rect': (300, 800, 200, 80)}),   # OCR 文本命中区内
    ('设置', None),                                                # 文本不匹配 → 未命中
], ids=['text-hit', 'text-miss'])
def test_find_area_text_by_ocr_result(ocr_text: str, expect: dict | None) -> None:
    """文本区命中/未命中参数化:OCR 结果落在区内且文本匹配 → 命中详情透传;不匹配 → None。"""
    ctx = MagicMock()
    ocr = MagicMock(data=ocr_text, confidence=0.95, x=300, y=800, w=200, h=80)
    ctx.ocr_service.get_ocr_result_list.return_value = [ocr]
    d = find_area_with_detail(ctx, MagicMock(), _text_area())
    if expect is None:
        assert d is None
        return
    assert d.area_type == AreaType.TEXT
    assert d.text == ocr_text
    assert d.confidence == expect['confidence']
    assert (d.x, d.y, d.width, d.height) == expect['rect']


@pytest.mark.parametrize('area_kind,expect', [
    ('template_hit', (1710, 60, 50, 60, 0.92)),   # 绝对坐标 = mrl.max + area.rect 偏移
    ('template_miss', None),                      # 模板未命中
    ('plain', None),                              # 纯定位区(无 text/template)不参与识别
], ids=['template-hit', 'template-miss', 'plain'])
def test_find_area_template_and_plain(area_kind: str, expect: tuple | None) -> None:
    """模板区命中/未命中、纯定位区参数化:模板命中返绝对坐标详情;未命中 / 纯定位返 None。"""
    ctx = MagicMock()
    if area_kind.startswith('template'):
        area = _template_area()
        mrl = MagicMock()
        mrl.max = (MagicMock(x=10, y=20, w=50, h=60, confidence=0.92)
                   if area_kind == 'template_hit' else None)
        ctx.tm.crop_and_match_template.return_value = mrl
    else:
        area = _plain_area()
    d = find_area_with_detail(ctx, MagicMock(), area)
    if expect is None:
        assert d is None
        return
    assert d.area_type == AreaType.TEMPLATE
    assert d.confidence == expect[4]
    assert (d.x, d.y) == expect[:2]
    assert (d.width, d.height) == expect[2:4]


def test_find_area_default_crop_first_false() -> None:
    """默认 crop_first=False(全图 OCR 缓存复用,与框架 find_* 系列默认一致)。"""
    ctx = MagicMock()
    ctx.ocr_service.get_ocr_result_list.return_value = []
    find_area_with_detail(ctx, MagicMock(), _text_area())
    _args, kwargs = ctx.ocr_service.get_ocr_result_list.call_args
    assert kwargs.get('crop_first') is False


# --- find_screen_matches 测试(find_screen_matches 一次遍历分级匹配)---


def _screen_info(name: str, areas: list[ScreenArea]) -> ScreenInfo:
    """用 ScreenInfo 构造一个画面(area_list 来自入参)。"""
    data = {'screen_id': name, 'screen_name': name, 'app_id': '',
            'area_list': [a.to_dict() for a in areas]}
    return ScreenInfo(data)


def _id_mark_text_area(name: str, text: str) -> ScreenArea:
    a = ScreenArea(area_name=name, pc_rect=Rect(0, 0, 100, 50), text=text, lcs_percent=0.5)
    a.id_mark = True
    return a


def _make_loader(screens: list[ScreenInfo], current: str | None = None,
                 last: str | None = None) -> MagicMock:
    """构造 mock screen_loader。"""
    loader = MagicMock()
    loader.screen_info_list = screens
    loader.active_screen_info_list = screens
    loader.screen_info_map = {s.screen_name: s for s in screens}
    loader.active_screen_names = None   # backend 语境 scope 不激活
    loader.current_screen_name = current
    loader.last_screen_name = last
    return loader


def _patch_find(monkeypatch, hit_map: dict) -> None:
    """patch 模块级 find_area_with_detail:按 area_name 决定命中(走 text 分支语义)。

    必须用 monkeypatch.setattr(_sm, ...)patch 模块属性 —— find_screen_matches 内部以
    模块级引用调用 find_area_with_detail(见实现注),patch 模块属性才生效。
    """
    def fake_find(ctx, screen, area, crop_first=False):
        if area.area_name in hit_map and hit_map[area.area_name]:
            return AreaMatchDetail(area_name=area.area_name, area_type=AreaType.TEXT,
                                   x=0, y=0, width=10, height=10, text=area.text or '')
        return None
    monkeypatch.setattr(_sm, 'find_area_with_detail', fake_find)


def test_precise_early_stop_when_current_set(monkeypatch) -> None:
    """current 有值 + 该画面 id_mark 全中 → 精准早停返 1 个 is_precise=True。"""
    menu = _screen_info('菜单', [_id_mark_text_area('菜单标题', '菜单')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([menu], current='菜单')
    _patch_find(monkeypatch, {'菜单标题': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == '菜单'
    assert result[0].is_precise is True


def test_no_precise_returns_topn_by_hit_count(monkeypatch) -> None:
    """无 id_mark 全中 → 按命中数 top_n(is_precise=False)。"""
    a = _screen_info('画面A', [ScreenArea(area_name='a1', pc_rect=Rect(0, 0, 10, 10), text='x'),
                               ScreenArea(area_name='a2', pc_rect=Rect(0, 0, 10, 10), text='y')])
    b = _screen_info('画面B', [ScreenArea(area_name='b1', pc_rect=Rect(0, 0, 10, 10), text='z')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b])
    _patch_find(monkeypatch, {'a1': True, 'a2': True, 'b1': True})
    result = find_screen_matches(ctx, MagicMock(), top_n=5)
    assert len(result) == 2
    assert result[0].screen_name == '画面A'   # 命中 2 个,排前
    assert result[0].is_precise is False
    assert result[1].screen_name == '画面B'


def test_current_last_none_full_traversal(monkeypatch) -> None:
    """current/last 均 None → 直接全量遍历(无 BFS)。"""
    menu = _screen_info('菜单', [_id_mark_text_area('标题', '菜单')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([menu], current=None, last=None)
    _patch_find(monkeypatch, {'标题': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].is_precise is True


def test_bfs_traverses_goto_neighbors(monkeypatch) -> None:
    """BFS 从 current 沿 goto_list 扩散到邻接画面(图不连通时兜底全量覆盖)。"""
    a = _screen_info('A', [_id_mark_text_area('a_mark', 'a')])
    a_area = ScreenArea(area_name='a_goto', pc_rect=Rect(0, 0, 10, 10), text='goto')
    a_area.goto_list = ['B']
    a.area_list.append(a_area)
    b = _screen_info('B', [_id_mark_text_area('b_mark', 'b')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b], current='A')
    _patch_find(monkeypatch, {'b_mark': True})   # A 的 a_mark 未中 → 沿 goto 到 B
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == 'B'
    assert result[0].is_precise is True


def test_precise_early_stop_returns_first_processed(monkeypatch) -> None:
    """current 起的精准早停:两画面共享 id_mark 时,current 先处理即返(B 不会进 BFS)。

    (精准早停使「共享 id_mark tie-break」实际不可达 —— 首个精准即返,不存在多精准排序。)
    """
    a = _screen_info('A', [_id_mark_text_area('shared', 'x')])
    b = _screen_info('B', [_id_mark_text_area('shared', 'x')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b], current='A')
    _patch_find(monkeypatch, {'shared': True})
    result = find_screen_matches(ctx, MagicMock())
    assert len(result) == 1
    assert result[0].screen_name == 'A'   # current=A,BFS 从 A 起,A 首个精准即返


def test_scope_inactive_traverses_all_screens(monkeypatch) -> None:
    """scope 未激活(active_screen_names=None)→ 全量遍历所有画面,均进候选。

    spec ⑧:backend 语境 scope 恒不激活(loader.active_screen_names=None),
    find_screen_matches 应遍历 loader.active_screen_info_list 全部画面。设多画面、
    无 id_mark 命中(均进 top_n),断言全部进候选。
    """
    a = _screen_info('画面A', [ScreenArea(area_name='a1', pc_rect=Rect(0, 0, 10, 10), text='a')])
    b = _screen_info('画面B', [ScreenArea(area_name='b1', pc_rect=Rect(0, 0, 10, 10), text='b')])
    c = _screen_info('画面C', [ScreenArea(area_name='c1', pc_rect=Rect(0, 0, 10, 10), text='c')])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([a, b, c], current=None, last=None)
    assert ctx.screen_loader.active_screen_names is None   # scope 未激活
    _patch_find(monkeypatch, {'a1': True, 'b1': True, 'c1': True})

    result = find_screen_matches(ctx, MagicMock(), top_n=10)

    # 三画面均进候选(全量遍历,无 scope 过滤)
    names = {m.screen_name for m in result}
    assert names == {'画面A', '画面B', '画面C'}


# --- 未命中 area(unmatched_areas)测试 ---


def test_precise_unmatched_areas_categorized(monkeypatch) -> None:
    """精准命中 → unmatched_areas 按原因分类:纯定位区 NO_METHOD,未命中识别区 SUB_STATE。

    画面含:id_mark(命中→精准)、纯定位区(永不命中)、未命中文本子态区、命中模板区。
    unmatched 只含纯定位区 + 文本子态区;分类与字段(pc_rect / text)透传正确。
    """
    id_mark = _id_mark_text_area('标题', '菜单')                                  # id_mark,命中
    plain = ScreenArea(area_name='点击区', pc_rect=Rect(10, 20, 110, 120))        # 纯定位,无 text/template
    sub_text = ScreenArea(area_name='开关态', pc_rect=Rect(0, 0, 50, 50), text='已开启')   # 子态文本,未命中
    hit_tmpl = ScreenArea(area_name='图标', pc_rect=Rect(1700, 40, 1760, 100),
                          template_id='mail', template_sub_dir='menu')           # 模板,命中
    screen = _screen_info('菜单', [id_mark, plain, sub_text, hit_tmpl])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen], current='菜单')
    _patch_find(monkeypatch, {'标题': True, '图标': True})   # 仅 id_mark + 模板命中

    result = find_screen_matches(ctx, MagicMock())

    assert len(result) == 1 and result[0].is_precise is True
    by_name = {u.area_name: u for u in result[0].unmatched_areas}
    # 命中区(标题/图标)不出现在 unmatched
    assert '标题' not in by_name and '图标' not in by_name
    # 纯定位区 → NO_METHOD,pc_rect 透传
    assert by_name['点击区'].reason == UnmatchedReason.NO_METHOD
    assert by_name['点击区'].pc_rect == [10, 20, 110, 120]
    assert by_name['点击区'].text == '' and by_name['点击区'].template_id == ''
    # 子态文本区 → SUB_STATE,text 透传
    assert by_name['开关态'].reason == UnmatchedReason.SUB_STATE
    assert by_name['开关态'].text == '已开启'


def test_precise_unmatched_template_sub_state(monkeypatch) -> None:
    """精准命中 + 未命中模板子态区 → SUB_STATE,template_id 透传。"""
    id_mark = _id_mark_text_area('标题', '菜单')
    sub_tmpl = ScreenArea(area_name='面板展开态', pc_rect=Rect(1700, 40, 1760, 100),
                          template_id='panel_open', template_sub_dir='menu')
    screen = _screen_info('菜单', [id_mark, sub_tmpl])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen], current='菜单')
    _patch_find(monkeypatch, {'标题': True})   # 模板子态区未命中

    result = find_screen_matches(ctx, MagicMock())

    by_name = {u.area_name: u for u in result[0].unmatched_areas}
    assert by_name['面板展开态'].reason == UnmatchedReason.SUB_STATE
    assert by_name['面板展开态'].template_id == 'panel_open'


def test_precise_all_recognizable_hit_unmatched_empty(monkeypatch) -> None:
    """精准命中且所有识别区都命中(无纯定位区)→ unmatched_areas 为空。"""
    id_mark = _id_mark_text_area('标题', '菜单')
    hit_text = ScreenArea(area_name='副标题', pc_rect=Rect(0, 0, 100, 50), text='子')
    screen = _screen_info('菜单', [id_mark, hit_text])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen], current='菜单')
    _patch_find(monkeypatch, {'标题': True, '副标题': True})

    result = find_screen_matches(ctx, MagicMock())

    assert result[0].is_precise is True
    assert result[0].unmatched_areas == []


def test_fuzzy_match_unmatched_areas_empty(monkeypatch) -> None:
    """模糊候选(无 id_mark 全中)→ unmatched_areas 恒空(仅精准命中才计算)。"""
    a1 = ScreenArea(area_name='a1', pc_rect=Rect(0, 0, 10, 10), text='a')   # 无 id_mark → 永不精准
    plain = ScreenArea(area_name='点击区', pc_rect=Rect(10, 20, 110, 120))
    screen = _screen_info('画面A', [a1, plain])
    ctx = MagicMock()
    ctx.screen_loader = _make_loader([screen])
    _patch_find(monkeypatch, {'a1': True})   # a1 命中但无 id_mark → 模糊候选

    result = find_screen_matches(ctx, MagicMock())

    assert len(result) == 1 and result[0].is_precise is False
    assert result[0].unmatched_areas == []
