"""小地图「是否受击」(is_under_attack)测试 —— 读本地 fixture png + 纯函数。"""
from __future__ import annotations

from pathlib import Path

from one_dragon.utils import cv2_utils
from sr_od.sr_map import mini_map_utils


def test_under_attack(test_image_dir: Path) -> None:
    mm = cv2_utils.read_image(str(test_image_dir / 'under_1.png'))
    assert mini_map_utils.is_under_attack(mm, show=False, strict=False)

    mm = cv2_utils.read_image(str(test_image_dir / 'under_2.png'))
    assert mini_map_utils.is_under_attack(mm, show=False, strict=True)

    mm = cv2_utils.read_image(str(test_image_dir / 'under_3.png'))
    assert not mini_map_utils.is_under_attack(mm, show=False)

    mm = cv2_utils.read_image(str(test_image_dir / 'under_4.png'))
    assert not mini_map_utils.is_under_attack(mm, show=False, strict=True)

    mm = cv2_utils.read_image(str(test_image_dir / 'under_5.png'))
    assert not mini_map_utils.is_under_attack(mm, show=False, strict=True)
