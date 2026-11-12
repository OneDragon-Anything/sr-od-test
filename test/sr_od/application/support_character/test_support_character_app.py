"""SupportCharacterApp 支援角色奖励 画面引用 + 漫游签证面板态测试。

覆盖:
- ``('菜单', '更多按钮')`` / ``('漫游签证', '按钮-支援奖励领取位')`` area 应在
  screen_info 存在。
- 漫游签证面板 fixture → ``in_secondary_ui('漫游签证')`` 判定在漫游签证页。

fixture(screens/):
- ``漫游签证/角色展示.webp``:漫游签证面板 角色展示 tab(支援角色 飞霄 / 遐蝶 / 黄泉)。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.screen_state import common_screen_state

# SupportCharacterApp 的省略号检测裁这个 area(_click_ellipsis / _click_profile);
# 领取奖励位走 漫游签证 area(2026-09-02 由硬编码 Point(1862,358) 迁移)
APP_AREA_REFS: list[tuple[str, str]] = [
    ('菜单', '更多按钮'),
    ('漫游签证', '按钮-支援奖励领取位'),
]


class TestSupportCharacterApp:
    """支援角色奖励:画面引用 + 省略号检测 + 漫游签证面板态。"""

    def test_app_area_refs_exist(self, test_context: SrTestContext) -> None:
        """``('菜单', '更多按钮')`` 应在 screen_info 存在(省略号检测靠它)。"""
        by_screen: dict[str, set[str]] = {}

        def has(screen_name: str, area_name: str) -> bool:
            if screen_name not in by_screen:
                info = test_context.screen_loader.get_screen(screen_name)
                by_screen[screen_name] = {a.area_name for a in info.area_list}
            return area_name in by_screen[screen_name]

        for screen_name, area_name in APP_AREA_REFS:
            assert has(screen_name, area_name), (
                f'support_character 引用的 area 不存在:{screen_name}/{area_name}'
            )

    def test_profile_in_secondary_ui(self, test_context: SrTestContext) -> None:
        """漫游签证面板 fixture → in_secondary_ui('漫游签证') 判定在漫游签证页。"""
        if not test_context.has_screen('漫游签证', '角色展示'):
            pytest.skip('存档截图缺失:screens/漫游签证/角色展示.webp')
        screen = test_context.load_screen('漫游签证', '角色展示')
        assert common_screen_state.in_secondary_ui(test_context, screen, '漫游签证'), (
            '应判定在「漫游签证」页'
        )
