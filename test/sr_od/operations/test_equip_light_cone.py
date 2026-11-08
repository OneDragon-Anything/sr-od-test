"""EquipLightConeOp(替换光锥)定位算法与节点流程测试。

测试层级声明:SIFT 落格投票定位为纯函数直测(fixture = 实机替换界面截图,
目标卡位置已知);节点流程为打桩流程测试(round_by_* / OCR 读名打桩)——
替换交互链本体(点替换→选卡→点替换→自动回 TAB)由生产实机摸底覆盖,
不在此重复。

锁的内容(出处 src/sr_od/operations/equip_light_cone.py):
- 模板加载:解包图标透明底合成白底;表外光锥名返回 None;
- 落格投票定位:目标卡得票显著(实机 15:2),定位中心吸附列中心;
  目标不在当前屏(涂掉目标特征)返回 None;
- 扫描循环:当前屏未命中 → 拖动重扫(有界);命中即点击并停;
  拖满上限仍未命中显式失败;
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
from sr_od.operations.equip_light_cone import (
    EquipLightConeOp,
    _load_template_gray,
    _locate_cone_cell,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_FIXTURE_DIR = Path(__file__).parent / 'equip_light_cone'
_LIST_AREA: Rect = Rect(95, 130, 1420, 960)


class _NoWindowEquipLightCone(EquipLightConeOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext, cone_name: str) -> None:
        EquipLightConeOp.__init__(self, ctx, cone_name=cone_name)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_load_template_gray() -> None:
    """模板加载:表内光锥出灰度图;表外名字 None(不抛异常,调用方判停)。"""
    template = _load_template_gray('行于流逝的岸')
    assert template is not None
    assert template.ndim == 2  # 灰度单通道

    assert _load_template_gray('不存在的光锥名字') is None


def test_locate_cone_cell_on_fixtures() -> None:
    """实机 fixture 定位:目标卡分别在第一行第一列/第二列,列中心吸附正确。"""
    template = _load_template_gray('行于流逝的岸')
    assert template is not None

    screen_a = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col0.webp'))
    cell = _locate_cone_cell(cv2.cvtColor(screen_a, cv2.COLOR_RGB2GRAY), template, _LIST_AREA)
    assert cell is not None, 'fixture A 应定位到第一行第一列'
    assert abs(cell.x - 167) <= 10, f'列中心应吸附首列(~167),实际 {cell.x}'
    assert 195 <= cell.y <= 360, f'应落在第一行带,实际 {cell.y}'

    screen_b = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col1.webp'))
    cell_b = _locate_cone_cell(cv2.cvtColor(screen_b, cv2.COLOR_RGB2GRAY), template, _LIST_AREA)
    assert cell_b is not None, 'fixture B 应定位到第一行第二列'
    assert abs(cell_b.x - 306) <= 10, f'列中心应吸附第二列(~306),实际 {cell_b.x}'


def test_locate_cone_cell_rejects_when_target_absent() -> None:
    """负例:目标卡特征被涂掉(移出当前屏的模拟)→ 返回 None 不误点。"""
    template = _load_template_gray('行于流逝的岸')
    assert template is not None

    screen = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_target_row0_col0.webp'))
    gray = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    # 涂白第一行前两列(定位结果所在格)与整行特征——模拟目标不在该屏
    gray[130:520, 95:720] = 255
    assert _locate_cone_cell(gray, template, _LIST_AREA) is None


def test_find_and_select_scans_then_clicks(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """扫描循环:前两屏未命中 → 拖动 2 次后第三屏命中并点击;
    始终未命中 → 拖满上限后显式失败。"""
    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')
    state = {'scans': 0}
    drags: list = []
    clicks: list = []

    def _fake_locate(screen_gray, template_gray, list_rect):
        state['scans'] += 1
        if state['scans'] >= 3:  # 前两屏未命中,第三屏(拖动后)命中
            from one_dragon.base.geometry.point import Point
            return Point(306, 270)
        return None

    monkeypatch.setattr(equip_module, '_locate_cone_cell', _fake_locate)
    monkeypatch.setattr(test_context.controller, 'drag_to',
                        lambda end, start=None, duration=0.5: drags.append((start, end)))
    monkeypatch.setattr(test_context.controller, 'click',
                        lambda pos, **kwargs: clicks.append(pos))
    monkeypatch.setattr(test_context.controller, 'screenshot',
                        lambda independent=False: (0.0, np.zeros((1080, 1920, 3), dtype=np.uint8)))

    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            # 模拟框架节点重试:前两轮未命中(拖动),第三轮命中(点击)
            for _ in range(3):
                op.find_and_select()
    finally:
        reset_running_state(op.ctx, op)

    assert len(drags) == 2, f'命中前应拖动 2 次,实际 {len(drags)}'
    assert len(clicks) == 1, '命中卡应点击一次'

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


def test_happy_flow_and_already_equipped(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全链:入口(已装备幂等 / 未装备走全链)→ 打开替换 → 定位选卡 →
    验证选中 → 确认替换 → 结果核对 LIGHT_CONE_EQUIPPED。"""
    from one_dragon.base.geometry.point import Point

    op = _NoWindowEquipLightCone(test_context, cone_name='行于流逝的岸')

    scene = {'screen': 'tab'}  # 当前画面场景:tab(TAB 页) / replace(替换界面)

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        if scene['screen'] == 'replace':
            if (s_name, a_name) in {('光锥-替换', '标题-光锥替换'), ('光锥-替换', '文本-命途相符组头')}:
                return self.round_success(status=a_name)
            return self.round_wait(status=f'未找到 {a_name}')
        # tab 场景:仅 TAB 标题命中
        if (s_name, a_name) == ('角色-光锥', '标题-角色光锥'):
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_click(self, screen, s_name, a_name, *args, **kwargs):
        if a_name == '按钮-替换':  # TAB 点替换 → 进替换界面;替换界面点替换 → 回 TAB 且装备生效
            if scene['screen'] == 'replace':
                scene['screen'] = 'tab'
                read_state['cone_tab_name'] = '行于流逝的岸'  # 装备生效,TAB 读区更新
            else:
                scene['screen'] = 'replace'
        return self.round_success(status=a_name)

    read_state = {'cone_tab_name': None}  # TAB 读区光锥名(None=不匹配目标)

    def _fake_read_name(self, screen_name, area_name):
        if screen_name == '角色-光锥':
            return read_state['cone_tab_name']
        return '行於流逝的岸'  # 替换界面选中名(OCR 形近变体)

    monkeypatch.setattr(EquipLightConeOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(EquipLightConeOp, 'round_by_find_and_click_area', _fake_find_click)
    monkeypatch.setattr(EquipLightConeOp, '_read_name', _fake_read_name)
    monkeypatch.setattr(equip_module, '_locate_cone_cell',
                        lambda *args: Point(306, 270))
    monkeypatch.setattr(test_context.controller, 'click', lambda pos, **kwargs: None)
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
