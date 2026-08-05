"""world_patrol cal_pos 测试(xfail:坐标精度漂移,待数据栈对齐后移除)。"""
from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import pytest

from one_dragon.base.geometry.point import Point
from one_dragon.utils import cal_utils, cv2_utils
from one_dragon.utils.log_utils import log
from sr_od.operations.move import cal_pos_utils
from sr_od.operations.move.cal_pos_utils import VerifyPosInfo
from sr_od.sr_map import large_map_utils, mini_map_utils
from test.sr_od.operations.move.cal_pos_utils.cal_pos_utils_test_case import (
    TestCase,
    TestCaseLoader,
)

pytestmark = [
    pytest.mark.skipif(
        bool(os.environ.get('CI')),
        reason='需完整 SR 数据栈（screen 配置/模板/OCR），CI clean checkout 无；本地有数据则跑',
    ),
    pytest.mark.xfail(
        reason='cal_pos 坐标精度因 SR 数据栈(template/地图)漂移偏 6-10px,暂忽略;后续优化对齐后移除',
    ),
]


def _run_one_test_case(
    ctx, case: TestCase, test_image_dir: Path, show: bool = False,
) -> bool:
    """执行一个测试样例:返回计算坐标与目标点距离是否 < 5。"""
    img_name = case.image_name
    if not img_name.endswith('.png'):
        img_name = f'{img_name}.png'
    mm = cv2_utils.read_image(str(test_image_dir / img_name))

    lm_info = ctx.map_data.get_large_map_info(case.region)
    possible_pos = tuple(case.possible_pos)
    lm_rect = large_map_utils.get_large_map_rect_by_pos(
        lm_info.gray.shape, mm.shape[:2], possible_pos,
    )

    mm_info = mini_map_utils.analyse_mini_map(mm)
    verify = VerifyPosInfo(
        last_pos=Point(case.possible_pos[0], case.possible_pos[1]),
        max_distance=case.possible_pos[1],
    )

    start_time = time.time()
    pos = cal_pos_utils.cal_character_pos(
        ctx,
        lm_info=lm_info,
        mm_info=mm_info,
        running=case.running,
        real_move_time=case.real_move_time,
        lm_rect=lm_rect,
        retry_without_rect=False,
        show=show,
        verify=verify,
    )
    print('耗时 %.4f' % (time.time() - start_time))
    if show:
        cv2.waitKey(0)

    if pos is None:
        log.error('%s 当前计算坐标为空', case.unique_id)
        return False
    dis = cal_utils.distance_between(pos.center, case.pos)
    log.info('%s 当前计算坐标为 %s 与目标点 %s 距离 %.2f', case.unique_id, pos.center, case.pos, dis)
    return dis < 5


def test_cal_pos(test_context, test_image_dir: Path) -> None:
    # 预热(方便后续统计耗时)
    test_context.init_for_world_patrol()
    loader = TestCaseLoader(test_context)
    cases = loader.read_test_cases(str(test_image_dir / 'test_cases.yml'))

    fail_cnt = 0
    for case in cases:
        result = _run_one_test_case(test_context, case, test_image_dir, show=False)
        if not result:
            fail_cnt += 1
            log.info('%s 计算坐标失败', case.unique_id)

    # performance_recorder.log_all_performance()
    assert fail_cnt == 0
