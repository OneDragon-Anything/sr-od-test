"""小地图朝向分析(analyse_angle)测试 —— 读本地 fixture png + 纯函数,不依赖 ctx。"""
from __future__ import annotations

from pathlib import Path

from one_dragon.utils import cv2_utils
from sr_od.sr_map import mini_map_utils


def test_analyse_angle(test_image_dir: Path) -> None:
    mini_map = cv2_utils.read_image(str(test_image_dir / '0.png'))
    angle = mini_map_utils.analyse_angle(mini_map)
    if angle > 180:
        angle = 360 - angle
    assert abs(angle) <= 2
