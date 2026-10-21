"""count_eidolon_locks 挂锁计数:真实截图条带 fixtures 锁定行为。

星魂两态(已获得白亮无锁/未获得暗图标+挂锁章)下 eidolon_count = 6 - 锁数;
fixtures = 实机星魂页 6 个锁位区 60x60 拼条(银狼 E3 / 真珠 E0 / 布洛妮娅 E6,
2026-10-21 采集),模板 = assets/template/account_profile/eidolon_lock。
"""
from pathlib import Path

from one_dragon.base.matcher.template_matcher import TemplateMatcher
from one_dragon.base.screen.template_loader import TemplateLoader
from one_dragon.utils import cv2_utils

from sr_od.application.account_profile.account_profile_core import count_eidolon_locks

FIXTURES = Path(__file__).parent / 'fixtures'
# 条带内第 i 个锁位 tile 的矩形(60x60 逐个拼接)
RECTS: list[tuple[int, int, int, int]] = [(i * 60, 0, (i + 1) * 60, 60) for i in range(6)]
EXPECTED: dict[str, int] = {'silverwolf_e3': 3, 'zhenzhu_e0': 6, 'bronya_e6': 0}


def test_count_eidolon_locks_fixtures() -> None:
    """锁计数 = 各角色实机命臂数:混合态(3/6)、全锁(6)、全亮(0)。"""
    tm = TemplateMatcher(TemplateLoader())
    for name, want in EXPECTED.items():
        screen = cv2_utils.read_image(str(FIXTURES / (name + '.webp')))
        got = count_eidolon_locks(tm, screen, RECTS)
        assert got == want, f'{name}: locks={got}, want={want}'
