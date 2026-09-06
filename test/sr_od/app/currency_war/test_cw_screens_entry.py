# -*- coding: utf-8 -*-
"""test_cw_screens_entry 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- test_currency_war_entry: test_currency_war_entry.py
- test_currency_war_entry_flow: test_currency_war_entry_flow.py
- test_briefing_recognizer: test_briefing_recognizer.py
- test_battle_prep_recognizer: test_battle_prep_recognizer.py
- test_currency_war_char_id: test_currency_war_char_id.py
- test_currency_war_invest_strategy_screen: test_currency_war_invest_strategy_screen.py
- test_currency_war_plane_transition_screen: test_currency_war_plane_transition_screen.py
- test_currency_war_supply_box_screen: test_currency_war_supply_box_screen.py
- test_currency_war_supply_screen: test_currency_war_supply_screen.py
- test_currency_war_wish_trial_screen: test_currency_war_wish_trial_screen.py
- test_currency_war_shop: test_currency_war_shop.py
- w518_briefing_telemetry: test_cw_w518_briefing_telemetry.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== test_currency_war_entry ====================

from pathlib import Path
from typing import TYPE_CHECKING

from cv2.typing import MatLike

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def _has_text(ctx: SrTestContext, screen: MatLike, kw: str) -> bool:
    """全屏 OCR,判断关键词是否出现(子串,容 OCR 分词差异)。"""
    texts = [m.data for m in
             ctx.ocr_service.get_ocr_result_list(image=screen, rect=Rect(0, 0, 1920, 1080))]
    return any(kw in t for t in texts)


def test_difficulty_confirm_a5_has_return_max(test_context, test_image_dir: Path) -> None:
    """A5 子态(默认,未在最高):"返回最高职级" 在 → op 应先点它切 A8。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_difficulty_confirm_a5.png'))
    assert _has_text(test_context, screen, '返回最高职级'), 'A5 子态应有"返回最高职级"按钮'
    assert _has_text(test_context, screen, '开始对局')


def test_difficulty_confirm_a8_no_return_max(test_context, test_image_dir: Path) -> None:
    """A8 子态(最高):"返回最高职级" 不在 → op 直接"开始对局"。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_difficulty_confirm_a8.png'))
    assert not _has_text(test_context, screen, '返回最高职级'), 'A8 子态不应有"返回最高职级"'
    assert _has_text(test_context, screen, '开始对局')
    assert _has_text(test_context, screen, 'A8'), '应识别为 A8 子态'


# ==================== test_currency_war_entry_flow ====================

import pytest

from sr_od.application.currency_war.operations.cw_entry.cw_entry_start import  CwEntryStart
from test.conftest import SrTestContext
from test.harness.fixture_controller import  FixtureController, WatchdogOperationMixin, enter_running_state, fast_sleep, reset_running_state


class _WatchedCwEntryStart(WatchdogOperationMixin, CwEntryStart):
    """带看门狗的 CwEntryStart(防 WAIT 段死循环)。"""


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


def _build_phases_train_supply_popup() -> list[dict]:
    """列车补给每日弹窗剧本(真帧锁:2026-08-31 实机建档帧)。

    launch_dead 停机后游戏停在大世界+「列车补给」全屏每日领取弹窗,下一局
    入局链被弹窗挡死 → 「推进到备战阶段」超时失败。剧本:弹窗(点中央徽章
    领取)→ 大厅 → 模式选择 → 难度确认 A8 → 简报 → 备战(转换恢复)。
    """
    return [
        {  # 弹窗:入口 op 领取分支点「按钮-领取补贴」(中央徽章,无 X 关闭钮)
            'frame': ('货币战争-列车补给弹窗', '今日未领取'),
            'exit': ('on_click_in', '货币战争-列车补给弹窗', '按钮-领取补贴'),
        },
        {
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


def _build_phases_jade_detail_popup() -> list[dict]:
    """星琼详情弹窗剧本(真帧锁:2026-09-07 实机卡死事故帧;ADR-0574)。

    列车补给领取点击命中弹窗中央星琼图标 → 货币详情弹窗模态盖场,入口链全部
    背景锚点失明 → 推进循环空烧 60 步超时(修复前事故)。剧本:弹窗(守卫点
    「按钮-关闭X」)→ 大厅 → 模式选择 → 难度确认 A8 → 简报 → 备战(转换恢复)。
    """
    return [
        {  # 弹窗:守卫点「按钮-关闭X」关闭(双锚识别,纯坐标点击)
            'frame': ('货币战争-星琼详情', 'default'),
            'exit': ('on_click_in', '货币战争-星琼详情', '按钮-关闭X'),
        },
        {
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


class TestCwEntryStartFlow:
    """CwEntryStart 入口流程行为测试。"""

    def test_new_match_a8_reaches_prep(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        phases = _build_phases_new_match_a8()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedCwEntryStart(test_context)
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
        # 简报词缀读取验证(W971 P3b:直写 session,ctx 信箱退役):
        # CwScreenBriefing read_affixes → session.briefing_affixes(A8 最高 4 词缀)
        _sess = test_context.cw_match.session
        assert _sess.briefing_affixes, '简报词缀未读取(简报分支没读存)'
        assert len(_sess.briefing_affixes) == 4, (
            f'期望 4 词缀(A8),实际 {_sess.briefing_affixes}'
        )
        # 简报首领读取验证:read_bosses + LCS 清洗 → session.briefing_bosses
        # (位面序真值,ADR-0397 勘误节;消费链 session→state.plane_bosses)
        assert _sess.briefing_bosses, '简报首领候选集未读取(简报分支没读存)'
        assert len(_sess.briefing_bosses) == 3, (
            f'期望 3 boss(3 位面),实际 {_sess.briefing_bosses}'
        )

    def test_new_match_a5_switches_to_max_rank(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        phases = _build_phases_new_match_a5()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedCwEntryStart(test_context)
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
        op = _WatchedCwEntryStart(test_context)
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


    def test_train_supply_popup_claimed_then_reaches_prep(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        """列车补给每日弹窗(真帧):入口 op 领取 → 转换恢复推进到备战。

        守卫锁:移除 op 的 ``_handle_train_supply_popup`` 分支 → 弹窗帧无分支可
        推进 → 本锁红(推进无路,超时失败)。
        """
        phases = _build_phases_train_supply_popup()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedCwEntryStart(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'弹窗领取后未恢复推进到备战:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # 领取点击必须落在中央徽章领取区(不是乱点/点提示文本)。
        assert fixture_controller.click_hit_area(
            '货币战争-列车补给弹窗', '按钮-领取补贴'), (
            '未点「按钮-领取补贴」领取弹窗:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'剧本应推进到末 phase(备战):phase_idx={fixture_controller.phase_idx}'
        )

    def test_jade_detail_popup_closed_then_reaches_prep(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        """星琼详情弹窗(真帧):守卫点「按钮-关闭X」→ 转换恢复推进到备战。

        守卫锁:移除 op 的 ``_handle_jade_detail_popup`` 分支 → 弹窗帧无分支可
        推进 → 本锁红(推进无路,超时失败;ADR-0574)。
        """
        phases = _build_phases_jade_detail_popup()
        _require_screens(test_context, phases)

        fixture_controller.set_phases(phases)
        op = _WatchedCwEntryStart(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'弹窗关闭后未恢复推进到备战:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # 关闭点击必须落在弹窗右上角 X 钮区(不是乱点/误点中央内容)。
        assert fixture_controller.click_hit_area(
            '货币战争-星琼详情', '按钮-关闭X'), (
            '未点「按钮-关闭X」关闭星琼详情弹窗:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'剧本应推进到末 phase(备战):phase_idx={fixture_controller.phase_idx}'
        )

    def test_jade_detail_popup_closed_at_app_entry_then_nav_resumes(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        """大世界+星琼详情弹窗帧(T-98 事故场景):app 首节点 `_enter_lobby`
        守卫分支点 X 关闭 → 重跑节点走「已在 CW」常规分支导航恢复。

        守卫锁:移除 `_enter_lobby` 的星琼弹窗分支,或把弹窗屏收进对局屏集(误判
        「已在对局中」跳过 enter 直交 loop)→ 本锁红。
        """
        from sr_od.application.currency_war.currency_war_app import CurrencyWarApp

        phases = [
            {  # 大世界+弹窗:首节点守卫分支点「按钮-关闭X」
                'frame': ('货币战争-星琼详情', 'default'),
                'exit': ('on_click_in', '货币战争-星琼详情', '按钮-关闭X'),
            },
            {  # 关闭后回落大厅:app 首节点走「已在 CW」常规分支(导航恢复)
                'frame': ('货币战争-大厅', 'lobby'),
            },
        ]
        _require_screens(test_context, phases)
        fixture_controller.set_phases(phases)

        app = CurrencyWarApp(test_context)
        enter_running_state(test_context)
        try:
            with fast_sleep():
                app.screenshot()
                # 节点方法直调语义(同下方列车补给锁):守卫分支返回 round_retry
                # (计入节点预算,ADR-0574),重跑节点才走常规分支。
                first = app._enter_lobby()
                app.screenshot()
                result = app._enter_lobby()
        finally:
            reset_running_state(test_context, app)

        assert first is not None and not first.is_success, (
            f'弹窗帧首轮应返回非成功(守卫分支),实:{first.status if first else None}'
        )
        assert fixture_controller.click_hit_area(
            '货币战争-星琼详情', '按钮-关闭X'), (
            'app 首节点未点「按钮-关闭X」关闭星琼详情弹窗:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert result.is_success, (
            f'弹窗关闭后导航未恢复:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'关闭后应恢复导航到大厅(末 phase):phase_idx={fixture_controller.phase_idx}'
        )

    def test_train_supply_popup_claimed_at_app_entry_then_nav_resumes(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        """大世界+弹窗帧(match2 实锤场景):app 首节点 `_enter_lobby` 前移挂点
        领取 → 恢复导航(下一帧大厅锚命中 → 「已在 CW」常规分支)。

        守卫锁:移除 `_enter_lobby` 的弹窗分支,或把弹窗屏收进对局屏集(误判
        「已在对局中」跳过 enter 直交 loop)→ 本锁红。
        """
        from sr_od.application.currency_war.currency_war_app import CurrencyWarApp

        phases = [
            {  # 大世界+弹窗:首节点前移挂点点「按钮-领取补贴」
                'frame': ('货币战争-列车补给弹窗', '今日未领取'),
                'exit': ('on_click_in', '货币战争-列车补给弹窗', '按钮-领取补贴'),
            },
            {  # 领取后回落大厅:app 首节点走「已在 CW」常规分支(导航恢复)
                'frame': ('货币战争-大厅', 'lobby'),
            },
        ]
        _require_screens(test_context, phases)
        fixture_controller.set_phases(phases)

        app = CurrencyWarApp(test_context)
        enter_running_state(test_context)
        try:
            with fast_sleep():
                app.screenshot()
                # 节点方法直调语义(同 test_cw_w817_recovery_precheck):弹窗分支
                # 返回 round_retry(ADR-0574 改形:RETRY 计节点预算,领取点击永不
                # 落地时有界具名 FAIL;原 WAIT 语义不计 retry 会无界空转)。
                first = app._enter_lobby()
                app.screenshot()
                result = app._enter_lobby()
        finally:
            reset_running_state(test_context, app)

        assert first is not None and not first.is_success, (
            f'弹窗帧首轮应返回非成功(领取分支 round_retry),实:{first.status if first else None}'
        )
        assert result.is_success, (
            f'弹窗领取后导航未恢复:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.click_hit_area(
            '货币战争-列车补给弹窗', '按钮-领取补贴'), (
            'app 首节点未点「按钮-领取补贴」领取弹窗:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.phase_idx == len(phases) - 1, (
            f'领取后应恢复导航到大厅(末 phase):phase_idx={fixture_controller.phase_idx}'
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


# ==================== test_briefing_recognizer ====================

from unittest.mock import MagicMock

import sr_od.application.currency_war.obs.recognizers.briefing_recognizer as mod
from sr_od.application.currency_war.kernel.cw_obs_core import BRIEFING_SCREEN
from sr_od.application.currency_war.obs.recognizers.briefing_recognizer import  BriefingRecognizer


def test_screen_name_matches_briefing() -> None:
    """recognizer 注册的 screen_name = '货币战争-简报'(与 screen_info 一致)。"""
    assert BriefingRecognizer.screen_name == BRIEFING_SCREEN == '货币战争-简报'


def test_recognize_composes_pure_reads(monkeypatch) -> None:
    """recognize 组合纯 reader → dict(affixes / bosses 字段齐全)。"""
    monkeypatch.setattr(mod, 'read_affixes', lambda ctx, screen: ['第二位面强化6', '前后台熄火'])
    monkeypatch.setattr(mod, 'read_bosses', lambda ctx, screen: ['增熵能源集团', '火线动力机甲', '银甲武装公司'])

    out = BriefingRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {
        'affixes': ['第二位面强化6', '前后台熄火'],
        'bosses': ['增熵能源集团', '火线动力机甲', '银甲武装公司'],
    }


def test_recognize_empty_when_unreadable(monkeypatch) -> None:
    """读不到 → 空 list(不伪造;词缀 / boss 缺 area 或 OCR 无果都返 [])。"""
    monkeypatch.setattr(mod, 'read_affixes', lambda ctx, screen: [])
    monkeypatch.setattr(mod, 'read_bosses', lambda ctx, screen: [])

    out = BriefingRecognizer().recognize(MagicMock(), MagicMock(), MagicMock())
    assert out == {'affixes': [], 'bosses': []}


def test_does_not_import_click_based_reader() -> None:
    """纯读观察:模块不导入语义要 click 的 read_affix_effect(recognizer 不 click)。"""
    assert not hasattr(mod, 'read_affix_effect'), 'recognizer 不得复用需先 click 的 read_affix_effect'


# ==================== test_battle_prep_recognizer ====================

from types import SimpleNamespace
from unittest.mock import MagicMock as _test_battle_prep_recognizer_MagicMock

import sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer as _test_battle_prep_recognizer_mod
from sr_od.application.currency_war.kernel.cw_obs_core import SCREEN_NAME
from sr_od.application.currency_war.obs.recognizers.battle_prep_recognizer import  BattlePrepRecognizer


def test_screen_name_matches_battle_prep() -> None:
    """recognizer 注册的 screen_name = '货币战争-备战'(与 screen_info 一致)。"""
    assert BattlePrepRecognizer.screen_name == SCREEN_NAME == '货币战争-备战'


def test_test_battle_prep_recognizer_recognize_composes_pure_reads(monkeypatch) -> None:
    """recognize 组合各纯 reader → dict(gold/phase/hp/streak/deploy/board 字段齐全)。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_gold', lambda ctx, screen: 42)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_read_phase_round_pure', lambda ctx, screen: (2, 5))
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_hp_opt', lambda ctx, screen: 80)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_streak', lambda ctx, screen: 3)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_count', lambda ctx, screen: 4)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deploy_cap', lambda ctx, screen: 5)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_board', lambda ctx, screen: {'仙舟': 2, '猎犬': 1})
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_level', lambda ctx, screen, p, r: 5)
    # 角色识别 reader mock 空(角色识别单测见下;避免 _test_battle_prep_recognizer_MagicMock screen 进 SIFT 崩)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_chars', lambda ctx, screen, templates, level=None: [])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_bench_chars', lambda ctx, screen, templates, level=None: [])
    # 立绘库未加载 → 不产角色(front/back/bench None);装备识别 mock 跳过(equips 注入 BenchChar.equips)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_portrait_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_tm_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_sift_templates', lambda ctx: None)  # owned 栏 SIFT 模板同 mock(recognizer:189)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_supply_boxes', lambda ctx, screen: [])      # B6 补给箱/奖励球 reader 同 mock(_test_battle_prep_recognizer_MagicMock screen 进 cv2 崩)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_reward_spheres', lambda ctx, screen: [])

    out = BattlePrepRecognizer().recognize(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock())
    assert out == {
        'gold': 42, 'phase': (2, 5), 'hp': 80, 'streak': 3,
        'deploy_count': 4, 'deploy_cap': 5, 'level': 5, 'board': {'仙舟': 2, '猎犬': 1},
        'front_line': None, 'back_line': None, 'bench': None, 'owned_equips': None,
        'supply_boxes': None, 'reward_spheres': None,   # B6 新增键(空 reader → None,与 owned_equips 同语义)
    }


def test_recognize_phase_none_when_unreadable(monkeypatch) -> None:
    """phase 纯读读不到 → None(不伪造 (1,1));其余字段仍产出。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_hp_opt', lambda ctx, screen: 100)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_chars', lambda ctx, screen, templates, level=None: [])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_bench_chars', lambda ctx, screen, templates, level=None: [])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_portrait_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_tm_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_sift_templates', lambda ctx: None)  # owned 栏 SIFT 模板同 mock(recognizer:189)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_supply_boxes', lambda ctx, screen: [])      # B6 补给箱/奖励球 reader 同 mock(_test_battle_prep_recognizer_MagicMock screen 进 cv2 崩)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_reward_spheres', lambda ctx, screen: [])

    out = BattlePrepRecognizer().recognize(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock())
    assert out['phase'] is None
    assert out['gold'] == 0
    assert out['front_line'] is None


def test_does_not_import_stateful_readers() -> None:
    """并发安全:模块不导入写全局的 read_phase_round、不导入读写 session 的 read_game_state。"""
    assert not hasattr(_test_battle_prep_recognizer_mod, 'read_phase_round'), '不得复用写 _last_phase_round 全局的 read_phase_round'
    assert not hasattr(_test_battle_prep_recognizer_mod, 'read_game_state'), '不得复用读写 cw_match.session 的 read_game_state'


def test_read_phase_round_pure_parses_dash(monkeypatch) -> None:
    """纯 phase 读:OCR "2-4" → (2, 4)。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_area_rect', lambda ctx, name: _test_battle_prep_recognizer_MagicMock())
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_ocr', lambda ctx, screen, rect: [_test_battle_prep_recognizer_MagicMock(data='2-4')])
    assert _test_battle_prep_recognizer_mod._read_phase_round_pure(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock()) == (2, 4)


def test_read_phase_round_pure_none_on_garbage(monkeypatch) -> None:
    """纯 phase 读:OCR 无数字 → None(不兜底、不写全局)。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_area_rect', lambda ctx, name: _test_battle_prep_recognizer_MagicMock())
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_ocr', lambda ctx, screen, rect: [_test_battle_prep_recognizer_MagicMock(data='乱七八糟无数字')])
    assert _test_battle_prep_recognizer_mod._read_phase_round_pure(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock()) is None


def _char(char_id: str, position_pref: str, slot: int = 1) -> SimpleNamespace:
    """轻量 mock BenchChar(recognize 用 char_id/position_pref/slot;equips 默认 [],deployed 由 recognize 注入)。"""
    return SimpleNamespace(char_id=char_id, position_pref=position_pref, slot=slot, equips=[])


def test_recognize_identifies_chars(monkeypatch) -> None:
    """templates 已加载 + SIFT 识别 → front_line / back_line / bench 产 BenchChar(含 char_id)。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_hp_opt', lambda ctx, screen: 100)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_chars', lambda ctx, screen, templates, level=None: [
        _char('藿藿', 'front', slot=1), _char('希儿', 'back', slot=1),
    ])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_bench_chars', lambda ctx, screen, templates, level=None: [_char('飞霄', 'back', slot=1)])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_portrait_templates', lambda ctx: 'templates')   # 非 None → 产角色
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_tm_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_sift_templates', lambda ctx: None)  # owned 栏 SIFT 模板同 mock(recognizer:189)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_supply_boxes', lambda ctx, screen: [])      # B6 补给箱/奖励球 reader 同 mock(_test_battle_prep_recognizer_MagicMock screen 进 cv2 崩)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_reward_spheres', lambda ctx, screen: [])          # 装备跳过 → equips=[]

    out = BattlePrepRecognizer().recognize(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock())
    assert [c.char_id for c in out['front_line']] == ['藿藿']
    assert [c.char_id for c in out['back_line']] == ['希儿']
    assert [c.char_id for c in out['bench']] == ['飞霄']
    # 装备按 slot 注入 BenchChar.equips(equip_grays None → 恒 [],机制见 recognizer docstring)
    assert all(c.equips == [] for c in out['front_line'] + out['back_line'] + out['bench'])


def test_recognize_no_chars_when_templates_none(monkeypatch) -> None:
    """立绘库不可用(ensure_portrait_templates → None)→ 不产角色(三字段 None)。"""
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_gold', lambda ctx, screen: 0)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, '_read_phase_round_pure', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_hp_opt', lambda ctx, screen: 100)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_streak', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_count', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deploy_cap', lambda ctx, screen: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_board', lambda ctx, screen: {})
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_deployed_chars', lambda *a, **k: [])   # 不该被调(templates None 跳过)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_bench_chars', lambda *a, **k: [])
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_portrait_templates', lambda ctx: None)   # 立绘库不可用
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_tm_templates', lambda ctx: None)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'ensure_equip_sift_templates', lambda ctx: None)  # owned 栏 SIFT 模板同 mock(recognizer:189)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_supply_boxes', lambda ctx, screen: [])      # B6 补给箱/奖励球 reader 同 mock(_test_battle_prep_recognizer_MagicMock screen 进 cv2 崩)
    monkeypatch.setattr(_test_battle_prep_recognizer_mod, 'read_reward_spheres', lambda ctx, screen: [])

    out = BattlePrepRecognizer().recognize(_test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock(), _test_battle_prep_recognizer_MagicMock())
    assert out['front_line'] is None
    assert out['back_line'] is None
    assert out['bench'] is None


# ==================== test_currency_war_char_id ====================

from pathlib import Path as _test_currency_war_char_id_Path

from one_dragon.utils import cv2_utils as _test_currency_war_char_id_cv2_utils
from sr_od.application.currency_war.obs.currency_war_char_id import  identify_character, load_avatar_templates

# 备战栏槽位 GT 坐标(同 currency_war_battle_prep.yml;[x1,y1,x2,y2])
BENCH1_RECT = (382, 845, 495, 979)


def test_identify_bench_herta(test_image_dir: _test_currency_war_char_id_Path) -> None:
    """备战屏 bench-1(herta)裁图 → SIFT 匹配头像库应识别为 herta(高置信)。"""
    screen = _test_currency_war_char_id_cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_herta.png'))
    avatar_dir = _test_currency_war_char_id_Path(__file__).parents[5] / 'assets' / 'template' / 'character_avatar'
    templates = load_avatar_templates(avatar_dir)
    assert len(templates) > 50, f'头像模板库应加载 50+ 个(实测 {len(templates)})'

    x1, y1, x2, y2 = BENCH1_RECT
    bench1 = screen[y1:y2, x1:x2]
    cid, score = identify_character(bench1, templates)

    assert cid == 'herta', f'bench-1 应识别为 herta(实测 {cid}, inliers={score})'
    assert score > 10, f'herta 匹配内点应 >10(实测 {score})'


# ==================== test_currency_war_invest_strategy_screen ====================

from typing import TYPE_CHECKING as _test_currency_war_invest_strategy_screen_TYPE_CHECKING

import pytest as _test_currency_war_invest_strategy_screen_pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if _test_currency_war_invest_strategy_screen_TYPE_CHECKING:
    from test.conftest import SrTestContext


SCREEN = '货币战争-投资策略'


@_test_currency_war_invest_strategy_screen_pytest.mark.parametrize('state', ['default', 'card1_selected', 'card3_refreshed'])
def test_invest_strategy_id_mark_true_positive(test_context: SrTestContext, state: str) -> None:
    """真阳性:三态 fixture(未选/选中卡1/刷新卡3)都精准匹配 投资策略屏。"""
    if not test_context.has_screen(SCREEN, state):
        _test_currency_war_invest_strategy_screen_pytest.skip(f'fixture 缺:screens/{SCREEN}/{state}.webp')
    img = test_context.load_screen(SCREEN, state)
    assert get_match_screen_name(test_context, img, screen_name_list=[SCREEN]) == SCREEN


def test_invest_strategy_not_misread_as_battle_prep(test_context: SrTestContext) -> None:
    """无碰撞:投资策略独立屏不被误判 货币战争-备战(无备战 id_mark 元素)。"""
    if not test_context.has_screen(SCREEN, 'default'):
        _test_currency_war_invest_strategy_screen_pytest.skip('fixture 缺:default.webp')
    img = test_context.load_screen(SCREEN, 'default')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) is None


# ==================== test_currency_war_jade_detail_screen ====================

def test_jade_detail_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:星琼详情弹窗 fixture(2026-09-07 事故帧)→ 精准匹配 货币战争-星琼详情。

    双 id_mark(标识-星琼标题 @0.5 + 标识-稀有货币 @0.75)全中才算精准;
    建档坐标 = 方案 §5 实测,MCP analyze_screen 当场验证 is_precise=True。
    """
    if not test_context.has_screen('货币战争-星琼详情', 'default'):
        _test_currency_war_invest_strategy_screen_pytest.skip('fixture 缺:screens/货币战争-星琼详情/default.webp')
    img = test_context.load_screen('货币战争-星琼详情', 'default')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-星琼详情']) == '货币战争-星琼详情', (
        '星琼详情 fixture 应精准匹配(id_mark 星琼标题+稀有货币 双锚全中)'
    )


def test_jade_detail_not_misread_as_sibling_screens(test_context: SrTestContext) -> None:
    """无碰撞:星琼详情帧不被误判同族弹窗/宿主屏(双锚位置约束区分)。

    候选撞车源:列车补给弹窗(同为入口链大世界弹窗,标题区不同屏)与 大厅
    (模态压暗背景下的宿主)。双锚的矩形约束使既有屏凑不齐自家 id_mark → 不精准。
    全屏库双向碰撞由 test_id_mark.py 自动发现机制另行覆盖,此处锁高危邻屏。
    """
    if not test_context.has_screen('货币战争-星琼详情', 'default'):
        _test_currency_war_invest_strategy_screen_pytest.skip('fixture 缺:screens/货币战争-星琼详情/default.webp')
    img = test_context.load_screen('货币战争-星琼详情', 'default')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-列车补给弹窗']) is None, (
        '星琼详情帧不应被误判 货币战争-列车补给弹窗'
    )
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-大厅']) is None, (
        '星琼详情帧(背景压暗)不应被误判 货币战争-大厅'
    )


# ==================== test_currency_war_plane_transition_screen ====================

from typing import TYPE_CHECKING as _test_currency_war_plane_transition_screen_TYPE_CHECKING

import pytest as _test_currency_war_plane_transition_screen_pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name as _test_currency_war_plane_transition_screen_get_match_screen_name

if _test_currency_war_plane_transition_screen_TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_plane_transition_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:位面1->2 过渡 fixture -> 精准匹配 货币战争-位面过渡。"""
    if not test_context.has_screen('货币战争-位面过渡', 'plane_1to2'):
        _test_currency_war_plane_transition_screen_pytest.skip('fixture 缺:screens/货币战争-位面过渡/plane_1to2.webp')
    img = test_context.load_screen('货币战争-位面过渡', 'plane_1to2')
    assert _test_currency_war_plane_transition_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-位面过渡']) == '货币战争-位面过渡', (
        '位面过渡 fixture 应精准匹配 货币战争-位面过渡(id_mark 标识-位面节点2+3 全中)'
    )


def test_plane_transition_not_misread_as_sim_universe(test_context: SrTestContext) -> None:
    """无碰撞:位面过渡 fixture 不被误判模拟宇宙。

    撞车源:sim_uni.yml 有同名 点击空白处继续 area -> 建档前两画面并列
    is_precise=false。组合 id_mark(位面节点2/3 位面 文字)使位面过渡精准命中,
    模拟宇宙无此 id_mark -> 不被误判。
    """
    if not test_context.has_screen('货币战争-位面过渡', 'plane_1to2'):
        _test_currency_war_plane_transition_screen_pytest.skip('fixture 缺:screens/货币战争-位面过渡/plane_1to2.webp')
    img = test_context.load_screen('货币战争-位面过渡', 'plane_1to2')
    # 位面过渡应精准命中自身
    assert _test_currency_war_plane_transition_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-位面过渡']) == '货币战争-位面过渡'
    # 模拟宇宙不应精准命中(无位面节点 id_mark)
    assert _test_currency_war_plane_transition_screen_get_match_screen_name(test_context, img, screen_name_list=['模拟宇宙']) is None, (
        '位面过渡 fixture 不应被误判模拟宇宙(模拟宇宙无位面节点 id_mark)'
    )


# ==================== test_currency_war_supply_box_screen ====================

from typing import TYPE_CHECKING as _test_currency_war_supply_box_screen_TYPE_CHECKING

import pytest as _test_currency_war_supply_box_screen_pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name as _test_currency_war_supply_box_screen_get_match_screen_name

if _test_currency_war_supply_box_screen_TYPE_CHECKING:
    from test.conftest import SrTestContext


_test_currency_war_supply_box_screen_SCREEN = '货币战争-备战-武装箱选择'


def test_supply_box_open_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:武装箱选择 fixture -> 精准匹配 货币战争-备战-武装箱选择。"""
    if not test_context.has_screen(_test_currency_war_supply_box_screen_SCREEN, 'box_open'):
        _test_currency_war_supply_box_screen_pytest.skip('fixture 缺:screens/货币战争-备战-武装箱选择/box_open.webp')
    img = test_context.load_screen(_test_currency_war_supply_box_screen_SCREEN, 'box_open')
    assert _test_currency_war_supply_box_screen_get_match_screen_name(test_context, img, screen_name_list=[_test_currency_war_supply_box_screen_SCREEN]) == _test_currency_war_supply_box_screen_SCREEN, (
        '武装箱选择 fixture 应精准匹配(id_mark 标识-武装箱+标识-请选择 全中)'
    )


def test_supply_box_open_not_misread_as_battle_prep(test_context: SrTestContext) -> None:
    """无碰撞:overlay 盖住备战 id_mark -> 不被误判货币战争-备战。"""
    if not test_context.has_screen(_test_currency_war_supply_box_screen_SCREEN, 'box_open'):
        _test_currency_war_supply_box_screen_pytest.skip('fixture 缺:screens/货币战争-备战-武装箱选择/box_open.webp')
    img = test_context.load_screen(_test_currency_war_supply_box_screen_SCREEN, 'box_open')
    assert _test_currency_war_supply_box_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) is None, (
        '武装箱 overlay 盖备战 id_mark,备战不应精准命中'
    )


# ==================== test_currency_war_supply_screen ====================

from typing import TYPE_CHECKING as _test_currency_war_supply_screen_TYPE_CHECKING

import pytest as _test_currency_war_supply_screen_pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name as _test_currency_war_supply_screen_get_match_screen_name

if _test_currency_war_supply_screen_TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_supply_options_five_column_fixture(test_context: SrTestContext) -> None:
    """正样本:5 选项特例帧 → 动态探测到 **5** 列(禁写死 4/5 的行为证明)。

    fixture ``screens/货币战争-补给/default.png|webp``(1-5 补给,5 张角色卡各带装备:
    银枝/希儿/丹恒·腾荒/飞霄/忘归人——augment 改写特例)。用户口径:补给通常 4 选 1,
    augment 动态改 3-5,列数以 read_supply_options 实际识别为准。
    """
    from sr_od.application.currency_war.obs.cw_node_obs import read_supply_options

    if not test_context.has_screen('货币战争-补给', 'default'):
        _test_currency_war_supply_screen_pytest.skip('fixture 缺:screens/货币战争-补给/default.webp')
    screen = test_context.load_screen('货币战争-补给', 'default')
    opts = read_supply_options(test_context, screen)
    assert len(opts) == 5, f'5 选项特例帧应动态探到 5 列,实际 {len(opts)}:{[o.equip for o, _p in opts]}'
    # 每列装备名非空(装备行定义列);角色按最近 x 配对(roster-validated),
    # OCR 艺术字形变下容忍部分列配空(如「丹恒·腾荒」间隔号连读)——动态列数
    # 与逐列内容透传是本批锁点,名字准确性归 get_char roster 校验上游。
    assert sum(bool(o.char) for o, _p in opts) >= 3, (
        f'5 列中角色配对不足 3(大面积漏读):{[(o.char, o.equip) for o, _p in opts]}')


def test_supply_screen_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:补给 fixture(未选择/已选择)→ 精准匹配 货币战争-补给。"""
    for state in ('未选择', '已选择'):
        if not test_context.has_screen('货币战争-补给', state):
            _test_currency_war_supply_screen_pytest.skip(f'fixture 缺:screens/货币战争-补给/{state}.webp')
    for state in ('未选择', '已选择'):
        img = test_context.load_screen('货币战争-补给', state)
        assert _test_currency_war_supply_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-补给']) == '货币战争-补给', (
            f'补给 fixture({state})应精准匹配 货币战争-补给(id_mark 标识-补给阶段 全中)'
        )


def test_supply_node_prep_not_misread_as_supply(test_context: SrTestContext) -> None:
    """无碰撞:补给节点备战(含「返回补给阶段」按钮)→ 精准匹配 货币战争-备战,非 货币战争-补给。

    防 BuyShopCards 假阳根因复发:备战「返回补给阶段」按钮文本含「补给阶段」,
    但其位置 [1716,51] ≠ 补给标题 id_mark [893,120,1027,230] → 备战不被误判补给。
    """
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        _test_currency_war_supply_screen_pytest.skip('fixture 缺:screens/货币战争-备战/补给节点.webp')
    img = test_context.load_screen('货币战争-备战', '补给节点')
    assert _test_currency_war_supply_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) == '货币战争-备战', (
        '补给节点备战应精准匹配 货币战争-备战'
    )
    assert _test_currency_war_supply_screen_get_match_screen_name(test_context, img, screen_name_list=['货币战争-补给']) is None, (
        '补给节点备战(含返回补给阶段按钮)不应被误判 货币战争-补给(id_mark 位置区分)'
    )


# ==================== test_currency_war_wish_trial_screen ====================

from typing import TYPE_CHECKING as _test_currency_war_wish_trial_screen_TYPE_CHECKING

import pytest as _test_currency_war_wish_trial_screen_pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name as _test_currency_war_wish_trial_screen_get_match_screen_name

if _test_currency_war_wish_trial_screen_TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_wish_trial_screen_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:祈愿试炼 fixture → 精准匹配 货币战争-祈愿试炼。"""
    if not test_context.has_screen('货币战争-祈愿试炼', '祈愿试炼'):
        _test_currency_war_wish_trial_screen_pytest.skip('fixture 缺:screens/货币战争-祈愿试炼/祈愿试炼.webp')
    img = test_context.load_screen('货币战争-祈愿试炼', '祈愿试炼')
    assert _test_currency_war_wish_trial_screen_get_match_screen_name(
        test_context, img, screen_name_list=['货币战争-祈愿试炼']) == '货币战争-祈愿试炼', (
        '祈愿试炼 fixture 应精准匹配(id_mark 标识-祈愿试炼 命中)')


# ==================== test_currency_war_shop ====================

from pathlib import Path as _test_currency_war_shop_Path
from typing import TYPE_CHECKING as _test_currency_war_shop_TYPE_CHECKING

import pytest as _test_currency_war_shop_pytest
from cv2.typing import MatLike as _test_currency_war_shop_MatLike

from one_dragon.base.geometry.rectangle import Rect as _test_currency_war_shop_Rect
from one_dragon.utils import cv2_utils as _test_currency_war_shop_cv2_utils
from sr_od.application.currency_war.kernel.cw_state import HP_SAFE_THRESHOLD as HP_DANGER
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.obs.cw_observation import  read_game_state, read_hp, read_shop_cards

if _test_currency_war_shop_TYPE_CHECKING:
    from test.conftest import SrTestContext


def _test_currency_war_shop_has_text(ctx: SrTestContext, screen: _test_currency_war_shop_MatLike, kw: str) -> bool:
    """全屏 OCR,判断关键词是否出现(子串,容 OCR 分词差异)。"""
    texts = [m.data for m in
             ctx.ocr_service.get_ocr_result_list(image=screen, rect=_test_currency_war_shop_Rect(0, 0, 1920, 1080))]
    return any(kw in t for t in texts)


def test_read_shop_cards_sift(test_context) -> None:
    """商店屏 → SIFT 读出 5 张牌名 + roster 派生 faction/cost(D-55 OCR→SIFT)。

    read_shop_cards 裁 ``商店牌-1..5`` 肖像区(VLM 定位)→ SIFT ``currency_war/portrait_plaza`` 官方立绘库
    → 规范名;faction/cost 从 roster 派生。fixture ``shop_open.webp`` GT:翡翠/丹恒·腾荒/不死途/飞霄/三月七。
    """
    if not test_context.has_screen('货币战争-备战-开商店', 'shop_open'):
        _test_currency_war_shop_pytest.skip('存档截图缺失:screens/货币战争-备战-开商店/shop_open.webp')
    screen = test_context.load_screen('货币战争-备战-开商店', 'shop_open')
    cards = read_shop_cards(test_context, screen)
    gt = ['翡翠', '丹恒·腾荒', '不死途', '飞霄', '三月七']
    assert [c.name for c in cards] == gt, f'SIFT 牌名错,实际 {[c.name for c in cards]}'
    assert all(c.faction in FACTIONS for c in cards), f'阵营应 roster 派生 ∈ FACTIONS,实际 {[c.faction for c in cards]}'
    assert all(c.cost >= 1 for c in cards), f'cost 应 roster 派生 ≥1,实际 {[c.cost for c in cards]}'


def test_read_game_state_prep(test_context, test_image_dir: _test_currency_war_shop_Path) -> None:
    """备战屏 → read_game_state 读 gold/plane/round/board/shop + level 启发式(打印实测值)。"""
    screen = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))
    state = read_game_state(test_context, screen)
    print(f'\n[game state] gold={state.gold} hp={state.hp} level={state.level} '
          f'plane={state.plane} round={state.round_num} board={state.board}')
    assert 0 <= state.gold <= 400, f'gold 越界 {state.gold}'
    assert 1 <= state.level <= 10, f'level 越界 {state.level}'
    assert 1 <= state.plane <= 3, f'plane 越界 {state.plane}'


def test_read_hp_shop_state(test_context, test_image_dir: _test_currency_war_shop_Path) -> None:
    """HP 只在 shop **关闭**态显示右上角(shop 开启态该区空 → 默认 100)。

    多样本确认(2026-08-03):5 张 shop-关闭态全读到真 HP(80/80/80/29/84)、shop-开启态该区空。
    回归 guard:锁住 ``BuyShopCards``「shop 关闭帧读 hp 覆盖 state.hp」修复的前提 —— 改 read_hp /
    shop 流程后重跑本测试,确保 HP 读取行为不回归。
    """
    closed = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_closed.png'))        # shop 关,hp=84
    lowhp = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_closed_lowhp.png'))  # shop 关,hp=29
    open_shop = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))           # shop 开,hp 区空
    assert read_hp(test_context, closed) == 84
    assert read_hp(test_context, lowhp) == 29
    assert read_hp(test_context, lowhp) < HP_DANGER, '低血(< HP_DANGER)应能让保血触发'
    assert read_hp(test_context, open_shop) == 100, 'shop 开 → HP 区空 → 默认 100'


def test_prep_anchor_buyexp_present_on_prep_absent_elsewhere(test_context, test_image_dir: _test_currency_war_shop_Path) -> None:
    """``BuyShopCards`` 非备战屏守卫(2026-08-04 plane2 投资策略叠层实测)的前提:

    备战锚点「购买经验」在**备战屏有**(→ 守卫不触发,正常买牌)、**非备战屏无**(→ 守卫
    round_fail 快速退出,交主循环 loop 接手处理事件叠层;否则 round_retry 在非商店屏浪费
    max_retry 次后才恢复)。用可靠 fixture(备战 shop 屏 + 大厅)锁守卫检测前提,改守卫/OCR
    后重跑确保不回归。
    """
    prep = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_shop.png'))        # 备战屏(shop 开,底部有「购买经验」)
    assert _test_currency_war_shop_has_text(test_context, prep, '购买经验'), '备战屏应有「购买经验」→ 守卫不触发,正常买牌'
    lobby = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / 'currency_war_lobby.png'))      # 货币战争大厅(非备战)
    assert not _test_currency_war_shop_has_text(test_context, lobby, '购买经验'), '非备战屏无「购买经验」→ 守卫应 round_fail 退出,交主循环处理'


def test_read_deploy_paddle_cap_and_count(test_context, test_image_dir: _test_currency_war_shop_Path) -> None:
    """D-139:「区域-部署数」paddle「X/Y」→ read_deployed_count=X、read_deploy_cap=Y(同源)。

    回归 guard:refactor(read_deployed_count → _read_deploy_paddle[0])不破坏 X 读取;新增
    read_deploy_cap 给真 cap(非 level 估,deploy_bench D-139 用)。paddle 在小 stylized 区偶 OCR 漏 →
    读不到=None 合法(调用方 fallback),故只断言「读到则 sane」+ X<=Y。打印实测值供多样本核实。
    """
    from sr_od.application.currency_war.obs.cw_observation import  read_deploy_cap, read_deployed_count
    for name in ('currency_war_shop.png', 'currency_war_prep_closed.png',
                 'currency_war_prep_herta.png'):
        screen = _test_currency_war_shop_cv2_utils.read_image(str(test_image_dir / name))
        x = read_deployed_count(test_context, screen)
        y = read_deploy_cap(test_context, screen)
        print(f'\n[deploy paddle {name}] deployed={x} cap={y}')
        if x is not None:
            assert 0 <= x <= 9, f'deployed 越界 {x}'
        if y is not None:
            assert 1 <= y <= 9, f'cap 越界 {y}'
        if x is not None and y is not None:
            assert x <= y, f'deployed({x}) > cap({y})'


# (D-84 test_tracked_bench_chars_seeds_identity 已随 tracked_bench 旧名账退役删除:
#  被锁的 _tracked_bench_chars helper 及其唯一消费点(旧回退播种)同批移除,
#  事故帧回归锁迁至 test_cw4_shop_line.py 守卫族。)


# ==================== w518_briefing_telemetry ====================

import inspect

from sr_od.application.currency_war.operations.cw_screen import cw_screen_briefing
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def test_handle_briefing_telemetry_wiring_in_source() -> None:
    """接线锁:简报 op 真调 record_exogenous(kind='briefing')(落盘点唯一源)。

    W971 P3b:简报 op 迁至 cw_flow.CwScreenBriefing(HandleBriefing 退役),锁随迁。
    """
    src = inspect.getsource(cw_screen_briefing.CwScreenBriefing.handle)
    assert 'record_exogenous(' in src, 'CwScreenBriefing 未接 briefing 遥测落账(W518 断链)'
    assert "'briefing'" in src, "落账 kind 不是 'briefing'(须与原位面简报先例同口径)"
