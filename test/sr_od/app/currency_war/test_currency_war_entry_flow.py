"""货币战争 入口 op 行为测试(fixture 驱动的流程测试)。

覆盖 ``StartCurrencyWarMatch`` 从大厅推进到备战阶段的 happy-path:

1. **新局 A8(最高职级)**:大厅(点开始货币战争)→ 模式选择(点进入标准博弈)
   → 难度确认 A8(点开始对局)→ 简报(点下一步)→ 备战(terminal,``_at_prep`` 命中)。
2. **新局 A5(未在最高)**:同上,但难度确认先点「返回最高职级」切 A8,再开始对局
   (多一个 phase,验证 D-24 锁最高难度分支)。

验证:

- op 完整跑完 ``execute()`` 并成功到达备战(``STATUS_AT_PREP``);
- 每个前进按钮的 click 落在对应 screen_info area 内(``click_hit_area``);
- 剧本推进到末 phase(备战)。

配套 ``test_currency_war_entry.py``(只测难度确认 OCR 检测);本文件测**节点行为**
(2026-08-05 方向 2,补 op 行为测试)。fixture 缺时 skip,归档后自动恢复运行。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.operations.entry.start_currency_war_match import (
    StartCurrencyWarMatch,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _WatchedStartCurrencyWarMatch(WatchdogOperationMixin, StartCurrencyWarMatch):
    """带看门狗的 StartCurrencyWarMatch(防 WAIT 段死循环)。"""


def _build_phases_new_match_a8() -> list[dict]:
    """新局 A8 happy-path 剧本(最高职级,直接开始对局,无「返回最高职级」)。

    每个前进按钮经 screen_info area 点击(2026-08-05 方向 1 改造),click 落 area 内推进。
    """
    return [
        {  # 大厅:click_start 点「按钮-开始货币战争」
            'frame': ('货币战争-大厅', 'lobby'),
            'exit': ('on_click_in', '货币战争-大厅', '按钮-开始货币战争'),
        },
        {  # 模式选择:advance_to_prep 点「按钮-进入标准博弈」
            'frame': ('货币战争-模式选择', 'default'),
            'exit': ('on_click_in', '货币战争-模式选择', '按钮-进入标准博弈'),
        },
        {  # 难度确认 A8:advance_to_prep 点「按钮-开始对局」(无返回最高职级)
            'frame': ('货币战争-难度确认', 'a8'),
            'exit': ('on_click_in', '货币战争-难度确认', '按钮-开始对局'),
        },
        {  # 简报:advance_to_prep 点「按钮-下一步」
            'frame': ('货币战争-简报', 'default'),
            'exit': ('on_click_in', '货币战争-简报', '按钮-下一步'),
        },
        {  # 备战:terminal(_at_prep 命中「购买经验」→ round_success)
            'frame': ('货币战争-备战', 'shop_closed'),
        },
    ]


def _build_phases_new_match_a5() -> list[dict]:
    """新局 A5 happy-path 剧本(未在最高职级):先「返回最高职级」切 A8,再开始对局。

    难度确认拆两 phase:A5 子态点「按钮-返回最高职级」→ A8 子态点「按钮-开始对局」
    (验证 D-24 锁最高难度:op 不直接点开始对局打 A5,而是先切最高)。
    """
    return [
        {
            'frame': ('货币战争-大厅', 'lobby'),
            'exit': ('on_click_in', '货币战争-大厅', '按钮-开始货币战争'),
        },
        {
            'frame': ('货币战争-模式选择', 'default'),
            'exit': ('on_click_in', '货币战争-模式选择', '按钮-进入标准博弈'),
        },
        {  # 难度确认 A5:点「按钮-返回最高职级」切最高
            'frame': ('货币战争-难度确认', 'a5'),
            'exit': ('on_click_in', '货币战争-难度确认', '按钮-返回最高职级'),
        },
        {  # 难度确认 A8:点「按钮-开始对局」
            'frame': ('货币战争-难度确认', 'a8'),
            'exit': ('on_click_in', '货币战争-难度确认', '按钮-开始对局'),
        },
        {
            'frame': ('货币战争-简报', 'default'),
            'exit': ('on_click_in', '货币战争-简报', '按钮-下一步'),
        },
        {
            'frame': ('货币战争-备战', 'shop_closed'),
        },
    ]


def _build_phases_residual_lobby_escape() -> list[dict]:
    """残留大厅逃逸剧本(真帧锁:2026-08-27 实机首跑失败帧)。

    上局结束「回大厅」后大厅 UI 层残留:开始按钮死(点击不推进画面),右上角
    「按钮-关闭」才是真退出。剧本:

    残留大厅(点开始无效,点关闭才推进)→ 朝露公馆世界入口(F 交互按 F)
    → 新鲜大厅(重新点开始)→ 模式选择 → 难度确认 A8 → 简报 → 备战。

    残留帧用测试仓归档 ``大厅-残留态-run49.webp``(真 OCR/模板,不 mock 识别)。
    """
    return [
        {  # 残留大厅:click_start 点「按钮-开始货币战争」是死点击(exit 不认它),
            # 推进等待节点判残留态 → 点「按钮-关闭」才推进到世界
            'frame': ('货币战争-大厅', '大厅-残留态-run49'),
            'exit': ('on_click_in', '货币战争-大厅', '按钮-关闭'),
        },
        {  # 世界入口(朝露公馆):F 分支按 F,on_polls 等转场到大厅
            'frame': ('大世界', '朝露公馆入口'),
            'exit': ('on_polls', 3),
        },
        {  # 新鲜大厅:逃逸后重新点「按钮-开始货币战争」
            'frame': ('货币战争-大厅', 'lobby'),
            'exit': ('on_click_in', '货币战争-大厅', '按钮-开始货币战争'),
        },
        {
            'frame': ('货币战争-模式选择', 'default'),
            'exit': ('on_click_in', '货币战争-模式选择', '按钮-进入标准博弈'),
        },
        {
            'frame': ('货币战争-难度确认', 'a8'),
            'exit': ('on_click_in', '货币战争-难度确认', '按钮-开始对局'),
        },
        {
            'frame': ('货币战争-简报', 'default'),
            'exit': ('on_click_in', '货币战争-简报', '按钮-下一步'),
        },
        {  # 备战:terminal
            'frame': ('货币战争-备战', 'shop_closed'),
        },
    ]


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """注入 FixtureController 替换 MockController(op 的 controller.click 走剧本推进)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    return ctrl


def _require_screens(test_context: SrTestContext, phases: list[dict]) -> None:
    """剧本里每个 phase 的 frame 截图都必须存在,否则 skip(归档后自动恢复)。"""
    for phase in phases:
        screen_name, state = phase['frame']
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


class TestStartCurrencyWarMatchFlow:
    """StartCurrencyWarMatch 入口流程行为测试。"""

    def test_new_match_a8_reaches_prep(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        phases = _build_phases_new_match_a8()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedStartCurrencyWarMatch(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'未到达备战:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # 每个前进按钮的 click 都落在对应 area 内。
        assert fixture_controller.click_hit_area('货币战争-大厅', '按钮-开始货币战争'), (
            '未点「按钮-开始货币战争」:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.click_hit_area('货币战争-模式选择', '按钮-进入标准博弈')
        assert fixture_controller.click_hit_area('货币战争-难度确认', '按钮-开始对局')
        assert fixture_controller.click_hit_area('货币战争-简报', '按钮-下一步')
        # 健全性:推进到末 phase(备战)。
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'剧本未推进到末 phase:phase_idx={fixture_controller.phase_idx}'
        )
        # 简报词缀读取验证:op 简报分支 read_affixes → ctx.cw_briefing_affixes(A8 最高 4 词缀)
        assert test_context.cw_briefing_affixes, '简报词缀未读取(简报分支没读存)'
        assert len(test_context.cw_briefing_affixes) == 4, (
            f'期望 4 词缀(A8),实际 {test_context.cw_briefing_affixes}'
        )
        # 简报首领候选集读取验证:op 简报分支 read_bosses → ctx.cw_briefing_bosses
        # (ADR-0397:画面 x 序候选集,仅供遥测——不再 copy 进 session 当 plane_bosses;
        # 真值走 CollectPlaneIntel 实采,锁见 test_cw_w219_boss_collect_channel.py)
        assert test_context.cw_briefing_bosses, '简报首领候选集未读取(简报分支没读存)'
        assert len(test_context.cw_briefing_bosses) == 3, (
            f'期望 3 boss(3 位面),实际 {test_context.cw_briefing_bosses}'
        )

    def test_new_match_a5_switches_to_max_rank(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        phases = _build_phases_new_match_a5()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedStartCurrencyWarMatch(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'未到达备战:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # A5 子态先点「返回最高职级」(锁最高难度),再「开始对局」。
        assert fixture_controller.click_hit_area('货币战争-难度确认', '按钮-返回最高职级'), (
            'A5 子态未先点「按钮-返回最高职级」切最高难度:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.click_hit_area('货币战争-难度确认', '按钮-开始对局')
        assert fixture_controller.phase_idx == len(phases) - 1

    def test_residual_lobby_escapes_via_close_and_world(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        """残留大厅态(真帧):点开始不推进 → 点关闭露世界 → F 重进 → 重新点开始到备战。"""
        phases = _build_phases_residual_lobby_escape()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedStartCurrencyWarMatch(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'残留大厅态应逃逸到备战:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'剧本应推进到末 phase(备战):phase_idx={fixture_controller.phase_idx}'
        )
        # 点击次序锁:第 1 次点开始(残留态的死点击,不推进)→ 第 2 个点击是关闭
        # (唯一一次)→ 世界 F 重进后重新点开始。残留态期间绝不重试点开始
        # (判据=大厅锚,不是死按钮文字——死按钮仍 OCR 可见,锚错了就会误判能点)。
        # 注:后续画面的右下角按钮(模式选择/难度确认)坐标与开始钮矩形重叠,
        # 全程按坐标数开始点击会跨屏误伤,故只锁「关闭前」的点击序列。
        start_clicks = _clicks_in_area(fixture_controller, '货币战争-大厅', '按钮-开始货币战争')
        close_clicks = _clicks_in_area(fixture_controller, '货币战争-大厅', '按钮-关闭')
        clicks = fixture_controller.recorded_clicks
        assert len(clicks) >= 2 and start_clicks and clicks[0] in start_clicks, (
            f'第 1 个点击应是残留态的死点击(开始钮):{_fmt_clicks(clicks)}'
        )
        assert len(close_clicks) == 1 and clicks[1] == close_clicks[0], (
            f'第 2 个点击应是唯一一次「按钮-关闭」:{_fmt_clicks(clicks)}'
        )
        assert len(start_clicks) >= 2, (
            f'逃逸后应重新点开始(全程 ≥2 次落在开始钮):{_fmt_clicks(clicks)}'
        )
        # 世界入口真按了 F(防伪绿:F 分支没跑、靠 poll 副作用推进也能 PASS)
        assert test_context.game_config.key_interact in fixture_controller.recorded_btn_taps, (
            f'世界入口应按交互键 F 重进大厅:{fixture_controller.recorded_btn_taps}'
        )


def _clicks_in_area(ctrl: FixtureController, screen_name: str, area_name: str) -> list:
    """落在指定 area 内的点击(按 recorded_clicks 顺序)。"""
    area = ctrl.ctx.screen_loader.get_area(screen_name, area_name)
    if area is None:
        return []
    rect = area.pc_rect
    region = (rect.x1, rect.y1, rect.x2, rect.y2)
    return [
        p for p in ctrl.recorded_clicks
        if FixtureController._pos_in_region(p, region)
    ]


def _fmt_clicks(clicks: list) -> str:
    return ', '.join(f'({p.x},{p.y})' for p in clicks) or '<empty>'
