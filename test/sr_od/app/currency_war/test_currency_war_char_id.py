"""货币战争角色识别(char_id)测试。

覆盖 ``currency_war_char_id.identify_character``:对备战屏填充槽位裁图,SIFT 特征匹配
``character_avatar`` 模板库 → 识别角色。实测 bench-1 为 herta(脸部独特,高置信命中)。
配饰/半身角色会判 None(低置信,见 design);本测只断言可靠命中的 herta。
"""

from pathlib import Path

from sr_od.application.currency_war.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)
from test import SrTestBase

# 备战栏槽位 GT 坐标(同 currency_war_battle_prep.yml;[x1,y1,x2,y2])
BENCH1_RECT = (382, 845, 495, 979)


class TestCurrencyWarCharId(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_identify_bench_herta(self):
        """备战屏 bench-1(herta)裁图 → SIFT 匹配头像库应识别为 herta(高置信)。"""
        screen = self.get_test_image('currency_war_prep_herta.png')
        avatar_dir = Path(__file__).parents[5] / 'assets' / 'template' / 'character_avatar'
        templates = load_avatar_templates(avatar_dir)
        self.assertGreater(len(templates), 50, f'头像模板库应加载 50+ 个(实测 {len(templates)})')

        x1, y1, x2, y2 = BENCH1_RECT
        bench1 = screen[y1:y2, x1:x2]
        cid, score = identify_character(bench1, templates)

        self.assertEqual(cid, 'herta', f'bench-1 应识别为 herta(实测 {cid}, inliers={score})')
        self.assertGreater(score, 10, f'herta 匹配内点应 >10(实测 {score})')
