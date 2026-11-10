"""SelectBagRelicOp(背包遗器选件导航)流程与守卫测试。

锁的内容(出处 src/sr_od/operations/select_bag_relic.py):
- 构造守卫:部位越界 / 套装名不在常量表 / 套装无该部位件 / main_stat 未实现
  显式失败;
- 全链流程(fixture 剧本):部位筛选点击 → 漏斗开面板 → 套装选择开弹窗 →
  扫描滚动后 OCR 命中套装行点行文本中心 → 确认关弹窗 → 网格选卡件名核对
  成功(终点=背包-遗器选中件,不执行强化);
- 无套装意图快速路径:部位筛选后底部强化/重掷按钮出现即选中证据,
  不经筛选面板链。

fixture 出处:实机摸底帧(2026-11-11 背包-遗器筛选链,进展目录
recon/bag-relic-screen.md),归档 screens/背包-遗器*/;弹窗滚动帧用
「已勾选」帧承载扫描命中(静态帧语义:点击坐标与 OCR 行定位的真实性)。
"""

from __future__ import annotations

import pytest

from sr_od.operations.select_bag_relic import SelectBagRelicOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_BAG_FRAME = ('背包-遗器', '列表默认')
_BAG_SELECTED_FRAME = ('背包-遗器', '套装筛选选中件')
_PANEL_FRAME = ('背包-遗器-筛选', '面板打开')
_RULE_LIST_FRAME = ('背包-遗器-筛选规则', '隧洞列表')
_RULE_CHECKED_FRAME = ('背包-遗器-筛选规则', '已勾选')

# 「已勾选」帧上「晨昏交界的翔鹰」行文本 OCR 中心 (628,480),外扩容错
_SET_ROW_RECT = [527, 455, 735, 505]


class _WatchedSelectBagRelic(WatchdogOperationMixin, SelectBagRelicOp):
    """带看门狗的流程测试 op(轮次超限自动停,防剧本错配死循环)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: SrTestContext, set_name: str | None = '晨昏交界的翔鹰') -> None:
        SelectBagRelicOp.__init__(self, ctx, pos=1, set_name=set_name)
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


def test_construction_guards(test_context: SrTestContext) -> None:
    """构造守卫:部位越界/套装表外/套装无该部位件/main_stat 未实现均显式失败;
    表内意图解析出单件名(set+pos 唯一确定)。"""
    with pytest.raises(ValueError, match='超出 1-6'):
        SelectBagRelicOp(test_context, pos=0)
    with pytest.raises(ValueError, match='不在常量表'):
        SelectBagRelicOp(test_context, pos=1, set_name='不存在的套装')
    with pytest.raises(ValueError, match='无部位'):
        SelectBagRelicOp(test_context, pos=5, set_name='晨昏交界的翔鹰')
    with pytest.raises(ValueError, match='main_stat'):
        SelectBagRelicOp(test_context, pos=1, main_stat='速度')
    op = SelectBagRelicOp(test_context, pos=1, set_name='晨昏交界的翔鹰')
    assert op._piece_name == '翔鹰的长喙头盔'


def test_full_chain_selects_filtered_piece(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """套装意图全链:部位筛选 → 漏斗开面板 → 套装选择开弹窗 → 扫描(滚动
    一屏后)OCR 命中点行文本中心 → 确认关弹窗 → 网格选卡件名核对成功。

    锁:筛选链逐节点点击缺一即落空(选卡件名核对是最终防线);弹窗滚动后
    只点行文本中心(实机坑:滚动后点击系统性偏移一行)。"""
    frames = [_BAG_FRAME, _PANEL_FRAME, _RULE_LIST_FRAME,
              _RULE_CHECKED_FRAME, _BAG_SELECTED_FRAME]
    _require_screens(test_context, frames)
    fixture_controller.set_phases([
        {'frame': _BAG_FRAME, 'exit': ('on_click_in', '背包-遗器', '部位筛选-头部')},
        {'frame': _BAG_FRAME, 'exit': ('on_click_in', '背包-遗器', '按钮-筛选漏斗')},
        {'frame': _PANEL_FRAME, 'exit': ('on_click_in', '背包-遗器-筛选', '按钮-套装选择')},
        # 隧洞列表首屏无目标套装 → 扫描拖拽滚动,一次截图后推进到已勾选帧
        {'frame': _RULE_LIST_FRAME, 'exit': ('on_polls', 1)},
        {'frame': _RULE_CHECKED_FRAME, 'exit': ('on_click_in', _SET_ROW_RECT)},
        {'frame': _RULE_CHECKED_FRAME,
         'exit': ('on_click_in', '背包-遗器-筛选规则', '按钮-确认')},
        {'frame': _BAG_SELECTED_FRAME},
    ])
    op = _WatchedSelectBagRelic(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success, (
        f'选件全链未成功:status={result.status!r} message={result.message!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert result.status == 'SELECTED', f'应以选中件收尾:status={result.status!r}'
    assert fixture_controller.phase_idx == 6, (
        f'应推进到筛选后选中件帧:phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area('背包-遗器', '部位筛选-头部'), \
        '部位筛选点击缺失'
    assert fixture_controller.click_hit_area('背包-遗器', '按钮-筛选漏斗'), \
        '漏斗点击缺失(面板未打开)'
    assert fixture_controller.click_hit_area('背包-遗器-筛选', '按钮-套装选择'), \
        '套装选择点击缺失(弹窗未打开)'
    row_clicked = any(
        _SET_ROW_RECT[0] <= p.x <= _SET_ROW_RECT[2]
        and _SET_ROW_RECT[1] <= p.y <= _SET_ROW_RECT[3]
        for p in fixture_controller.recorded_clicks)
    assert row_clicked, f'套装行文本中心点击缺失:{fixture_controller.recorded_clicks}'
    assert fixture_controller.click_hit_area('背包-遗器-筛选规则', '按钮-确认'), \
        '确认点击缺失(筛选未提交)'


def test_no_set_path_skips_filter_chain(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """无套装意图:部位筛选后底部重掷按钮出现即选中证据(选中态帧),
    不开筛选面板、不开弹窗。"""
    _require_screens(test_context, [_BAG_FRAME])
    fixture_controller.set_phases([
        {'frame': _BAG_FRAME, 'exit': ('on_click_in', '背包-遗器', '部位筛选-头部')},
        {'frame': _BAG_FRAME},
    ])
    op = _WatchedSelectBagRelic(test_context, set_name=None)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert result.success and result.status == 'SELECTED', (
        f'无套装路径应选中收尾:status={result.status!r} '
        f'clicks={fixture_controller.recorded_clicks}')
    assert fixture_controller.click_hit_area('背包-遗器', '部位筛选-头部'), \
        '部位筛选点击缺失'
    assert fixture_controller.phase_idx == 1, (
        f'不应有帧推进(漏斗/面板链未走):phase_idx={fixture_controller.phase_idx}')
    assert not fixture_controller.click_hit_area('背包-遗器-筛选', '按钮-套装选择')
    assert not fixture_controller.click_hit_area('背包-遗器-筛选规则', '按钮-确认')


def test_entry_screen_guard(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """入口画面级判定:非背包-遗器起点显式失败,零点击(AGENTS §3)。"""
    _require_screens(test_context, [('遗器-替换', 'default')])
    fixture_controller.set_phases([{'frame': ('遗器-替换', 'default')}])
    op = _WatchedSelectBagRelic(test_context)
    op._init_watchdog()
    result = _run_execute(test_context, op)

    assert not result.success, '入口不符应显式失败'
    assert '不在背包-遗器' in (result.status or ''), \
        f'失败信息应指明前置:{result.status!r}'
    assert fixture_controller.recorded_clicks == [], \
        f'入口失败不应有任何点击:{fixture_controller.recorded_clicks}'
