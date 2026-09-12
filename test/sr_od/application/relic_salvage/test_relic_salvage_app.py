"""RelicSalvageApp 遗器分解配置 / 画面引用 + fixture 匹配测试(纯 screen_info + fixture,不跑游戏)。

覆盖:
- ``RelicLevelEnum`` 显示值('4星及以下' / '5星及以下')= ``salvage_level`` 用作 area_name,
  应在 ``背包-遗器分解-快速选择`` screen 真实存在(``choose_level`` 靠它点击)。
- 各节点 ``round_by_find_and_click_area`` 引用的 ``(screen, area)`` 应在 screen_info 存在。
- **fixture 匹配**:``click_filter``(按钮-快速选择)在 背包-遗器分解 fixture 命中;``choose_level``
  (4星及以下)在 快速选择 fixture 命中 —— 验 area 真能在真实画面匹配(抓模板 / 文字漂移)。

fixture(screens/):
- ``背包-遗器分解/分解.webp``:遗器分解界面(遗器 2148/3000,可分解 632,智能弃置 / 快速选择 / 分解)。
- ``背包-遗器分解-快速选择/快速选择.webp``:快速选择弹窗(全选已弃置 / 2-5 星及以下 / 确认)。

不依赖游戏 / SrContext 运行态。area 改名 / 删除 / 模板漂移即暴露。
"""

import pytest
from test.conftest import SrTestContext

from sr_od.application.relic_salvage.relic_salvage_app import RelicSalvageApp
from sr_od.application.relic_salvage.relic_salvage_config import RelicLevelEnum

# RelicSalvageApp 各节点 round_by_find_and_click_area 引用的 (screen_name, area_name)
APP_AREA_REFS: list[tuple[str, str]] = [
    ('背包-遗器分解', '按钮-快速选择'),  # click_filter
    ('背包-遗器分解-快速选择', '全选已弃置'),  # choose_abandon
    ('背包-遗器分解-快速选择', '按钮-确认'),  # click_filter_confirm
    ('背包-遗器分解', '按钮-分解'),  # click_salvage
    ('背包-遗器分解', '按钮-分解确认'),  # click_salvage_confirm
]

FILTER_SCREEN = '背包-遗器分解-快速选择'


class TestRelicSalvageApp:
    """遗器分解:配置枚举 + 画面引用契约 + fixture 匹配。"""

    def test_relic_level_enum_values(self) -> None:
        """RelicLevelEnum 显示值(= area_name,choose_level 用)。"""
        assert RelicLevelEnum.LEVEL_4.value.value == '4星及以下'
        assert RelicLevelEnum.LEVEL_5.value.value == '5星及以下'

    def test_salvage_level_enum_matches_screen_areas(self, test_context: SrTestContext) -> None:
        """``salvage_level`` 用作 ``背包-遗器分解-快速选择`` 的 area_name —— RelicLevelEnum 每个值
        应是该 screen 的真实 area(否则 ``choose_level`` 点不到对应等级)。"""
        screen = test_context.screen_loader.get_screen(FILTER_SCREEN)
        area_names = {a.area_name for a in screen.area_list}
        for level in RelicLevelEnum:
            assert level.value.value in area_names, (
                f'RelicLevelEnum {level.name}={level.value.value!r} 不是 {FILTER_SCREEN} 的 area'
            )

    def test_app_area_refs_exist(self, test_context: SrTestContext) -> None:
        """各节点引用的 ``(screen, area)`` 应在 screen_info 存在(改名 / 删 area → 节点点击失效)。"""
        by_screen: dict[str, set[str]] = {}

        def has(screen_name: str, area_name: str) -> bool:
            if screen_name not in by_screen:
                info = test_context.screen_loader.get_screen(screen_name)
                by_screen[screen_name] = {a.area_name for a in info.area_list}
            return area_name in by_screen[screen_name]

        for screen_name, area_name in APP_AREA_REFS:
            assert has(screen_name, area_name), (
                f'relic_salvage 引用的 area 不存在:{screen_name}/{area_name}'
            )

    def test_click_filter_finds_button(self, test_context: SrTestContext) -> None:
        """背包-遗器分解 fixture → click_filter 命中「按钮-快速选择」(area 在真实画面可匹配)。"""
        if not test_context.has_screen('背包-遗器分解', '分解'):
            pytest.skip('存档截图缺失:screens/背包-遗器分解/分解.webp')
        test_context.mock_screen('背包-遗器分解', '分解')
        op = RelicSalvageApp(test_context)
        op.screenshot()
        result = op.click_filter()
        assert result.is_success, f'应命中 按钮-快速选择,实际 status={result.status}'

    def test_choose_level_finds_area(self, test_context: SrTestContext) -> None:
        """快速选择 fixture → choose_level 命中「4星及以下」(默认 salvage_level)。"""
        if not test_context.has_screen('背包-遗器分解-快速选择', '快速选择'):
            pytest.skip('存档截图缺失:screens/背包-遗器分解-快速选择/快速选择.webp')
        test_context.mock_screen('背包-遗器分解-快速选择', '快速选择')
        op = RelicSalvageApp(test_context)
        op.screenshot()
        result = op.choose_level()
        assert result.is_success, f'应命中 4星及以下,实际 status={result.status}'
