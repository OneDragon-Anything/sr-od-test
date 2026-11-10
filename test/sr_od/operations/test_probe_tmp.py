"""临时探针:36 格全量点击读名验证(验证后删除)。"""
import sys
import time

sys.path.insert(0, 'src')
sys.path.insert(0, 'sr-od-test')

import cv2

from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from test.conftest import SrTestContext

# 行列解耦版 36 格中心(列 x 恒距 139、行带 4 行)
COL_X = [167, 306, 445, 584, 723, 862, 1001, 1140, 1279]
ROW_Y = [275, 447, 620, 864]
DETAIL_RECT = Rect(1695, 150, 1908, 215)


def test_probe(test_context: SrTestContext) -> None:
    ctx = test_context
    results = []
    for r, ry in enumerate(ROW_Y):
        for c, cx in enumerate(COL_X):
            idx = r * 9 + c + 1
            click_ok = ctx.controller.click(pos=Point(cx, ry), press_time=0.1)
            time.sleep(1.2)
            img = ctx.controller.get_screenshot()
            ocr = ctx.ocr_service.get_ocr_result_list(image=img, rect=DETAIL_RECT, crop_first=False)
            names = [str(o.data).strip() for o in ocr if str(o.data).strip()]
            name = names[1] if len(names) > 1 else (names[0] if names else '(读名失败)')
            results.append(f'{idx:02d} 行{r + 1}列{c + 1} ({cx},{ry}): {name} [click={click_ok}]')
            print(results[-1], flush=True)
    print('=== 汇总 ===')
    print('\n'.join(results))
    assert True
