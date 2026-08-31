"""货币战争角色识别(char_id)测试。

覆盖 ``currency_war_char_id.identify_character``:对备战屏填充槽位裁图,SIFT 特征匹配
``character_avatar`` 模板库 → 识别角色。实测 bench-1 为 herta(脸部独特,高置信命中)。
配饰/半身角色会判 None(低置信,见 design);本测只断言可靠命中的 herta。


出处:docs/develop/currency_war/decisions/0247-sift-two-phase-lazy-ransac.md;docs/develop/currency_war/decisions/0281-back-layout-level-model.md(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from pathlib import Path

from one_dragon.utils import cv2_utils
from sr_od.application.currency_war.obs.currency_war_char_id import (
    identify_character,
    load_avatar_templates,
)

# 备战栏槽位 GT 坐标(同 currency_war_battle_prep.yml;[x1,y1,x2,y2])
BENCH1_RECT = (382, 845, 495, 979)


def test_identify_bench_herta(test_image_dir: Path) -> None:
    """备战屏 bench-1(herta)裁图 → SIFT 匹配头像库应识别为 herta(高置信)。"""
    screen = cv2_utils.read_image(str(test_image_dir / 'currency_war_prep_herta.png'))
    avatar_dir = Path(__file__).parents[5] / 'assets' / 'template' / 'character_avatar'
    templates = load_avatar_templates(avatar_dir)
    assert len(templates) > 50, f'头像模板库应加载 50+ 个(实测 {len(templates)})'

    x1, y1, x2, y2 = BENCH1_RECT
    bench1 = screen[y1:y2, x1:x2]
    cid, score = identify_character(bench1, templates)

    assert cid == 'herta', f'bench-1 应识别为 herta(实测 {cid}, inliers={score})'
    assert score > 10, f'herta 匹配内点应 >10(实测 {score})'
