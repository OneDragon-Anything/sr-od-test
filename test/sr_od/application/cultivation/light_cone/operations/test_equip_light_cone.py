"""EquipLightConeOp(替换光锥)定位算法与节点流程测试。

测试层级声明:实机 fixture 直测 recognize 全量清单(fixture = 实机替换界面
截图,目标卡位置已知;识别住本域 light_cone_list_recognizer 自含实现,
遗器侧在 relic_list_recognizer 各持一份,两域零共用);节点流程为打桩
流程测试(画面判定 / 查找区域 / OCR 读名打桩)——
替换交互链本体(点替换→选卡→点替换→自动回 TAB)由生产实机摸底覆盖,
不在此重复。

锁的内容(出处 src/sr_od/application/cultivation/light_cone/operations/equip_light_cone.py +
本域 light_cone_list_recognizer.py):
- 全量清单识别:实机 fixture 上目标件被 masked TM 判出且 cell 落位正确
  (缺件 = 滚动扫屏兜底的前提,清单纯全才可能漏滚);
- 滚顶:固定次数快速大范围拖拽(手指上滑、短 duration),不做识别判顶
  直接成功;
- 扫描循环:当前屏未命中 → 拖动重扫(有界,方向 = 手指上滑);命中即点击
  并停;拖满上限仍未命中显式失败;
- 不抢语义:目标件全被占用 → 不点击,预算耗尽显式失败(ALL_OWNED);
  allow_take_over=True 时同数据命中点击;
- 画面判定:入口用画面级判定限定替换列表画面;列表中途退出显式失败
  (重新打开后再调),不盲识别盲拖动;
- 全链:入口已装备幂等成功 / 替换完成状态与读区核对。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.light_cone.light_cone_list_recognizer import (
    LightConeReplaceRecognizer,
)
from sr_od.application.cultivation.light_cone.operations import (
    equip_light_cone as equip_module,
)
from sr_od.application.cultivation.light_cone.operations.equip_light_cone import (
    EquipLightConeOp,
)

_FIXTURE_DIR = Path(__file__).parent / 'equip_light_cone'
_LIST_AREA: Rect = Rect(95, 130, 1420, 960)


def _recognizer_ctx(test_context: SrTestContext) -> SimpleNamespace:
    """recognize 直测的 mock ctx(列表区 + 真实例 OCR / 叠影模板库)。"""
    return SimpleNamespace(
        screen_loader=SimpleNamespace(
            get_area=lambda screen_name, area_name: SimpleNamespace(rect=_LIST_AREA)),
        template_loader=TemplateLoader(),
        ocr_service=test_context.ocr_service)


def test_locate_on_fixtures(test_context: SrTestContext) -> None:
    """实机 fixture 全量识别:目标件 行于流逝的岸 分别在首行首列/次列,
    masked TM 判出名且 cell 落位正确(列中心吸附固定列先验)。"""
    for fname, want_cell in [('replace_target_row0_col0.webp', (97, 197, 236, 352)),
                             ('replace_target_row0_col1.webp', (236, 197, 375, 352))]:
        img = cv2_utils.read_image(str(_FIXTURE_DIR / fname))
        assert img is not None
        out = LightConeReplaceRecognizer().recognize(
            _recognizer_ctx(test_context), img, None)
        assert out is not None, fname
        hits = [it for it in out['items'] if it['cone'] == '行于流逝的岸']
        assert hits, (f'{fname} 应命中目标件,实际前 6 项: '
                      f'{[(it["cone"], tuple(it["cell"])) for it in out["items"][:6]]}')
        assert tuple(hits[0]['cell']) == want_cell, \
            f'{fname} 目标 cell 应为 {want_cell},实际 {tuple(hits[0]["cell"])}'
        assert hits[0]['path_cn'] == '虚无'
        assert hits[0]['level'] == 80


def _target_item() -> dict:
    """目标光锥的识别件结构(字段子集,够 op 过滤与点击即可,cell 中心 ≈ (305,274))。"""
    return {'cell': [236, 197, 375, 352], 'cone': '行于流逝的岸',
            'rank': 1, 'level': 80, 'owner': None, 'path_cn': '同谐'}


class _NoWindowEquipLightCone(EquipLightConeOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext, cone_name: str,
                 allow_take_over: bool = False) -> None:
        EquipLightConeOp.__init__(self, ctx, cone_name=cone_name,
                                  allow_take_over=allow_take_over)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_reset_to_top_fast_drags(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """滚顶:固定次数的快速大范围拖拽(方向 = 手指上滑、短 duration),
    不做识别判顶,直接 AT_TOP。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')
    drags: list = []

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '光锥-替换')
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda end, start=None, duration=0.5: drags.append((start, end, duration)))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.reset_to_top()
    finally:
        reset_running_state(op.ctx, op)
    assert result.status == 'AT_TOP', '滚顶节点应直接成功(无识别判顶)'
    assert len(drags) == equip_module._RESET_TOP_DRAGS, \
        f'应恰好拖拽 {equip_module._RESET_TOP_DRAGS} 次,实际 {len(drags)}'
    for start, end, duration in drags:
        assert end.y > start.y, f'回卷拖拽应为手指下滑(end.y={end.y} > start.y={start.y})'
        assert duration == equip_module._TOP_DRAG_DURATION, '回卷应为短 duration 快速甩动'


def test_find_and_select_scans_then_clicks(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描循环:首屏未命中 → 滚动重扫 → 次屏命中点击;扫描预算耗尽 →
    立即失败不再拖动。(滚顶已前移至 reset_to_top 节点,本节点纯扫描)"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')
    state = {'scans': 0}
    drags: list = []
    clicks: list = []

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '光锥-替换')

    def _fake_recognize(self, ctx, image, screen_info):
        state['scans'] += 1
        if state['scans'] >= 2:  # 首屏未命中,滚动后命中
            return {'items': [_target_item()]}
        return {'items': []}

    monkeypatch.setattr(equip_module.LightConeReplaceRecognizer, 'recognize', _fake_recognize)
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda end, start=None, duration=0.5: drags.append((start, end)))
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda pos, **kwargs: clicks.append(pos))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            op.find_and_select()  # 首屏未命中 → 滚动
            op.find_and_select()  # 次屏命中 → 点击
    finally:
        reset_running_state(op.ctx, op)

    assert len(drags) == 1, f'首屏未命中滚动 1 次,实际 {len(drags)}'
    assert len(clicks) == 1, '命中卡应点击一次'
    start, end = drags[0]
    assert end.y < start.y, f'扫描滚动应为手指上滑向下翻页(end.y={end.y} < start.y={start.y})'

    # 扫描预算:预算耗尽(_scan_screens 跨轮累积)→ 立即失败,不再拖动
    op._scan_screens = 12
    drags.clear()
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)
    assert not result.is_success, '扫描预算耗尽应显式失败'
    assert len(drags) == 0, '预算耗尽后不应再拖动'


def test_find_and_select_fails_when_list_exited(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """画面退出显式失败:扫描轮画面判定非替换界面 → round_fail(重新打开
    后再调),不再盲识别盲拖动。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')
    drags: list = []
    clicks: list = []

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '角色-光锥'  # 列表中途被关,退回 TAB

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen', _fake_check_screen)
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda *args, **kwargs: drags.append(1))
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda pos, **kwargs: clicks.append(pos))

    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)

    assert not result.is_success, '列表退出应显式失败'
    assert '重新打开' in (result.status or ''), '失败信息应指向重新打开列表'
    assert len(drags) == 0, '退出后不应再拖动'
    assert len(clicks) == 0, '退出后不应再点击'


def test_no_take_over_and_allow_take_over(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """不抢语义:目标件全被占用 → 不点击,预算耗尽后 ALL_OWNED 显式失败;
    allow_take_over=True 时同数据命中并点击。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '光锥-替换')

    def _fake_recognize(self, ctx, image, screen_info):
        # 两件同名副本均被占用
        return {'items': [
            {'cell': [236, 197, 375, 352], 'cone': '行于流逝的岸',
             'rank': 1, 'level': 80, 'owner': '角色甲', 'path_cn': '同谐'},
            {'cell': [375, 197, 514, 352], 'cone': '行于流逝的岸',
             'rank': 1, 'level': 80, 'owner': '角色乙', 'path_cn': '同谐'},
        ]}

    monkeypatch.setattr(equip_module.LightConeReplaceRecognizer, 'recognize', _fake_recognize)
    monkeypatch.setattr(test_context.controller, 'drag_to', lambda *args, **kwargs: None)
    clicks: list = []
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda pos, **kwargs: clicks.append(pos))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    # 不抢(默认):12 屏滚动后 ALL_OWNED 失败,全程零点击
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.find_and_select()
            rounds = 0
            while not result.is_fail and rounds < 25:
                result = op.find_and_select()
                rounds += 1
    finally:
        reset_running_state(op.ctx, op)
    assert result.is_fail, '全占用且不抢应显式失败'
    assert '仅见已被装备' in (result.status or ''), '失败信息应说明仅见被占用件'
    assert len(clicks) == 0, '不抢语义不应点击任何卡'

    # 允许占用:首屏即命中点击
    op_take = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸',
                                      allow_take_over=True)
    enter_running_state(op_take.ctx)
    try:
        with fast_sleep(op_take):
            result = op_take.find_and_select()
            rounds = 0
            while len(clicks) == 0 and not result.is_fail and rounds < 10:
                result = op_take.find_and_select()
                rounds += 1
    finally:
        reset_running_state(op_take.ctx, op_take)
    assert len(clicks) == 1, 'allow_take_over=True 应命中并点击占用件'


def test_happy_flow_and_already_equipped(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """列表起点全链:入口(已装备幂等 / 未装备走全链)→ 定位选卡 → 验证选中
    → 确认替换(画面判定确认回 TAB)→ 结果核对 LIGHT_CONE_EQUIPPED。
    起点不在列表画面 → 显式失败提示先调 OpenLightConeReplaceOp。"""
    from one_dragon.base.screen.screen_utils import FindAreaResultEnum

    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')

    scene = {'screen': 'replace'}  # 当前画面场景:tab(TAB 页) / replace(替换界面)

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '光锥-替换' if scene['screen'] == 'replace' else '角色-光锥'

    read_state = {
        'cone_cur_name': None,  # 替换列表左栏当前装备名(None=未装备目标)
        'cone_tab_name': None,  # TAB 读区光锥名(None=不匹配目标)
    }

    def _fake_click(pos, **kwargs):
        y = pos.y if hasattr(pos, 'y') else pos.center.y  # 兼容 Point / Rect 两种点击入参
        if y > 900 and scene['screen'] == 'replace':  # 底部「替换」按钮:回 TAB 且装备生效
            scene['screen'] = 'tab'
            read_state['cone_tab_name'] = '行于流逝的岸'
            read_state['cone_cur_name'] = '行于流逝的岸'

    def _fake_read_name(self, screen_name, area_name):
        if screen_name == '角色-光锥':
            return read_state['cone_tab_name']
        if area_name == '读区-当前光锥名':
            return read_state['cone_cur_name']
        return '行於流逝的岸'  # 选中名读区(OCR 形近变体)

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen', _fake_check_screen)
    monkeypatch.setattr(equip_module.screen_utils, 'find_area',
                        lambda *args, **kwargs: FindAreaResultEnum.TRUE)
    monkeypatch.setattr(EquipLightConeOp, '_read_name', _fake_read_name)
    monkeypatch.setattr(equip_module.LightConeReplaceRecognizer, 'recognize',
                        lambda self, ctx, image, screen_info: {'items': [_target_item()]})
    monkeypatch.setattr(test_context.controller, 'click', _fake_click)
    monkeypatch.setattr(test_context.controller, 'drag_to', lambda *args, **kwargs: None)
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    # 入口不在列表画面 → 显式失败,信息指向 OpenLightConeReplaceOp
    scene['screen'] = 'tab'
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.check_entry()
    finally:
        reset_running_state(op.ctx, op)
    assert not result.is_success, 'TAB 页起点应显式失败'
    assert 'OpenLightConeReplaceOp' in (result.status or '')

    # 入口:当前角色已装备目标 → 幂等成功
    scene['screen'] = 'replace'
    read_state['cone_cur_name'] = '行于流逝的岸'
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.check_entry()
    finally:
        reset_running_state(op.ctx, op)
    assert result.status == 'ALREADY_EQUIPPED'

    # 未装备 → 全链成功
    read_state['cone_cur_name'] = None
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(op.ctx, op)
    assert result.success, f'替换全链应成功结束,status={result.status}'
    assert result.status == 'LIGHT_CONE_EQUIPPED'
