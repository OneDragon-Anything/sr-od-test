"""战斗画面状态识别测试(需完整 SR 数据栈,CI 无数据 skip)。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from one_dragon.base.screen.screen_utils import FindAreaResultEnum, find_area_in_screen
from one_dragon.utils import cv2_utils
from sr_od.screen_state import battle_screen_state

pytestmark = pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈（screen 配置/模板/OCR），CI clean checkout 无；本地有数据则跑',
)


def test_is_battle_fail(test_context, test_image_dir: Path) -> None:
    screen = cv2_utils.read_image(str(test_image_dir / 'normal_world_battle_fail.png'))
    assert battle_screen_state.is_battle_fail(test_context, screen)


def test_battle_reward_exit_btn_area_matches_full_ocr(test_context) -> None:
    """战斗胜利结算「退出关卡按钮」pc_rect 须罩住全图 OCR 检测框(ADR-0215 重叠契约)。

    背景:crop_first 默认翻转 False 后,文本 area 的 pc_rect 必须容纳全图 OCR
    检测框 ≥70%(以检测框为基准),否则 OCR 读到但被区域过滤静默失配
    (2026-08-24 历战余响实锤,旧 rect y2=975 罩不住检测框 y2=987)。
    fixture:screens/战斗画面/挑战成功.webp,'退出关卡' 检测框 (664,958,764,987)。
    """
    if not test_context.has_screen('战斗画面', '挑战成功'):
        pytest.skip('缺 fixture: screens/战斗画面/挑战成功.webp')
    screen = test_context.load_screen('战斗画面', '挑战成功')
    area = test_context.screen_loader.get_area('战斗画面', '退出关卡按钮')
    assert area is not None and area.is_text_area
    assert find_area_in_screen(test_context, screen, area) == FindAreaResultEnum.TRUE, \
        '退出关卡按钮 未命中:pc_rect 与全图 OCR 检测框重叠率不足(ADR-0215 契约回归)'
