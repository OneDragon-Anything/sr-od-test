"""小地图「敌人位置」(get_enemy_pos)测试 —— 读本地 fixture png + 纯函数。"""
from __future__ import annotations

from pathlib import Path

from cv2.typing import MatLike

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult, MatchResultList
from one_dragon.utils import cv2_utils
from sr_od.sr_map import mini_map_utils


def test_with_enemy_nearby(test_image_dir: Path) -> None:
    mm = cv2_utils.read_image(str(test_image_dir / 'mm_no_enemy.png'))
    assert not mini_map_utils.with_enemy_nearby(mm)


def test_get_enemy_pos(test_image_dir: Path) -> None:
    mm = cv2_utils.read_image(str(test_image_dir / 'enemy_pos_1.png'))
    mm_info = mini_map_utils.analyse_mini_map(mm)
    pos_list = mini_map_utils.get_enemy_pos(mm_info)
    print(pos_list)
    assert len(pos_list) == 1

    mm = cv2_utils.read_image(str(test_image_dir / 'enemy_pos_2.png'))
    mm_info = mini_map_utils.analyse_mini_map(mm)
    pos_list = mini_map_utils.get_enemy_pos(mm_info)
    print(pos_list)
    assert len(pos_list) == 2

    mm = cv2_utils.read_image(str(test_image_dir / 'enemy_pos_3.png'))
    mm_info = mini_map_utils.analyse_mini_map(mm)
    pos_list = mini_map_utils.get_enemy_pos(mm_info)
    print(pos_list)
    assert len(pos_list) == 1


def _show_enemy_pos(mm: MatLike, pos_list: list[Point]) -> None:
    """调试辅助:在小地图上画出敌人位置(未在断言中调用,保留备用)。"""
    cx = mm.shape[1] // 2
    cy = mm.shape[0] // 2
    mrl = MatchResultList(only_best=False)
    for pos in pos_list:
        mrl.append(MatchResult(1, cx + pos.x - 3, cy + pos.y - 3, 7, 7))

    cv2_utils.show_image(mm, mrl, win_name='show_enemy_pos', wait=0)
