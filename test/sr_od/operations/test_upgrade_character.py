"""UpgradeCharacterOp(角色晋阶升级)差异化分支流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_trace.py
模块 docstring——「角色-等级提升」等面板态帧测试仓缺存档、识别类输入禁止
合成),monkeypatch 识别层构造 round 结果,驱动完整 ``execute()`` 节点图。

同构精简说明:与 UpgradeTraceOp 同构的部分(flat loop 分类/缺料判停/
升级按钮执行)已在 test_upgrade_trace.py 锁定,本文件只测 character 特有
分支——出处 src/sr_od/operations/upgrade_character.py 模块 docstring 与
upgrade_loop 实现:
- 入口 ALREADY_MAX 分流:晋阶按钮缺席 = 已满,不进升级循环直接成功;
- 升级执行后的「角色晋阶」结果横幅关闭(行迹线无横幅形态);
- 判停后经「返回箭头」回详情页收尾(行迹线 = 点空白关面板)。
"""

from __future__ import annotations

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.operations.upgrade_character import UpgradeCharacterOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_DETAIL: str = '角色-详情'
_ASCEND: str = '角色-等级提升'

# 升级循环每轮分类的第一个识别查询 = 晋阶结果横幅锚(优先级①在判停检查
# 之前,判停收尾轮同样先查它),桩以它计轮推进剧本。
_ROUND_START: tuple[str, str] = (_ASCEND, '标题-晋阶结果')


class _WatchedUpgradeCharacter(WatchdogOperationMixin, UpgradeCharacterOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 40

    def __init__(self, ctx: SrTestContext, auto_farm: bool = False) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。"""
        UpgradeCharacterOp.__init__(self, ctx, auto_farm=auto_farm)
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


class TestUpgradeCharacterBranches:

    def test_entry_already_max_succeeds_directly(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口 ALREADY_MAX 分流:详情 TAB 在但「晋阶」按钮缺席 = 已满级。

        不进打开晋阶/升级循环,零画面动作直接 MAX_LEVEL 成功——已满级起点
        直接成功是类 docstring 声明的结果契约。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情')},
        ]
        _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'晋阶按钮缺席应入口判满直接成功,status={result.status}'
        )
        assert clicks == [], f'已满级起点不应有任何画面点击:{clicks}'

    def test_banner_then_material_capped_returns_to_detail(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """横幅关闭 + 材料不足判停 + 返回箭头收尾全链。

        升级执行后弹「角色晋阶」结果横幅(点标题区关闭,until=横幅消失);
        按钮转「材料不足」且未授权 auto_farm → 判停;判停后经「返回箭头」
        回详情页,以 MATERIAL_CAPPED 成功结束,判停等级恰好读取一次。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-晋阶')},
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},
            {(_ASCEND, '标题-晋阶结果')},
            {(_ASCEND, '标题-等级提升')},
            set(),
            {(_DETAIL, '按钮-属性详情')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=75)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'判停应经返回箭头收尾,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-快速升级'), (
            '材料足轮次应执行升级点击'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-晋阶'),
            (_ASCEND, '标题-晋阶结果'),
            (_ASCEND, '按钮-返回箭头'),
        ], f'find+click 序列(开晋阶/关横幅/返回详情)漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'
