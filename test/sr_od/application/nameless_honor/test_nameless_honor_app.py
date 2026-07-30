"""NamelessHonorApp 无名勋礼画面引用契约 + 画面态测试(纯 screen_info + fixture,不跑游戏)。

覆盖:
- 各节点 ``round_by_find_and_click_area`` / ``round_by_click_area`` 引用的 ``('菜单', area)``
  应在 screen_info 存在(改名 / 删 area → 节点点击失效)。
- ``in_secondary_ui('无名勋礼')``:无名勋礼面板 fixture → 判定在「无名勋礼」二级页
  (``_check_screen_after_reward`` 靠它确认所在页)。

fixture(screens/):
- ``菜单/无名勋礼-奖励.webp``:无名勋礼 奖励 tab(tab1),等级轨 19→30,本周经验 3500/8000,
  0/800,无名客的荣勋(付费轨)未解锁,剩余 25 天。无红点 / 可领(等级 <19)。

注:节点含消耗型领奖 + 红点判定,需 running 状态,不 mock ``execute()``。模板类的
``get_phone_menu_item_pos(NAMELESS_HONOR)`` / ``get_nameless_honor_tab_pos`` 走模板匹配
非 area 引用,不在此校验。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.screen_state import common_screen_state

# NamelessHonorApp 各节点引用的 (screen_name, area_name)(均在 '菜单' screen)
APP_AREA_REFS: list[tuple[str, str]] = [
    ('菜单', '无名勋礼-开启无名勋礼'),  # _click_tab_2(版本更新首次)
    ('菜单', '无名勋礼-任务-一键领取'),  # _claim_task
    ('菜单', '无名勋礼-点击空白处关闭'),  # _claim_task / _check_screen_after_reward
    ('菜单', '无名勋礼-奖励-一键领取'),  # _claim_reward
    ('菜单', '无名勋礼-奖励-取消'),  # _check_screen_after_reward
]


class TestNamelessHonorApp:
    """无名勋礼:画面引用契约 + 画面态。"""

    def test_app_area_refs_exist(self, test_context: SrTestContext) -> None:
        """各节点引用的 ``('菜单', area)`` 应在 screen_info 存在(改名 / 删 area → 节点点击失效)。"""
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
        if not test_context.has_screen('菜单', '无名勋礼-奖励'):
            pytest.skip('存档截图缺失:screens/菜单/无名勋礼-奖励.webp')
        screen = test_context.load_screen('菜单', '无名勋礼-奖励')
        assert common_screen_state.in_secondary_ui(test_context, screen, '无名勋礼'), (
            '应判定在「无名勋礼」二级页'
        )
