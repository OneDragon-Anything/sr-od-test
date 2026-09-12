"""共享画面 fixture 态测试 —— 验 ``in_secondary_ui`` 在真实归档截图上能正确识别。

这些是 app 共用的通用画面(合成 被 synthesize_trick_snack 等用;队伍 被战前编队 / world_patrol 等
用),无独立 app 测试文件,故集中在此验画面态识别(标题锚点在真实截图上可匹配)。fixture 缺则 skip。
"""

import pytest

from sr_od.screen_state import common_screen_state
from test.conftest import SrTestContext

# (screen, state, 期望命中的左上角标题词)
SHARED_SCREENS: list[tuple[str, str, str]] = [
    ('合成', '消耗品合成', '合成'),
    ('队伍', '编队', '队伍'),
    ('任务', '全部任务', '任务'),
    ('角色', '详情', '角色详情'),
    ('商店', '推荐', '商店'),
]


class TestSharedScreenFixtures:
    """共享画面:in_secondary_ui 在 fixture 上应命中。"""

    @pytest.mark.parametrize('screen,state,title', SHARED_SCREENS)
    def test_in_secondary_ui(
        self, test_context: SrTestContext, screen: str, state: str, title: str
    ) -> None:
        if not test_context.has_screen(screen, state):
            pytest.skip(f'存档截图缺失:screens/{screen}/{state}.webp')
        img = test_context.load_screen(screen, state)
        assert common_screen_state.in_secondary_ui(test_context, img, title), (
            f'应判定在「{title}」二级页({screen}/{state})'
        )
