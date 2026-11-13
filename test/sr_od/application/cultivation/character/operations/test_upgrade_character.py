"""UpgradeCharacterOp(角色晋阶升级)流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_trace.py
——「角色-等级提升」等面板态帧测试仓缺存档、识别类输入禁止合成),
monkeypatch 识别层构造 round 结果,驱动完整 ``execute()`` 节点图。

锁定的设计约定(出处 upgrade_character.py 模块 docstring 与 upgrade_loop
实现,2026-11-13 阿哈等级1 全形态实机摸底后重构):
- 入口按钮三态分流:详情页右下「升级」(未满级)/「晋阶」(到上限)/
  无按钮(80 满)——未满级角色不得再被误判已满;
- 通用材料补全链(fill_generic 默认 True):缺料按钮 → 确认框确认 →
  材料齐后快速升级执行;
- fill_generic=False 时缺料判停(MATERIAL_CAPPED),不碰确认框;
- 升级/晋阶执行横幅两种标题(「等级提升」/「角色晋阶」)点空白关闭。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.cultivation.character.operations.upgrade_character import (
    UpgradeCharacterOp,
)

_DETAIL: str = '角色-详情'
_ASCEND: str = '角色-等级提升'

# 升级循环每轮分类的第一个识别查询 = 材料补全确认框锚(优先级①),桩以它计轮
_ROUND_START: tuple[str, str] = (_ASCEND, '标题-材料补全弹窗')


class _WatchedUpgradeCharacter(WatchdogOperationMixin, UpgradeCharacterOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 40

    def __init__(self, ctx: SrTestContext, fill_generic: bool = True,
                 auto_farm: bool = False) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。"""
        UpgradeCharacterOp.__init__(self, ctx, fill_generic=fill_generic,
                                    auto_farm=auto_farm)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _install_script(
    monkeypatch: pytest.MonkeyPatch,
    ctx: SrTestContext,
    scenes: list[set[tuple[str, str]]],
    level: int,
) -> dict:
    """桩识别层并装记录器(场景语义同 test_upgrade_trace._install_script)。"""
    state: dict = {'round': 0, 'level_reads': 0, 'find_events': [],
                   'find_clicks': []}

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        if (s_name, a_name) == _ROUND_START:
            state['round'] += 1
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is None:
            raise AssertionError(f'升级循环剧本耗尽:第 {state["round"]} 轮查询 {a_name}')
        if (s_name, a_name) in scene:
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
        state['find_clicks'].append((s_name, a_name))
        return self.round_success(status=a_name)

    def _fake_level(self) -> int | None:
        state['level_reads'] += 1
        return level

    monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeCharacterOp, '_read_ascend_level', _fake_level)
    return state


def _record_controller_clicks(
    monkeypatch: pytest.MonkeyPatch, ctx: SrTestContext,
) -> list[tuple[int, int]]:
    """包装 controller.click 记录点击坐标(op 直点全部经 controller)。"""
    clicks: list[tuple[int, int]] = []
    real_click = ctx.controller.click

    def _recording_click(pos=None, press_time: float = 0, pc_alt: bool = False,
                         gamepad_key: str | None = None) -> bool:
        if pos is not None:
            clicks.append((int(pos.x), int(pos.y)))
        return real_click(pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctx.controller, 'click', _recording_click)
    return clicks


def _has_click_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> bool:
    """是否有点击落在建档区 pc_rect 内(坐标单一真相源 = screen_info)。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    rect = area.pc_rect
    return any(
        rect.x1 <= x <= rect.x2 and rect.y1 <= y <= rect.y2 for x, y in clicks
    )


def _run_op(op: UpgradeCharacterOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


class TestUpgradeCharacterEntryStates:

    def test_unmaxed_level_entry_not_mistaken_as_max(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口「升级」按钮(未满级角色)分流:不得误判已满。

        1.1 实机摸底:等级未到上限的角色右下按钮是「升级」而非「晋阶」,
        旧版只认「晋阶」会把这类角色误判 ALREADY_MAX 直接退出——本测试
        锁定「升级」入口正常打开界面并走升级循环。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮1:执行升级
            {(_ASCEND, '标题-升级结果')},                            # 轮2:升级横幅
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:详情页判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=80)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'未满级入口应正常升级到满,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _DETAIL, '按钮-升级'), (
            '未满级入口应点击「升级」按钮打开界面'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-快速升级'), (
            '材料足轮次应执行升级点击'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-升级'),
            (_ASCEND, '点击区-关闭横幅'),
        ], f'find+click 序列(开界面/关升级横幅)漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 0, '满级路径不应读等级'

    def test_already_max_entry_stays_zero_click(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口无按钮(80/80):零点击直接 MAX_LEVEL(已满判据保持)。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情')},
        ]
        _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'无按钮起点应直接 MAX_LEVEL,status={result.status}'
        )
        assert clicks == [], f'已满级起点不应有任何画面点击:{clicks}'


class TestUpgradeCharacterFillGeneric:

    def test_generic_fill_then_upgrade_chain(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """通用材料补全全链(fill_generic 默认 True):缺料按钮 → 确认框
        确认 → 材料齐 → 快速升级执行 → 横幅关闭 → 详情判满。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-通用材料补全')},  # 轮1:缺料
            {(_ASCEND, '标题-材料补全弹窗')},                       # 轮2:确认框
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮3:材料齐
            {(_ASCEND, '标题-晋阶结果')},                           # 轮4:晋阶横幅(双锚之一)
            {(_DETAIL, '按钮-属性详情')},                           # 轮5:详情页判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context)  # fill_generic 默认 True
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'通用材料补全链应以满级结束,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-通用材料补全'), (
            '缺料轮应点击「使用通用材料补全」'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-确认材料补全'), (
            '确认框轮应点击确认(fill_generic 默认授权)'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-升级'),
            (_ASCEND, '点击区-关闭横幅'),
        ], f'find+click 序列漂移:{state["find_clicks"]}'
        assert state['find_events'].count(_ROUND_START) == 5, (
            '循环应恰好分类 5 轮,轮数漂移 = 循环结构变化'
        )

    def test_fill_generic_false_stops_on_lacking(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """fill_generic=False:缺料判停 MATERIAL_CAPPED,不碰通用材料补全。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-晋阶')},   # 入口轮:到上限态
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-通用材料补全')},  # 轮1:缺料判停
            {(_ASCEND, '标题-等级提升')},                           # 轮2:收尾途中
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:回到详情
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=20)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context, fill_generic=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'未授权通用材料应判停收尾,status={result.status}'
        )
        assert not _has_click_in(clicks, test_context, _ASCEND, '按钮-通用材料补全'), (
            'fill_generic=False 不应点击通用材料补全按钮'
        )
        assert not _has_click_in(clicks, test_context, _ASCEND, '按钮-确认材料补全'), (
            'fill_generic=False 不应确认材料补全弹窗'
        )
        assert state['find_clicks'][-1] == (_ASCEND, '按钮-返回箭头'), (
            '判停后应经返回箭头收尾'
        )
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'
