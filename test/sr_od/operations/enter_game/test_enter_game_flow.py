"""EnterGame 多节点流程测试(fixture 驱动,从 ZZZ 同步、SR 适配)。

覆盖 SR EnterGame 的三条 happy-path:

1. 已登录态:进入游戏/点击进入 →(click 文本-点击进入)→ 大世界/普通 (terminal)
2. 国服账号密码登录:手机号登录 →(click 国服-账号密码 tab)→ 账号密码-旧
   →(输入账密 + click 国服-账号密码进入游戏)→ 大世界/普通 (terminal)
3. 切换账号(force_login,switch=True):点击进入 →(click 按钮-登出)→ 退出弹窗
   →(click 按钮-退出,保留记录)→ 选账号 →(click 按钮登陆其他账号)→ 手机号登录
   → 账号密码-旧 →(输账密 + click 进游戏)→ 大世界/普通 (terminal)

验证:

- op 完整跑完 ``execute()`` 并成功完成;
- 关键流程 click 被记录(文本-点击进入 / 国服-账号密码 / 按钮-登出 / 按钮-退出 /
  按钮登陆其他账号 / 国服-账号密码进入游戏 等);
- 账密 / 切换分支还验证 mock ``keyboard.type`` 输入了账号 + 密码(recorded_inputs)。

从 ZZZ ``test_enter_game_flow.py`` 同步。ZZZ 的 EnterGame 状态机复杂(资源下载 /
多次进入点击 / B服 / 国际服),SR 简单。安全验证(账号风险)分支未覆盖(op 无法自动
过验证,需人工)。

缺 fixture 时 skip(而非 error),fixture 采到后自动恢复运行。
"""

from __future__ import annotations

import pytest

from one_dragon.base.config.basic_game_config import TypeInputWay
from sr_od.operations.enter_game.enter_game import EnterGame
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)


class _WatchedEnterGame(WatchdogOperationMixin, EnterGame):
    """带看门狗的 EnterGame(看门狗通过混入覆盖 ``_execute_one_round``)。"""


def _build_phases() -> list[dict]:
    """构造 SR 已登录态 happy-path 剧本。

    - 点击进入:唯一流程 click 是 ``文本-点击进入``(在 ``check_screen`` 节点经
      ``round_by_find_and_click_area`` 触发);click 落在该 area 的 pc_rect 内即推进。
    - 大世界:op 检测 ``角色图标`` → ``round_success('大世界')`` → ``wait_game``
      (``BackToNormalWorldPlus`` 在大世界帧快速 success);terminal,不推进。
    """
    return [
        {
            'frame': ('进入游戏', '点击进入'),
            'exit': ('on_click_in', '进入游戏', '文本-点击进入'),
        },
        {
            'frame': ('大世界', '普通'),
            # terminal:不推进。
        },
    ]


def _build_phases_account_password() -> list[dict]:
    """构造 SR 国服账号密码登录 happy-path 剧本。

    - 手机号登录:``check_screen`` 非 force 分支先找 ``文本-点击进入`` / ``提示-确认``
      (本态都没有)→ 找 ``国服-账号密码`` tab 命中 → 点 tab → ``round_success``
      流转到 ``input_account_password``。
    - 账号密码-旧:``input_account_password`` 点账号/密码输入区 + mock ``keyboard.type``
      输入 + 检测 ``文本-同意-旧`` 点同意 + 点 ``国服-账号密码进入游戏`` → 推进。
      中间的账号区/密码区/同意 click 不在进游戏 area 内,不推进(``on_click_in`` 只认
      进游戏 click);它们仍被 ``recorded_clicks`` 记录。
    - 大世界:terminal。
    """
    return [
        {
            'frame': ('进入游戏', '手机号登录'),
            'exit': ('on_click_in', '进入游戏', '国服-账号密码'),
        },
        {
            'frame': ('进入游戏', '账号密码-旧'),
            'exit': ('on_click_in', '进入游戏', '国服-账号密码进入游戏'),
        },
        {
            'frame': ('大世界', '普通'),
            # terminal:不推进。
        },
    ]


def _build_phases_switch_account() -> list[dict]:
    """构造 SR 切换账号(force_login)happy-path 剧本(switch=True 触发)。

    - 点击进入:force 分支检测 ``文本-点击进入`` 命中 → 点 ``按钮-登出`` → 弹出退出弹窗。
    - 退出弹窗:force 分支 ``标题-退出登录``(背后点击进入仍命中)→ ``logout_with_account_kept``
      点 ``按钮-退出并保留登陆记录``(不推进)+ ``按钮-退出``(推进)。
    - 选账号:``choose_other_account`` 点 ``按钮-登陆其他账号`` → 手机号登录。
    - 手机号登录 → 账号密码-旧:``check_screen``(choose_other_account 后 already_login 仍 False)
      force else 无 ``按钮-登陆其他账号`` → 公共 ``国服-账号密码`` tab → ``input_account_password``
      输账密 + 点 ``国服-账号密码进入游戏``。
    - 大世界:terminal。
    """
    return [
        {
            'frame': ('进入游戏', '点击进入'),
            'exit': ('on_click_in', '进入游戏', '按钮-登出'),
        },
        {
            'frame': ('进入游戏-退出登陆', '退出弹窗'),
            'exit': ('on_click_in', '进入游戏-退出登陆', '按钮-退出'),
        },
        {
            'frame': ('进入游戏-选择账号', '选账号'),
            'exit': ('on_click_in', '进入游戏-选择账号', '按钮-登陆其他账号'),
        },
        {
            'frame': ('进入游戏', '手机号登录'),
            'exit': ('on_click_in', '进入游戏', '国服-账号密码'),
        },
        {
            'frame': ('进入游戏', '账号密码-旧'),
            'exit': ('on_click_in', '进入游戏', '国服-账号密码进入游戏'),
        },
        {
            'frame': ('大世界', '普通'),
            # terminal:不推进。
        },
    ]


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """注入 FixtureController 并 pin 键盘输入方式(避免写真实 OS 剪贴板)。

    用 ``monkeypatch.setattr`` 改写 ``controller`` / ``type_input_way``,pytest 在
    测试结束后自动还原 —— 避免污染 session 级 ``test_context``(否则后续测试拿到
    FixtureController 而非 MockController,且其 screenshot 忽略 mock_screenshot)。
    """
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # 强制走 keyboard.type 分支,避免 PcClipboard.copy_and_paste 写真实剪贴板。
    monkeypatch.setattr(
        test_context.game_config,
        'type_input_way',
        TypeInputWay.INPUT.value.value,
    )
    return ctrl


class TestEnterGameFlow:
    """EnterGame 端到端流程测试。"""

    def test_enter_game_reaches_big_world(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
    ) -> None:
        # 缺 fixture 时 skip(而非 error),采到后自动恢复运行,无需改代码。
        if not test_context.has_screen('进入游戏', '点击进入'):
            pytest.skip('存档截图缺失:screens/进入游戏/点击进入.webp')
        if not test_context.has_screen('大世界', '普通'):
            pytest.skip('存档截图缺失:screens/大世界/普通.webp')

        # 载入剧本
        fixture_controller.set_phases(_build_phases())

        # 单实例 + switch=False → force_login=False,直接走已登录态进入。
        op = _WatchedEnterGame(test_context, switch=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        # 核心断言:op 成功完成。
        assert result.success, (
            f'EnterGame 未成功完成:status={result.status}'
            f';最后 phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )

        # 关键流程 click 被记录到:「文本-点击进入」area 内至少一次 click。
        assert fixture_controller.click_hit_area('进入游戏', '文本-点击进入'), (
            '未记录到「文本-点击进入」流程 click:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )

        # 健全性:op 已消费到剧本末 phase(大世界)。
        assert fixture_controller.phase_idx == len(_build_phases()) - 1, (
            f'剧本未推进到末 phase:phase_idx={fixture_controller.phase_idx}'
        )

    def test_enter_game_input_account_password(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 缺 fixture 时 skip。
        if not test_context.has_screen('进入游戏', '手机号登录'):
            pytest.skip('存档截图缺失:screens/进入游戏/手机号登录.webp')
        if not test_context.has_screen('进入游戏', '账号密码-旧'):
            pytest.skip('存档截图缺失:screens/进入游戏/账号密码-旧.webp')
        if not test_context.has_screen('大世界', '普通'):
            pytest.skip('存档截图缺失:screens/大世界/普通.webp')

        # mock 账号密码(input_account_password 检查非空,否则 round_fail「未配置账号密码」)。
        monkeypatch.setattr(test_context.game_account_config, 'account', '13800000000')
        monkeypatch.setattr(test_context.game_account_config, 'password', 'test_password')

        fixture_controller.set_phases(_build_phases_account_password())

        # switch=False + 单实例 → force_login=False,直接走账密检测分支。
        op = _WatchedEnterGame(test_context, switch=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'EnterGame 未成功完成:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # 流程 click:点了「国服-账号密码」tab + 「国服-账号密码进入游戏」。
        assert fixture_controller.click_hit_area('进入游戏', '国服-账号密码'), (
            '未记录到「国服-账号密码」tab click:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        assert fixture_controller.click_hit_area(
            '进入游戏', '国服-账号密码进入游戏'
        ), (
            '未记录到「国服-账号密码进入游戏」click:'
            f'{_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # mock keyboard.type 输入了账号 + 密码(recorded_inputs)。
        assert len(fixture_controller.recorded_inputs) >= 2, (
            f'未输入账号密码:recorded_inputs={fixture_controller.recorded_inputs}'
        )

    def test_enter_game_switch_account(
        self,
        test_context: SrTestContext,
        fixture_controller: FixtureController,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # 缺 fixture 时 skip。
        for screen_name, state in [
            ('进入游戏', '点击进入'),
            ('进入游戏-退出登陆', '退出弹窗'),
            ('进入游戏-选择账号', '选账号'),
            ('进入游戏', '手机号登录'),
            ('进入游戏', '账号密码-旧'),
            ('大世界', '普通'),
        ]:
            if not test_context.has_screen(screen_name, state):
                pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')

        # mock 账号密码(input_account_password 检查非空)。
        monkeypatch.setattr(test_context.game_account_config, 'account', '18928573369')
        monkeypatch.setattr(test_context.game_account_config, 'password', 'moyijie920.')

        fixture_controller.set_phases(_build_phases_switch_account())

        # switch=True → force_login=True,走切换账号分支。
        op = _WatchedEnterGame(test_context, switch=True)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(test_context)
        try:
            with fast_sleep():
                result = op.execute()
        finally:
            reset_running_state(test_context, op)

        assert result.success, (
            f'EnterGame 未成功完成:status={result.status}'
            f';phase_idx={fixture_controller.phase_idx}'
            f';recorded_clicks={_fmt_clicks(fixture_controller.recorded_clicks)}'
        )
        # 关键流程 click:登出 → 退出 → 登陆其他账号 → 账密进游戏。
        assert fixture_controller.click_hit_area('进入游戏', '按钮-登出')
        assert fixture_controller.click_hit_area('进入游戏-退出登陆', '按钮-退出')
        assert fixture_controller.click_hit_area('进入游戏-选择账号', '按钮-登陆其他账号')
        assert fixture_controller.click_hit_area('进入游戏', '国服-账号密码进入游戏')
        # 输入了账密(mock keyboard.type)。
        assert len(fixture_controller.recorded_inputs) >= 2, (
            f'未输入账号密码:recorded_inputs={fixture_controller.recorded_inputs}'
        )


def _fmt_clicks(clicks: list) -> str:
    return ', '.join(f'({p.x},{p.y})' for p in clicks) or '<empty>'
