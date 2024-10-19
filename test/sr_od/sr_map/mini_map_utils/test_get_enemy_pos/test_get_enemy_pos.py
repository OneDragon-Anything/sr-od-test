from cv2.typing import MatLike
from typing import List

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResultList, MatchResult
from one_dragon.utils import cv2_utils
from sr_od.sr_map import mini_map_utils
from test import SrTestBase


class TestGetEnemyPos(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

    def test_with_enemy_nearby(self):
        mm = self.get_test_image('mm_no_enemy.png')
        self.assertFalse(mini_map_utils.with_enemy_nearby(mm))

    def test_get_enemy_pos(self):
        mm = self.get_test_image('enemy_pos_1.png')
        mm_info = mini_map_utils.analyse_mini_map(mm)
        pos_list = mini_map_utils.get_enemy_pos(mm_info)
        print(pos_list)
        self.assertEquals(1, len(pos_list))
        # self.show_enemy_pos(mm, pos_list)

        mm = self.get_test_image('enemy_pos_2.png')
        mm_info = mini_map_utils.analyse_mini_map(mm)
        pos_list = mini_map_utils.get_enemy_pos(mm_info)
        print(pos_list)
        self.assertEquals(2, len(pos_list))

        mm = self.get_test_image('enemy_pos_3.png')
        mm_info = mini_map_utils.analyse_mini_map(mm)
        pos_list = mini_map_utils.get_enemy_pos(mm_info)
        print(pos_list)
        self.assertEquals(1, len(pos_list))

    def show_enemy_pos(self, mm: MatLike, pos_list: List[Point]):
        cx = mm.shape[1] // 2
        cy = mm.shape[0] // 2
        mrl = MatchResultList(only_best=False)
        for pos in pos_list:
            mrl.append(MatchResult(1, cx + pos.x - 3, cy + pos.y - 3, 7, 7))

        cv2_utils.show_image(mm, mrl, win_name='show_enemy_pos', wait=0)