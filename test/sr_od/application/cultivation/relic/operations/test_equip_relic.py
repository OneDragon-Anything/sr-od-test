"""EquipRelicOp(替换遗器)定位与流程测试(与 test_equip_light_cone 同构)。

测试层级声明:落格投票定位直测(fixture = 实机遗器替换界面截图,部位筛选
已锁头部,死水深潜的先驱头部件在第一行);算法住本域 relic_list_recognizer
自含实现(光锥 op 在其域各持一份,两域零共用;此处锁遗器 4 列网格几何与
部件图模板);节点流程为打桩流程测试(同光锥版,交互链本体生产实机摸底覆盖)。

锁的内容(出处 src/sr_od/application/cultivation/relic/operations/equip_relic.py):
- 件名反查:PIECE_TO_SET 表外件名构造期显式失败;表内解析出套装与部位;
- 4 列网格几何:列中心 = 列表区 x1 + 首列偏移 + 间距 × i(实测误差 ≤1px);
- fixture 定位:死水头部部件图命中第一行(两张同套装件,任一列均满足意图);
- 排序前置链(重进路径):开弹窗→关建议排序→选等级→确认逐节点执行;
  快速路径(复用已在正确部位的列表)不重复执行排序前置。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.relic.operations.equip_relic import (
    EquipRelicOp,
    _filter_candidates,
    _relic_col_centers,
)
from sr_od.application.cultivation.relic.relic_list_recognizer import (
    RelicReplaceRecognizer,
)

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'
_LIST_AREA: Rect = Rect(33, 195, 536, 960)


class _NoWindowEquipRelic(EquipRelicOp):
    """真实构造路径;测试无游戏窗口,跳过窗口前置链(同 test_farm_material)。"""

    def __init__(self, ctx: SrTestContext, piece_name: str) -> None:
        EquipRelicOp.__init__(self, ctx, piece_name=piece_name)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def test_construction_guard(test_context: SrTestContext) -> None:
    """件名守卫:表外件名构造期显式失败;表内解析出套装与部位。"""
    with pytest.raises(ValueError, match='不在常量表'):
        _NoWindowEquipRelic(test_context, piece_name='不存在的遗器件名')

    op = _NoWindowEquipRelic(test_context, piece_name='先驱的绝热围壳')
    assert op.set_name == '死水深潜的先驱'
    assert op.pos == 1  # 头部


def test_character_check_skipped_when_expected_none(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """expected_character=None(默认)= 跳过角色核对直接通过,连读区 OCR
    也不触发(锁 docstring 契约「None = 跳过核对」;缺守卫时 None 参与子串
    匹配会 TypeError,默认构造的 op 进入替换界面核对即崩)。"""
    op = _NoWindowEquipRelic(test_context, piece_name='先驱的绝热围壳')
    assert op.expected_character is None

    def _boom(*args, **kwargs) -> None:
        raise AssertionError('None 分支应整体跳过核对,不应触发 OCR 读区')

    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', _boom)
    assert op._check_character_on_replace_screen() is None


def test_grid_geometry() -> None:
    """4 列网格几何:列中心与实机卡位误差 ≤2px(99/222/345/468;列距 123px
    为亮度剖面实测列中心 99/224/346/469 的标定,旧 110px 标定累计偏 40px
    曾致右侧列角标裁窗全部落空)。"""
    centers = _relic_col_centers(_LIST_AREA)
    assert centers == pytest.approx([99, 222, 345, 468], abs=2)


def test_locate_on_fixture(test_context: SrTestContext) -> None:
    """实机 fixture 定位(全量清单):第一行两张死水头副本**每件各占一格**——
    同套装多副本全部识别,不丢件(选哪件由调用方基于清单决策)。
    定位实现说明:走 TM 识别输出的 cell 清单(replace 界面卡上无件名文本,
    副本格位由身份层整卡匹配给出)。"""
    img = cv2_utils.read_image(str(_FIXTURE_DIR / 'replace_head_row0.webp'))
    assert img is not None
    from types import SimpleNamespace
    areas = {'区域-遗器列表': _LIST_AREA}
    for i, nm in enumerate(['头部', '手部', '躯干', '腿部', '位面球', '连结绳']):
        areas[f'部位TAB-{nm}'] = Rect(110 + 63 * i, 122, 166 + 63 * i, 164)

    def get_area(screen_name: str, area_name: str):
        return SimpleNamespace(rect=areas[area_name])

    mock = SimpleNamespace(screen_loader=SimpleNamespace(get_area=get_area),
                           ocr_service=test_context.ocr_service)
    out = RelicReplaceRecognizer().recognize_for_pos(mock, img, 1)
    assert out is not None
    dead_water = [it for it in out['items'] if it['piece'] == '先驱的绝热围壳']
    assert len(dead_water) >= 2, f'两张同套装副本应各自入清单,实际 {len(dead_water)} 张'
    cols = sorted({it['cell'][0] for it in dead_water})
    assert len(cols) >= 2, f'两件副本应位于不同列,实际列 {cols}'


def test_filter_candidates_allow_take_over() -> None:
    """allow_take_over 候选语义(纯函数):False 只取无主件;True 被穿着件入选
    且无主件稳定排前;两模式都排除弹框取消过的格(死循环防线)。"""
    matched = [
        {'cell': [100, 200, 200, 300], 'owner': '停云'},
        {'cell': [250, 200, 350, 300], 'owner': None},
        {'cell': [400, 200, 500, 300], 'owner': '星期日'},
        {'cell': [100, 380, 200, 480], 'owner': None},
    ]
    rob = {(400, 200)}

    # False(默认不抢):只留无主件,被穿着件与弹框格全部出局
    kept = _filter_candidates(matched, allow_take_over=False, rob_cells=rob)
    assert [it['cell'] for it in kept] == [[250, 200, 350, 300], [100, 380, 200, 480]]

    # True(交换语义):被穿着件入选但无主件排前;弹框格仍出局
    kept = _filter_candidates(matched, allow_take_over=True, rob_cells=rob)
    assert [it['owner'] for it in kept] == [None, None, '停云']

    # True 且全部被弹框取消过:候选为空(不无限重试同格)
    assert _filter_candidates(matched, allow_take_over=True,
                              rob_cells={(100, 200), (250, 200), (400, 200), (100, 380)}) == []


#------------------- 排序前置链(fixture 剧本流程测试) -------------------#

_TAB_FRAME = ('角色-遗器', 'default')
_REPLACE_FRAME = ('遗器-替换', 'default')
_DIALOG_ON_FRAME = ('遗器-排序规则', '建议排序开')
_DIALOG_OFF_FRAME = ('遗器-排序规则', '建议排序关')
_DIALOG_LVL_FRAME = ('遗器-排序规则', '等级已选中')


class _WatchedEquipRelic(WatchdogOperationMixin, EquipRelicOp):
    """带看门狗的流程测试 op(轮次超限自动停,防剧本错配死循环)。

    piece_name 用「学者的银边视镜」对齐替换屏 fixture:该帧右侧详情读区即
    此件(读区 OCR 幂等命中 → ALREADY_EQUIPPED 截断,不进扫描节点);
    expected_character='黑塔' 对齐同帧命途名读区「智识/黑塔」(核对通过)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: SrTestContext) -> None:
        EquipRelicOp.__init__(self, ctx, piece_name='学者的银边视镜',
                              expected_character='黑塔')
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def _run_execute(test_context: SrTestContext, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _require_screens(test_context: SrTestContext, frames: list[tuple[str, str]]) -> None:
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')


def test_reenter_runs_sort_prepend_chain(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """重进路径(着装页起点)全链:点遗器位进列表 → 排序前置链逐节点执行
    (点排序按钮开弹窗 → 点开关关建议排序 → 点等级选基础排序 → 点确认)
    → 当前装备核对幂等成功。

    锁:重进后列表会被游戏重置回「建议排序」动态重排态,op 必须先转静态
    再扫描——四步点击任一缺失,动态重排下扫描即落空(实机根因)。弹窗
    「开关已关跳过」「等级已选中跳过」的防呆分支由帧3/帧4 的状态变化
    自然覆盖(点击生效推进后,重入走跳过分支)。"""
    frames = [_TAB_FRAME, _REPLACE_FRAME, _DIALOG_ON_FRAME,
              _DIALOG_OFF_FRAME, _DIALOG_LVL_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _TAB_FRAME, 'exit': ('on_click_in', '角色-遗器', '遗器位-头部')},
        {'frame': _REPLACE_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-排序设置')},
        {'frame': _DIALOG_ON_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '开关-建议排序')},
        {'frame': _DIALOG_OFF_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '单选-等级')},
        {'frame': _DIALOG_LVL_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '按钮-确认')},
        {'frame': _REPLACE_FRAME},
    ])
    op = _WatchedEquipRelic(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'重进全链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert result.status == 'ALREADY_EQUIPPED', \
        f'应幂等成功截断(不进扫描):status={result.status!r}'
    assert fixture_controller.phase_idx == 5, (
        f'应推进到确认后的替换屏帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area('角色-遗器', '遗器位-头部'), \
        f'着装页遗器位点击缺失:{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area('遗器-替换', '按钮-排序设置'), \
        '排序按钮点击缺失(弹窗未打开)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '开关-建议排序'), \
        '开关点击缺失(建议排序未关)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '单选-等级'), \
        '等级 radio 点击缺失(基础排序未选等级)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '按钮-确认'), \
        '确认点击缺失(排序设置未提交)'


def test_reuse_path_skips_sort_prepend(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """快速路径(已在正确部位替换列表):滚顶复用列表,不执行排序前置。

    锁:排序设置只在重进时被游戏重置,复用列表时排序已静态——重复执行
    前置会白开弹窗+改用户手动设置过的排序。"""
    _require_screens(test_context, [_REPLACE_FRAME])
    fixture_controller.set_phases([{'frame': _REPLACE_FRAME}])
    op = _WatchedEquipRelic(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success and result.status == 'ALREADY_EQUIPPED', (
        f'复用路径应幂等成功:status={result.status!r} '
        f'clicks={fixture_controller.recorded_clicks}')
    # phase_idx==0 即「排序按钮区零真实点击」的铁证:本剧本首帧 exit 区 =
    # 排序按钮 pc_rect,任何落区内的真实点击都会推进 phase(harness 的
    # drag_to 只记账不推进,滚顶拖拽 end 点恰落按钮 rect 属记账噪声,不算)
    assert fixture_controller.phase_idx == 0, \
        f'复用路径不应有帧推进(排序按钮区被真实点击):{fixture_controller.recorded_clicks}'
