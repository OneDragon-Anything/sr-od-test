"""SimUniApp 模拟宇宙 guide 入口 + 旷宇纷争面板态测试(纯 guide_data + fixture,不跑游戏)。

覆盖:
- ``transport`` 节点依赖的 guide entry(旷宇纷争 / 差分宇宙 / 前往模拟宇宙)应能解析。
- 旷宇纷争入口 fixture → ``in_secondary_ui('旷宇纷争')`` 判定在旷宇纷争 tab。

不跑游戏 / 截图(模拟宇宙挑战消耗体力,核心流程不 mock)。
"""

import pytest
from test.conftest import SrTestContext

from one_dragon.utils.i18_utils import gt
from sr_od.screen_state import common_screen_state


class TestSimUniApp:
    """模拟宇宙:guide 入口解析契约 + 入口面板态。"""

    def test_guide_entry_resolves(self, test_context: SrTestContext) -> None:
        """transport 节点依赖的 guide entry(旷宇纷争 / 差分宇宙 / 前往模拟宇宙)应能解析。"""
        guide = test_context.guide_data

        tab = guide.best_match_tab_by_name(gt('旷宇纷争', 'game'))
        assert tab is not None, 'guide 无「旷宇纷争」tab(sim_universe transport 依赖)'

        category = guide.best_match_category_by_name(gt('差分宇宙', 'game'), tab)
        assert category is not None, 'guide「旷宇纷争」下无「差分宇宙」category'

        mission = guide.best_match_mission_by_name('前往模拟宇宙', category)
        assert mission is not None, 'guide「差分宇宙」下无「前往模拟宇宙」mission(transport 拿不到)'

    def test_kuangyu_entry_in_secondary_ui(self, test_context: SrTestContext) -> None:
        """旷宇纷争入口 fixture → in_secondary_ui('旷宇纷争') 判定在旷宇纷争 tab。"""
        if not test_context.has_screen('星际和平指南', '旷宇纷争'):
            pytest.skip('存档截图缺失:screens/星际和平指南/旷宇纷争.webp')
        screen = test_context.load_screen('星际和平指南', '旷宇纷争')
        assert common_screen_state.in_secondary_ui(test_context, screen, '旷宇纷争'), (
            '应判定在「旷宇纷争」tab'
        )
