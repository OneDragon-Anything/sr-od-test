"""NamelessHonorApp 无名勋礼画面引用契约 + 画面态测试(纯 screen_info + fixture,不跑游戏)。

覆盖:
- 各节点 ``round_by_find_and_click_area`` / ``round_by_click_area`` 引用的 ``('无名勋礼', area)``
  应在 screen_info 存在(改名 / 删 area → 节点点击失效)。
- ``in_secondary_ui('无名勋礼')``:无名勋礼面板 fixture → 判定在「无名勋礼」二级页
  (``_check_screen_after_reward`` 靠它确认所在页)。

fixture(screens/):
- ``无名勋礼/奖励.webp``:无名勋礼 奖励 tab(tab1),等级轨 30→40,本周经验 3250/8000,
  750/800,无名客的荣勋(付费轨)未解锁,剩余 8 天。奖励 tab 有红点 + 一键领取可见。
- ``无名勋礼/任务.webp``:任务 tab(tab2),本周任务/本期任务列表,追踪按钮。
- ``无名勋礼/无名勋礼-奖励.webp`` / ``无名勋礼-任务.webp``:上版本实拍(历史态,等级轨 19→30)。

注:节点含消耗型领奖 + 红点判定,需 running 状态,不 mock ``execute``。模板类的
``get_phone_menu_item_pos(NAMELESS_HONOR)`` / ``get_nameless_honor_tab_pos`` 走模板匹配
非 area 引用,不在此校验。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.nameless_honor.nameless_honor_app import NamelessHonorApp
from sr_od.application.sr_application import SrApplication
from sr_od.screen_state import common_screen_state

# NamelessHonorApp 各节点引用的 (screen_name, area_name)(均在 '无名勋礼' screen,2026-08-15 从菜单屏迁出)
APP_AREA_REFS: list[tuple[str, str]] = [
    ('无名勋礼', '按钮-开启无名勋礼'),  # _click_tab_2(版本更新首次)
    ('无名勋礼', '按钮-任务-一键领取'),  # _claim_task
    ('无名勋礼', '按钮-点击空白处关闭'),  # _claim_task / _check_screen_after_reward
    ('无名勋礼', '按钮-奖励-一键领取'),  # _claim_reward
    ('无名勋礼', '按钮-奖励-取消'),  # _check_screen_after_reward
    ('无名勋礼-等级加速弹窗', '按钮-点击空白处关闭'),  # _check_screen_after_reward(弹窗提示位 y≈737,与主面板同名 area y≈945 坐标异)
]


class _DirectNamelessHonor(NamelessHonorApp):
    """绕过游戏窗口前置的 NamelessHonorApp(仅调单节点方法,不 execute)。"""

    def __init__(self, ctx) -> None:
        SrApplication.__init__(
            self, ctx, 'nameless_honor', op_name='无名勋礼',
            need_check_game_win=False, run_record=None,
        )


class TestNamelessHonorApp:
    """无名勋礼:画面引用契约 + 画面态。"""

    def test_app_area_refs_exist(self, test_context: SrTestContext) -> None:
        """各节点引用的 ``('无名勋礼', area)`` 应在 screen_info 存在(改名 / 删 area → 节点点击失效)。"""
        by_screen: dict[str, set[str]] = {}

        def has(screen_name: str, area_name: str) -> bool:
            if screen_name not in by_screen:
                info = test_context.screen_loader.get_screen(screen_name)
                by_screen[screen_name] = {a.area_name for a in info.area_list}
            return area_name in by_screen[screen_name]

        for screen_name, area_name in APP_AREA_REFS:
            assert has(screen_name, area_name), (
                f'nameless_honor 引用的 area 不存在:{screen_name}/{area_name}'
            )

    def test_panel_in_secondary_ui(self, test_context: SrTestContext) -> None:
        """无名勋礼面板 fixture → in_secondary_ui 判定在「无名勋礼」二级页。

        ``_check_screen_after_reward`` 靠 ``in_secondary_ui('无名勋礼')`` 判断是否还在无名勋礼页;
        fixture 是真实的无名勋礼 奖励 tab(左上角标题含「无名勋礼」),故应为 True。
        """
        if not test_context.has_screen('无名勋礼', '奖励'):
            pytest.skip('存档截图缺失:screens/无名勋礼/奖励.webp')
        screen = test_context.load_screen('无名勋礼', '奖励')
        assert common_screen_state.in_secondary_ui(test_context, screen, '无名勋礼'), (
            '应判定在「无名勋礼」二级页'
        )

    def test_after_reward_levelup_popup_closed(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run 48:一键领取后弹「无名勋礼等级加速」弹窗 → 新候选命中点关闭,WAIT。

        背景(2026-08-27 run 48 实机,日志 19:09:22-28):领取奖励点击成功后弹该
        说明弹窗,旧三候选(secondary UI/奖励-取消/点击空白处关闭)全不命中 →
        「未知画面状态」×4 → op 失败。修复=补弹窗独立屏候选(命中→点提示位
        →round_wait 重跑本节点等回主界面)。真实 fixture 帧(测试仓
        ``screens/无名勋礼-等级加速弹窗/等级加速弹窗.webp``)作输入。
        """
        if not test_context.has_screen('无名勋礼-等级加速弹窗', '等级加速弹窗'):
            pytest.skip('存档截图缺失:screens/无名勋礼-等级加速弹窗/等级加速弹窗.webp')

        op = _DirectNamelessHonor(test_context)
        op.last_screenshot = test_context.load_screen('无名勋礼-等级加速弹窗', '等级加速弹窗')

        clicks: list[tuple[str, str]] = []

        def _fake_find_and_click(self, screen, screen_name, area_name, *args, **kwargs):
            if screen_name == '无名勋礼-等级加速弹窗' and area_name == '按钮-点击空白处关闭':
                clicks.append((screen_name, area_name))
                return self.round_success(status=f'{screen_name}-{area_name}')
            return self.round_wait(status=f'未找到 {area_name}')

        monkeypatch.setattr(
            NamelessHonorApp, 'round_by_find_and_click_area', _fake_find_and_click
        )

        result = op._check_screen_after_reward()

        # 弹窗帧不走 secondary UI / 主面板候选,新候选命中 → WAIT 等回主界面。
        assert result.is_success is False, (
            f'弹窗候选命中应 round_wait 非成功,status={result.status}'
        )
        assert result.status == '无名勋礼-等级加速弹窗-按钮-点击空白处关闭', (
            f'应点弹窗独立屏的关闭提示位,status={result.status}'
        )
        assert len(clicks) == 1, f'应恰好点一次关闭提示位,实际 {clicks}'

    def test_after_reward_panel_candidates_still_first(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """主面板帧(secondary UI 命中)不受新候选影响,仍走原成功路径。"""
        if not test_context.has_screen('无名勋礼', '奖励'):
            pytest.skip('存档截图缺失:screens/无名勋礼/奖励.webp')

        op = _DirectNamelessHonor(test_context)
        op.last_screenshot = test_context.load_screen('无名勋礼', '奖励')

        def _boom(*args, **kwargs):
            raise AssertionError('主面板帧应由 secondary UI 分支接管,不应触达任何点击候选')

        monkeypatch.setattr(NamelessHonorApp, 'round_by_find_and_click_area', _boom)

        result = op._check_screen_after_reward()

        assert result.is_success, f'主面板帧应 round_success,status={result.status}'
