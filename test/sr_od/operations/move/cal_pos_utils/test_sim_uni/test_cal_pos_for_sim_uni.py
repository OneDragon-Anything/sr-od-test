import os

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cal_utils
from one_dragon.utils.log_utils import log
from sr_od.operations.move import cal_pos_utils
from sr_od.operations.move.cal_pos_utils import VerifyPosInfo
from sr_od.sr_map import large_map_utils, mini_map_utils
from test import SrTestBase
from test.sr_od.operations.move.cal_pos_utils.cal_pos_utils_test_case import TestCaseLoader, TestCase


class TestCalPosForSimUni(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)

        # 预热 方便后续统计耗时
        self.ctx.init_for_world_patrol()
        self.test_case_loader = TestCaseLoader(self.ctx)

    @property
    def cases_path(self) -> str:
        return os.path.join(self.sub_package_path, 'test_cases.yml')

    def test_cal_pos_for_sim_uni(self):
        fail_cnt = 0
        case_list = self.test_case_loader.read_test_cases(self.cases_path)
        for case in case_list:
            # if case.unique_id !='P02_YLL6_R05_CXHL_01':
            #     continue
            result = self.run_one_test_case(case, show=False)
            if not result:
                fail_cnt += 1
                log.info('%s 计算坐标失败', case.unique_id)

        # performance_recorder.log_all_performance()
        self.assertEqual(0, fail_cnt)

    def run_one_test_case(self, case: TestCase, show: bool = False) -> bool:
        """
        执行一个测试样例
        :param case: 测试样例
        :param show: 显示
        :return: 是否与预期一致
        """
        mm = self.get_test_image(case.image_name)

        lm_info = self.ctx.map_data.get_large_map_info(case.region)
        lm_rect = large_map_utils.get_large_map_rect_by_pos(lm_info.gray.shape, mm.shape[:2], case.possible_pos)
        mm_info = mini_map_utils.analyse_mini_map(mm)
        verify = VerifyPosInfo(last_pos=Point(case.possible_pos[0], case.possible_pos[1]),
                               max_distance=case.possible_pos[1])

        result = cal_pos_utils.sim_uni_cal_pos(
            self.ctx,
            lm_info=lm_info,
            mm_info=mm_info,
            running=case.running,
            real_move_time=case.real_move_time,
            lm_rect=lm_rect,
            verify=verify,
            show=show
        )
        pos = None if result is None else result.center
        if show:
            cv2.waitKey(0)

        if pos is None:
            log.error('%s 当前计算坐标为空', case.unique_id)
            return False
        else:
            dis = cal_utils.distance_between(pos, case.pos)
            log.info('%s 当前计算坐标为 %s 与目标点 %s 距离 %.2f', case.unique_id, pos, case.pos, dis)
            return dis < 5
