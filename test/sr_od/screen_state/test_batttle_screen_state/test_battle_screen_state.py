"""战斗画面状态识别测试(需完整 SR 数据栈,CI 无数据 skip)。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from one_dragon.utils import cv2_utils
from sr_od.screen_state import battle_screen_state

pytestmark = pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈（screen 配置/模板/OCR），CI clean checkout 无；本地有数据则跑',
)


def test_is_battle_fail(test_context, test_image_dir: Path) -> None:
    screen = cv2_utils.read_image(str(test_image_dir / 'normal_world_battle_fail.png'))
    assert battle_screen_state.is_battle_fail(test_context, screen)
