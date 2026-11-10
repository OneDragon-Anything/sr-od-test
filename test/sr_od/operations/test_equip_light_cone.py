"""EquipLightConeOp(替换光锥)定位算法与节点流程测试。

测试层级声明:SIFT 落格投票定位为纯函数直测(fixture = 实机替换界面截图,
目标卡位置已知;定位算法住 grid_template_locate 公共模块,遗器 op 同源
复用);节点流程为打桩流程测试(画面判定 / 查找区域 / OCR 读名打桩)——
替换交互链本体(点替换→选卡→点替换→自动回 TAB)由生产实机摸底覆盖,
不在此重复。

锁的内容(出处 src/sr_od/operations/equip_light_cone.py +
grid_template_locate.py):
- 模板加载:图标透明底合成白底;缺失路径返回 None;
- 落格投票定位:目标卡得票显著(实机 15:2),定位中心吸附列中心;
  目标不在当前屏(涂掉目标特征)返回 None;
- 扫描循环:选件前逐轮滚回列表顶(每轮一次拖拽,轮间画面判定兜底);
  当前屏未命中 → 拖动重扫(有界);命中即点击并停;拖满上限仍未命中
  显式失败;
- 画面判定:入口与转移确认用画面级判定,禁单区域命中当画面判定
  (两屏标题「角色光锥 / 光锥替换」同位形近,单区域可互判误命中);
- 全链:入口已装备幂等成功 / 替换完成状态与读区核对。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.operations import equip_light_cone as equip_module
from sr_od.operations.equip_light_cone import EquipLightConeOp
from sr_od.operations.grid_template_locate import (
    load_template_gray,
    locate_cells_by_votes,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_FIXTURE_DIR = Path(__file__).parent / 'equip_light_cone'
_LIST_AREA: Rect = Rect(95, 130, 1420, 960)
_TEMPLATE_REL: str = 'assets/game_data/light_cone_icons/行于流逝的岸.webp'  # 游戏内名称键
_CONE_COL_CENTERS: list[float] = equip_module._cone_col_centers(_LIST_AREA)


def _target_item() -> dict:
    """目标光锥的识别件结构(字段子集,够 op 过滤与点击即可,cell 中心 ≈ (305,274))。"""
    return {'cell': [236, 197, 375, 352], 'cone': '行于流逝的岸',
            'rank': 1, 'level': 80, 'owner': None, 'path_cn': '同谐'}


class _NoWindowEquipLightCone(EquipLightConeOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext, cone_name: str) -> None:
        EquipLightConeOp.__init__(self, ctx, cone_name=cone_name)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_load_template_gray() -> None:
    """模板加载:图标存在出灰度图;缺失路径 None(不抛异常,调用方判停)。"""
    template = load_template_gray(_TEMPLATE_REL)
    assert template is not None
    assert template.ndim == 2  # 灰度单通道

    assert load_template_gray('assets/game_data/light_cone_icons/不存在的光锥名.webp') is None


def test_locate_on_fixtures() -> None:
    """实机 fixture 定位(全量清单):目标卡分别在第一行第一列/第二列,列中心吸附正确。"""
    template = load_template_gray(_TEMPLATE_REL)
    assert template is not None

    screen_a = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col0.webp'))
    cells = locate_cells_by_votes(cv2.cvtColor(screen_a, cv2.COLOR_RGB2GRAY), template,
                                  _LIST_AREA, _CONE_COL_CENTERS)
    assert cells, 'fixture A 应定位到第一行第一列'
    top_a = cells[0][0]
    assert abs(top_a.x - 167) <= 10, f'最高票候选应吸附首列(~167),实际 {top_a.x}'
    assert 195 <= top_a.y <= 360, f'应落在第一行带,实际 {top_a.y}'

    screen_b = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col1.webp'))
    cells_b = locate_cells_by_votes(cv2.cvtColor(screen_b, cv2.COLOR_RGB2GRAY), template,
                                    _LIST_AREA, _CONE_COL_CENTERS)
    assert cells_b, 'fixture B 应定位到第一行第二列'
    top_b = cells_b[0][0]
    assert abs(top_b.x - 306) <= 10, f'最高票候选应吸附第二列(~306),实际 {top_b.x}'


def test_locate_rejects_when_target_absent() -> None:
    """负例:目标卡特征被涂掉(移出当前屏的模拟)→ 返回空清单不误点。"""
    template = load_template_gray(_TEMPLATE_REL)
    assert template is not None

    screen = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col0.webp'))
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    # 涂白第一行前两列(定位结果所在格)与整行特征——模拟目标不在该屏
    gray[130:520, 95:720] = 255
    assert locate_cells_by_votes(gray, template, _LIST_AREA, _CONE_COL_CENTERS) == []


def test_find_and_select_scans_then_clicks(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描循环:滚顶 4 轮逐次拖拽 → 前两屏未命中滚动重扫 → 第三屏命中点击;
    扫描预算耗尽 → 立即失败不再拖动。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')
    state = {'scans': 0}
    drags: list = []
    clicks: list = []

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen',
                        lambda self, screen=None, screen_name_list=None,
                        crop_first=False: '光锥-替换')

    def _fake_recognize(self, ctx, image, screen_info):
        state['scans'] += 1
        if state['scans'] >= 3:  # 前两屏未命中,第三屏(滚动后)命中
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
            # 滚顶 4 轮(各 1 拖拽)+ 未命中 2 轮(各 1 滚动拖拽)+ 第 3 扫描轮命中点击
            for _ in range(7):
                op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)

    assert len(drags) == 6, f'滚顶 4 次 + 未命中滚动 2 次,实际 {len(drags)}'
    assert len(clicks) == 1, '命中卡应点击一次'

    # 扫描预算:预算耗尽(_scan_screens 跨轮累积)→ 立即失败,不再拖动
    op._scan_screens = 12
    op._reset_drags_left = 0
    drags.clear()
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)
    assert not result.is_success, '扫描预算耗尽应显式失败'
    assert len(drags) == 0, '预算耗尽后不应再拖动'


def test_find_and_select_reopens_on_screen_exit(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """画面退出自愈:扫描轮画面判定非替换界面 → REOPEN(重置扫描状态),
    不再盲识别盲拖动。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '角色-光锥'  # 列表中途被关,退回 TAB

    monkeypatch.setattr(EquipLightConeOp, 'check_and_update_current_screen', _fake_check_screen)

    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)

    assert result.status == 'REOPEN'
    assert op._scan_screens == 0, 'REOPEN 应重置扫描预算'
    assert op._reset_drags_left == 4, 'REOPEN 应重置滚顶拖拽预算'


def test_happy_flow_and_already_equipped(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全链:入口(已装备幂等 / 未装备走全链)→ 打开替换(画面判定确认转移)→
    定位选卡 → 验证选中 → 确认替换(画面判定确认回 TAB)→ 结果核对
    LIGHT_CONE_EQUIPPED。"""
    from one_dragon.base.screen.screen_utils import FindAreaResultEnum

    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')

    scene = {'screen': 'tab'}  # 当前画面场景:tab(TAB 页) / replace(替换界面)

    def _fake_check_screen(self, screen=None, screen_name_list=None, crop_first=False):
        return '光锥-替换' if scene['screen'] == 'replace' else '角色-光锥'

    read_state = {'cone_tab_name': None}  # TAB 读区光锥名(None=不匹配目标)

    def _fake_click(pos, **kwargs):
        y = pos.y if hasattr(pos, 'y') else pos.center.y  # 兼容 Point / Rect 两种点击入参
        if y > 900:  # 底部「替换」按钮(打开/确认);候选卡点击 y≈274 不触发
            if scene['screen'] == 'replace':  # 确认替换 → 回 TAB 且装备生效
                scene['screen'] = 'tab'
                read_state['cone_tab_name'] = '行于流逝的岸'
            else:  # 打开替换界面
                scene['screen'] = 'replace'

    def _fake_read_name(self, screen_name, area_name):
        if screen_name == '角色-光锥':
            return read_state['cone_tab_name']
        return '行於流逝的岸'  # 替换界面选中名(OCR 形近变体)

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

    # 入口:已装备 → 幂等成功
    read_state['cone_tab_name'] = '行于流逝的岸'
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.check_entry()
    finally:
        reset_running_state(op.ctx, op)
    assert result.status == 'ALREADY_EQUIPPED'

    # 未装备 → 全链成功
    read_state['cone_tab_name'] = None
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(op.ctx, op)
    assert result.success, f'替换全链应成功结束,status={result.status}'
    assert result.status == 'LIGHT_CONE_EQUIPPED'
