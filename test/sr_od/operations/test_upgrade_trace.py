"""UpgradeTraceOp(行迹升级)四分支流程测试。

测试层级声明:桩识别层的单元式流程测试——monkeypatch 掉
``round_by_find_area`` / ``round_by_find_and_click_area``(按剧本直接构造
round 结果)与面板读数辅助,驱动 op 跑完整 ``execute()`` 节点图,锁
「帧态 → 分支判定 → 动作 → 状态机流转」。不走真帧 + 真识别的理由:四个
分支的画面证据全是**同屏面板态**(满级锚/通用材料按钮/分类标签/灰字锚,
见 assets/game_data/screen_info/character_traces.yml「角色-行迹」screen),
测试仓只有树态存档帧(screens/角色-行迹/default.webp),面板态缺帧,且
识别类输入禁止合成(sr-od-test/README.md「识别类测试的图片输入」)。
识别层本身的正确性归画面建档流程与实机 run_operation 验证,不在本文件
锁面内;点击/状态断言的坐标都来自真实 screen_loader 建档区。

四分支规格出处:src/sr_od/operations/upgrade_trace.py 模块 docstring
「升级循环每轮分类(优先级)」与 upgrade_loop 实现(优先级⓪~⑤)。
"""

from __future__ import annotations

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.operations.upgrade_trace import UpgradeTraceOp
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_TRACE: str = '角色-行迹'

# 升级循环每轮分类的第一个识别查询 = 材料补全弹窗锚(⓪ 优先于判停/满级,
# 判停收尾轮同样先查它),桩以它计轮推进剧本。
_ROUND_START: tuple[str, str] = (_TRACE, '标题-材料补全弹窗')


class _WatchedUpgradeTrace(WatchdogOperationMixin, UpgradeTraceOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 40

    def __init__(self, ctx: SrTestContext, target: str,
                 fill_generic: bool = False) -> None:
        """真实构造路径(含 target 校验);测试无游戏窗口,跳过窗口前置链。"""
        UpgradeTraceOp.__init__(self, ctx, target=target,
                                fill_generic=fill_generic)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _install_script(
    monkeypatch: pytest.MonkeyPatch,
    ctx: SrTestContext,
    scenes: list[set[tuple[str, str]]],
    categories: list[str],
    level: int,
) -> dict:
    """桩识别层并装记录器。

    - ``scenes[0]`` = 入口核对轮的命中集(screen, area);``scenes[1:]`` =
      升级循环各轮命中集(含判停收尾轮),以弹窗锚查询为轮界逐轮推进;
      不在命中集的查询一律视为未命中。剧本耗尽即抛错(op 逐轮兜成 retry
      有界失败,测试以最终状态断言变红),不让剧本错误静默转绿。
    - ``categories``:``_read_panel_category`` 按调用次序弹出(分类校验桩)。
    - ``level``:``_read_panel_level`` 桩返回值;读取次数记入返回值供断言。
    返回 ``{'find_events', 'find_clicks', 'level_reads', 'round'}``。
    """
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

    def _fake_category(self) -> str | None:
        return categories.pop(0) if categories else None

    def _fake_level(self) -> int | None:
        state['level_reads'] += 1
        return level

    monkeypatch.setattr(UpgradeTraceOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeTraceOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeTraceOp, '_read_panel_category', _fake_category)
    monkeypatch.setattr(UpgradeTraceOp, '_read_panel_level', _fake_level)
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


def _run_op(op: UpgradeTraceOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


class TestUpgradeTraceBranches:
    """四分支各一条:满级 / 材料不足判停 / 目标校验 / 灰字全缺两子态。"""

    def test_max_level_shortcut(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """满级路径:面板态含「已达最大等级」锚 → 首轮分类即 MAX_LEVEL 成功。

        满级锚优先级高于面板态/按钮判定:命中后校验面板分类确实是目标技能
        (满级锚校验,防「别的满级技能的面板」误报),通过后点面板外空白关
        面板再交还控制权,不进按钮判定、不触发判停读取。"""
        scenes = [
            {(_TRACE, '标题-行迹')},
            {(_TRACE, '文本-已达最大等级')},
        ]
        state = _install_script(monkeypatch, test_context, scenes,
                                categories=['普攻'], level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, target='普攻')
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'满级锚应直接 MAX_LEVEL,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-面板外空白'), (
            f'MAX_LEVEL 收尾应点空白关面板,clicks={clicks}'
        )
        assert state['level_reads'] == 0, '满级路径不应触发判停等级读取'

    def test_material_capped_without_generic_fill(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """材料不足判停:「使用通用材料补全」命中且 fill_generic=False。

        未授权 = 不执行任何升级点击(两个升级按钮共用同一建档位,按钮区
        零点击即锁「不误点禁用按钮」);判停后点空白关面板回树态,以
        MATERIAL_CAPPED 成功结束,判停等级恰好读取一次。"""
        scenes = [
            {(_TRACE, '标题-行迹')},
            {(_TRACE, '开关-简略描述'), (_TRACE, '按钮-通用材料补全')},
            {(_TRACE, '开关-简略描述')},
            set(),
        ]
        state = _install_script(monkeypatch, test_context, scenes,
                                categories=['普攻'], level=6)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, target='普攻')
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'未授权缺料应判停收尾,status={result.status}'
        )
        assert op._capped_level == 6, '判停应捕获面板等级供报告(桩值 6)'
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-快速升级'), (
            f'未授权判停不得点击升级按钮区,clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-面板外空白')
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'

    def test_category_mismatch_reclicks_target_node(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """目标校验:面板分类标签(战技)≠ target(普攻)→ 再点目标节点切换。

        错面板不执行升级,先点目标节点切面板;切换生效后轮次照常推进升满
        (MAX_LEVEL)——轮次推进而非卡死由 op 成功终止锁住。"""
        scenes = [
            {(_TRACE, '标题-行迹')},
            {(_TRACE, '开关-简略描述')},
            {(_TRACE, '开关-简略描述'), (_TRACE, '按钮-快速升级')},
            {(_TRACE, '文本-已达最大等级')},
        ]
        state = _install_script(monkeypatch, test_context, scenes,
                                categories=['战技', '普攻', '普攻'], level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, target='普攻')
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'分类切换后应继续升满(轮次推进不卡死),status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-节点-普攻'), (
            f'分类不符应再点目标节点切换,clicks={clicks}'
        )
        assert state['find_clicks'] == [(_TRACE, '点击区-节点-普攻')], (
            f'打开面板外的 find+click 不应漂移:{state["find_clicks"]}'
        )

    def test_gray_all_missing_stops_but_transition_retries(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """灰字全缺两子态:过渡态不判停,真灰字态才判停。

        按钮+满级锚全缺时:「可提升至」不可见 = 执行后动画/过渡态 → 点空白
        重试、不判停(误报判停比多等一轮危害大);「可提升至」可见 = 真灰字
        全缺 → 判停。规格断言两件:循环在判停前查询过「可提升至」锚
        (两态判定的入口证据),判停等级恰好读取一次 = 过渡态未误判停。"""
        scenes = [
            {(_TRACE, '标题-行迹')},
            {(_TRACE, '开关-简略描述')},
            {(_TRACE, '开关-简略描述'), (_TRACE, '文本-可提升至')},
            {(_TRACE, '开关-简略描述')},
            set(),
        ]
        state = _install_script(monkeypatch, test_context, scenes,
                                categories=['普攻', '普攻'], level=9)
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, target='普攻')
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'过渡态→灰字态应最终判停收尾,status={result.status}'
        )
        assert (_TRACE, '文本-可提升至') in state['find_events'], (
            '判停前应查询「可提升至」锚区分过渡态/灰字态(两态判定),'
            f'find_events={state["find_events"]}'
        )
        assert state['level_reads'] == 1, (
            '判停决策应恰好一次:过渡态(第1轮)不判停,灰字态(第2轮)才判停'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-面板外空白'), (
            '过渡态应点空白重试、判停后应点空白关面板'
        )
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-快速升级'), (
            f'灰字全缺不得执行升级点击,clicks={clicks}'
        )
