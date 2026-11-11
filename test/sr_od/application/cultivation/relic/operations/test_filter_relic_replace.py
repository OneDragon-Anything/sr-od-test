"""FilterRelicReplaceOp 流程测试(set_name 链 / sort_stat 链 / 幂等空跑 /
重复运行不反选 四剧本)。

fixture 帧全部取自摸底归档(2026-11-12 实机交互链,事实 F1-F16):
着装页 default / 替换屏 default / 筛选面板开 / 筛选规则弹窗(+已勾选) /
chip 筛选后列表 / 排序弹窗建议开/建议关/等级已选中 / 属性排序上 /
排序应用后列表。帧缺失 skip。

剧本2(排序链)的滚动定位用「属性排序上」帧(该帧滚动位含攻击力行;摸底
帧序列不含「等级选中+属性分区同屏」态,用 on_polls 推进模拟拖拽后的画面
流转);排序摘要校验节点对摘要读区 rect 打桩(摸底帧摘要文本是历史操作
「稀有度|暴击率,速度」,与剧本排序意图不同——桩返回期望形态验证校验逻辑
本身,读区 OCR 行为由 S1 离线验证与实机验收覆盖)。
"""

from types import SimpleNamespace

import pytest
from one_dragon.base.geometry.rectangle import Rect

from sr_od.application.cultivation.relic.operations.filter_relic_replace import (
    FilterRelicReplaceOp,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    reset_running_state,
    fast_sleep,
)

_TAB_FRAME = ('角色-遗器', 'default')
_REPLACE_FRAME = ('遗器-替换', 'default')
_FILTER_PANEL_FRAME = ('遗器-替换', '筛选面板开')
_FILTER_CHIP_FRAME = ('遗器-替换', '筛选面板带chip筛选后列表')
_DIALOG_FRAME = ('遗器-替换', '筛选规则弹窗')
_DIALOG_CHECKED_FRAME = ('遗器-替换', '筛选规则弹窗已勾选')
_SORT_ON_FRAME = ('遗器-排序规则', '建议排序开')
_SORT_OFF_FRAME = ('遗器-排序规则', '建议排序关')
_SORT_LEVEL_FRAME = ('遗器-排序规则', '等级已选中')
_SORT_ATTR_FRAME = ('遗器-替换', '排序弹窗属性排序上')
_SORT_APPLIED_FRAME = ('遗器-替换', '排序应用后列表')


class _WatchedFilterRelic(WatchdogOperationMixin, FilterRelicReplaceOp):
    """带看门狗的流程测试 op(轮次超限自动停,防剧本错配死循环)。"""

    watchdog_max_rounds: int = 80

    def __init__(self, ctx: SrTestContext, pos: int = 1,
                 set_name: str | None = None, sort_stat: str | None = None) -> None:
        FilterRelicReplaceOp.__init__(self, ctx, pos=pos,
                                      set_name=set_name, sort_stat=sort_stat)
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


def _run_op(test_context: SrTestContext, op: FilterRelicReplaceOp):
    """fast_sleep(op) 包裹跑完整 execute(连带桩掉 op 模块的 time 引用),
    收尾复位运行态。"""
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return result


def _require_screens(test_context: SrTestContext, frames: list[tuple[str, str]]) -> None:
    for frame in frames:
        if not test_context.has_screen(*frame):
            pytest.skip(f'存档截图缺失:screens/{frame[0]}/{frame[1]}.webp')


# --------------------------------------------------------------------------- #
# 剧本1:set_name 链全流程
# --------------------------------------------------------------------------- #

def test_set_name_chain_applies_filter(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """套装筛选链全节点:漏斗开面板 → 套装弹窗(切TAB/全部清除/点行) →
    确认(筛选中角标) → 关面板收尾停替换屏。

    锁:F1 漏斗 toggle、F3 套装选择条开弹窗、F4 全部清除先行的幂等前置、
    F5 确认后面板保持打开、F7 筛选中角标验证——任一节点缺失即卡死或
    状态不符。"""
    frames = [_TAB_FRAME, _REPLACE_FRAME, _FILTER_PANEL_FRAME,
              _DIALOG_FRAME, _DIALOG_CHECKED_FRAME, _FILTER_CHIP_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _TAB_FRAME, 'exit': ('on_click_in', '角色-遗器', '遗器位-头部')},
        {'frame': _REPLACE_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-筛选漏斗')},
        {'frame': _FILTER_PANEL_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选', '按钮-套装选择')},
        {'frame': _DIALOG_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '按钮-全部清除')},
        {'frame': _DIALOG_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '区域-套装列表')},
        {'frame': _DIALOG_CHECKED_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '按钮-确认')},
        {'frame': _FILTER_CHIP_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-筛选漏斗')},
        {'frame': _REPLACE_FRAME},
    ])
    op = _WatchedFilterRelic(test_context, pos=1, set_name='密林卧雪的猎人')
    result = _run_op(test_context, op)

    assert result.success, (
        f'套装筛选链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert result.status == 'FILTER_SET', f'应收尾于 FILTER_SET:{result.status!r}'
    assert fixture_controller.phase_idx == 7, (
        f'应推进到关面板后的替换屏帧:phase_idx={fixture_controller.phase_idx}')
    # 全节点点击逐区断言(F1/F3/切TAB/F4/F4点行/F5/F1关面板)
    assert fixture_controller.click_hit_area('遗器-替换', '按钮-筛选漏斗'), \
        f'漏斗点击缺失(开/关面板):{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area('遗器-替换-筛选', '按钮-套装选择'), \
        '套装选择条点击缺失(弹窗未打开)'
    assert fixture_controller.click_hit_area('遗器-替换-筛选规则', 'TAB-隧洞遗器'), \
        '隧洞TAB点击缺失(cavern 套装应在隧洞 TAB 勾选)'
    assert fixture_controller.click_hit_area('遗器-替换-筛选规则', '按钮-全部清除'), \
        '全部清除点击缺失(重复运行不反选的幂等前置)'
    assert fixture_controller.click_hit_area('遗器-替换-筛选规则', '区域-套装列表'), \
        '套装行点击缺失(筛选未勾选)'
    assert fixture_controller.click_hit_area('遗器-替换-筛选规则', '按钮-确认'), \
        '确认点击缺失(筛选未应用)'


# --------------------------------------------------------------------------- #
# 剧本2:sort_stat 链全流程
# --------------------------------------------------------------------------- #

def test_sort_stat_chain_applies_static_sort(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """排序链全节点:开排序弹窗 → 关建议排序 → 选等级 → 滚动定位属性行 →
    全部清除 → 点属性行 → 确认 → 摘要全等校验。

    锁:排序前置子链与 equip_relic 同源(关建议/选等级的防呆与 until 重入);
    「全部清除先于属性行点击」(F11 选中历史保留,不清则混合优先级);
    摘要全等校验通过才 SORT_SET。"""
    frames = [_TAB_FRAME, _REPLACE_FRAME, _SORT_ON_FRAME, _SORT_OFF_FRAME,
              _SORT_LEVEL_FRAME, _SORT_ATTR_FRAME, _SORT_APPLIED_FRAME]
    _require_screens(test_context, frames)
    # 摘要读区 rect 桩:verify_sort_summary 的读区 OCR 返回期望形态
    # (摸底帧摘要为历史操作文本,与剧本意图不同;校验逻辑本身是断言对象)
    summary_area = test_context.screen_loader.get_area('遗器-替换', '读区-排序摘要')
    real_ocr = test_context.ocr_service.get_ocr_result_list

    def fake_ocr(image, rect: Rect | None = None, **kwargs):
        if rect is not None and (rect.x1, rect.y1) == (summary_area.rect.x1, summary_area.rect.y1):
            # 摘要 UI 用属性短名(无「百分比」后缀,与 op 期望映射同形态;
            # F15 样本「暴击率」无后缀印证,百分比三属性的短名待实机验收复核)
            return [SimpleNamespace(data='等级|攻击力', x=100, y=980,
                                    w=200, h=25, confidence=1.0)]
        return real_ocr(image, rect=rect, **kwargs)

    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', fake_ocr)

    fixture_controller.set_phases([
        {'frame': _TAB_FRAME, 'exit': ('on_click_in', '角色-遗器', '遗器位-头部')},
        {'frame': _REPLACE_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-排序设置')},
        {'frame': _SORT_ON_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '开关-建议排序')},
        {'frame': _SORT_OFF_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '单选-等级')},
        # 拖拽后画面流转用 on_polls 模拟:定位轮截图后推进到属性分区可见帧
        {'frame': _SORT_LEVEL_FRAME, 'exit': ('on_polls', 1)},
        {'frame': _SORT_ATTR_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '按钮-全部清除')},
        {'frame': _SORT_ATTR_FRAME, 'exit': ('on_click_in', '遗器-排序规则', '按钮-确认')},
        {'frame': _SORT_APPLIED_FRAME},
    ])
    op = _WatchedFilterRelic(test_context, pos=1, sort_stat='攻击力')
    result = _run_op(test_context, op)

    assert result.success, (
        f'排序链未成功:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert result.status == 'SORT_SET', f'应收尾于 SORT_SET:{result.status!r}'
    assert fixture_controller.click_hit_area('遗器-替换', '按钮-排序设置'), \
        '排序设置点击缺失(弹窗未打开)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '开关-建议排序'), \
        '开关点击缺失(建议排序未关)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '单选-等级'), \
        '等级 radio 点击缺失(基础排序未选等级)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '按钮-全部清除'), \
        '全部清除点击缺失(属性排序残留未清)'
    assert fixture_controller.click_hit_area('遗器-排序规则', '按钮-确认'), \
        '确认点击缺失(排序未提交)'
    # 属性行点击 = 落在弹窗滚动区内的坐标点(OCR 定位;不落滚动区 = 没点行)
    scroll_area = test_context.screen_loader.get_area('遗器-排序规则', '区域-弹窗滚动区')
    rect = scroll_area.rect
    assert any(rect.x1 <= click.x < rect.x2 and rect.y1 <= click.y < rect.y2
               for click in fixture_controller.recorded_clicks), \
        f'属性行点击缺失(无落滚动区的点击):{fixture_controller.recorded_clicks}'


# --------------------------------------------------------------------------- #
# 剧本3:幂等空跑(两参均空)
# --------------------------------------------------------------------------- #

def test_noop_only_guarantees_pos(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """set_name/sort_stat 均 None:只保证部位正确即幂等成功,不碰筛选/排序
    (筛选态是后续扫描的流程前提,空跑不得清掉已有筛选)。"""
    _require_screens(test_context, [_REPLACE_FRAME])
    fixture_controller.set_phases([{'frame': _REPLACE_FRAME}])
    op = _WatchedFilterRelic(test_context, pos=1)
    result = _run_op(test_context, op)

    assert result.success and result.status == 'NOOP', (
        f'空跑应幂等成功:NOOP:{result.status!r}')
    assert fixture_controller.recorded_clicks == [], (
        f'空跑不应有任何点击:{fixture_controller.recorded_clicks}')


# --------------------------------------------------------------------------- #
# 剧本4:重复运行同参数不反选
# --------------------------------------------------------------------------- #

def test_repeat_same_set_name_does_not_toggle_off(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """同参数连跑两遍:第二遍同样先「全部清除」再勾选目标行——不反选
    (盲点已勾选行 = 取消勾选,F4 的幂等设计;链路级锁 = 两遍点击序列
    一致且各自成功)。"""
    frames = [_TAB_FRAME, _REPLACE_FRAME, _FILTER_PANEL_FRAME,
              _DIALOG_FRAME, _DIALOG_CHECKED_FRAME, _FILTER_CHIP_FRAME]
    _require_screens(test_context, frames)
    phases = [
        {'frame': _TAB_FRAME, 'exit': ('on_click_in', '角色-遗器', '遗器位-头部')},
        {'frame': _REPLACE_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-筛选漏斗')},
        {'frame': _FILTER_PANEL_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选', '按钮-套装选择')},
        {'frame': _DIALOG_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '按钮-全部清除')},
        {'frame': _DIALOG_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '区域-套装列表')},
        {'frame': _DIALOG_CHECKED_FRAME, 'exit': ('on_click_in', '遗器-替换-筛选规则', '按钮-确认')},
        {'frame': _FILTER_CHIP_FRAME, 'exit': ('on_click_in', '遗器-替换', '按钮-筛选漏斗')},
        {'frame': _REPLACE_FRAME},
    ]
    click_sequences: list[list[tuple[int, int]]] = []
    statuses: list[str] = []
    for _round in range(2):
        fixture_controller.set_phases([dict(p) for p in phases])
        op = _WatchedFilterRelic(test_context, pos=1, set_name='密林卧雪的猎人')
        result = _run_op(test_context, op)
        assert result.success, f'第 {_round + 1} 遍未成功:status={result.status!r}'
        statuses.append(result.status)
        # Point 未定义 __eq__(身份比较),比坐标元组
        click_sequences.append([c.tuple() for c in fixture_controller.recorded_clicks])

    assert statuses == ['FILTER_SET', 'FILTER_SET'], f'两遍应收尾一致:{statuses}'
    assert click_sequences[0] == click_sequences[1], (
        '两遍点击序列应一致(第二遍同为全部清除→点行,不反选)')
    assert fixture_controller.click_hit_area('遗器-替换-筛选规则', '按钮-全部清除'), \
        '第二遍的全部清除点击缺失(反选防线)'
