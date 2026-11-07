"""UpgradeLightConeOp(光锥晋阶升级)差异化分支流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_trace.py
模块 docstring——「光锥-等级提升」等面板态帧测试仓缺存档、识别类输入禁止
合成),monkeypatch 识别层构造 round 结果,驱动完整 ``execute()`` 节点图。

同构精简说明:与 trace/character 同构的部分(flat loop 分类/缺料判停/
入口判满/升级按钮执行)已分别在 test_upgrade_trace.py /
test_upgrade_character.py 锁定,本文件只测 light cone 特有分支——出处
src/sr_od/operations/upgrade_light_cone.py 模块 docstring 与 upgrade_loop
实现:
- 「材料补全」确认弹窗:fill_generic 授权点「确认」继续;未授权防御性点
  「取消」判停——通用材料是稀缺消耗品,授权边界 = 确认/取消二选一;
- auto_farm 快速刷取预算耗尽判停(防开拓力/券无限烧)。
"""

from __future__ import annotations

import pytest

import sr_od.operations.upgrade_light_cone as lc_module
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.operations.upgrade_light_cone import UpgradeLightConeOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_LC_TAB: str = '角色-光锥'
_LC_ASC: str = '光锥-等级提升'

# 升级循环每轮分类的第一个识别查询 = 材料补全弹窗锚(优先级①在判停检查
# 之前,判停收尾轮同样先查它),桩以它计轮推进剧本。
_ROUND_START: tuple[str, str] = (_LC_ASC, '标题-材料补全弹窗')


class _WatchedUpgradeLightCone(WatchdogOperationMixin, UpgradeLightConeOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 40

    def __init__(self, ctx: SrTestContext, fill_generic: bool = False,
                 auto_farm: bool = False) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。"""
        UpgradeLightConeOp.__init__(self, ctx, fill_generic=fill_generic,
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

    def _fake_level(self, screen_name: str | None = None) -> int | None:
        state['level_reads'] += 1
        return level

    monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeLightConeOp, '_read_lc_level', _fake_level)
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


def _count_clicks_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> int:
    """落在建档区 pc_rect 内的点击次数。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    rect = area.pc_rect
    return sum(
        1 for x, y in clicks
        if rect.x1 <= x <= rect.x2 and rect.y1 <= y <= rect.y2
    )


def _run_op(op: UpgradeLightConeOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


_ENTRY_SCENES: list[set[tuple[str, str]]] = [
    {(_LC_TAB, '标题-角色光锥'), (_LC_TAB, '按钮-强化')},
]


class TestUpgradeLightConeBranches:

    def test_fill_generic_confirms_popup(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """fill_generic 授权:通用材料补全按钮 → 确认弹窗 → 点「确认」继续升满。

        弹窗分支只许点确认、绝不点取消(取消+判停是未授权防御路径);
        材料补上后按钮转「快速升级」执行,升满回光锥 TAB(MAX_LEVEL)。"""
        scenes = [
            *_ENTRY_SCENES,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-通用材料补全')},
            {(_LC_ASC, '标题-材料补全弹窗')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},
            set(),
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeLightCone(test_context, fill_generic=True)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'确认补全后应继续升满,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-通用材料补全'), (
            '缺料轮应先点通用材料补全按钮唤出弹窗'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-确认材料补全'), (
            '授权后弹窗应点确认'
        )
        assert not _has_click_in(clicks, test_context, _LC_ASC, '按钮-取消材料补全'), (
            f'授权流不得触发取消路径,clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-快速升级')
        assert state['level_reads'] == 0, '授权确认升满路径不应触发判停读取'

    def test_popup_cancelled_without_authorization_capped(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """弹窗在场但 fill_generic 未授权:防御路径点「取消」+ 判停。

        残留弹窗态下未授权 = 绝不点确认(确认即真实消耗稀缺通用材料);
        取消判停后经「关闭X」回光锥 TAB,LIGHT_CONE_CAPPED 结束。"""
        scenes = [
            *_ENTRY_SCENES,
            {(_LC_ASC, '标题-材料补全弹窗')},
            set(),
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeLightCone(test_context, fill_generic=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'未授权弹窗应取消判停收尾,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-取消材料补全'), (
            '未授权防御路径应点取消'
        )
        assert not _has_click_in(clicks, test_context, _LC_ASC, '按钮-确认材料补全'), (
            f'未授权绝不允许点确认(稀缺消耗),clicks={clicks}'
        )
        assert state['find_clicks'] == [
            (_LC_TAB, '按钮-强化'),
            (_LC_ASC, '按钮-关闭X'),
        ], f'find+click 序列(开晋阶/关X收尾)漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'

    def test_farm_budget_exhaustion_stops(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """auto_farm 快速刷取预算耗尽:恰刷 _LC_FARM_ROUNDS_MAX 次后判停。

        预算计数防开拓力/券无限烧:开始刷取点击次数 == 预算常量(单一来源
        现算),耗尽即判停收尾,不出现第 _MAX+1 次刷取点击。"""
        max_rounds = lc_module._LC_FARM_ROUNDS_MAX
        farm_scene = {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-开始刷取')}
        scenes = [
            *_ENTRY_SCENES,
            *[farm_scene] * max_rounds,
            {(_LC_ASC, '标题-光锥详情')},
            set(),
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeLightCone(test_context, auto_farm=True)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'刷取预算耗尽应判停收尾,status={result.status}'
        )
        farm_clicks = _count_clicks_in(clicks, test_context, _LC_ASC, '按钮-开始刷取')
        assert farm_clicks == max_rounds, (
            f'刷取点击应恰为预算 {max_rounds} 次,实际 {farm_clicks}'
        )
        assert state['find_clicks'] == [
            (_LC_TAB, '按钮-强化'),
            (_LC_ASC, '按钮-关闭X'),
        ], f'find+click 序列漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'
