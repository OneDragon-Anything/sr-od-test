"""r256 简易武装箱建档测试(summon hook 首捕)。"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))

from sr_od.application.currency_war.cw_identity_obs import (  # noqa: E402
    _get_crate_gray,
    find_supply_boxes,
)


class _R:
    """槽位 rect duck 类型(x1/y1/x2/y2)。"""

    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2


_EVIDENCE = Path(__file__).parent / 'screens' / '货币战争-武装箱' / 'r256_summon_42d15804.png'


def _imread(p: Path):
    """imdecode 读图(cv2.imread 吃不了中文路径)。"""
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)


def test_crate_template_matches_evidence():
    """简易武装箱模板在证据截图的 slot3 命中(≥0.7),
    邻槽(角色)不命中(<0.5)。"""
    tm = _get_crate_gray()
    assert tm is not None, '模板文件缺失'
    img = _imread(_EVIDENCE)
    assert img is not None, '证据截图缺失(本地档)'
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    slot3 = gray[815:1000, 600:780]
    s3 = cv2.minMaxLoc(cv2.matchTemplate(slot3, tm, cv2.TM_CCOEFF_NORMED))[1]
    assert s3 >= 0.7, f'slot3 应命中,得 {s3:.3f}'
    slot4 = gray[815:1000, 740:920]
    s4 = cv2.minMaxLoc(cv2.matchTemplate(slot4, tm, cv2.TM_CCOEFF_NORMED))[1]
    assert s4 < 0.5, f'邻槽不应命中,得 {s4:.3f}'


def test_find_supply_boxes_multi_template():
    """find_supply_boxes 多模板(补给箱+武装箱)任一命中即报。"""
    img = _imread(_EVIDENCE)
    if img is None:
        return   # 证据是本地档,无此文件时跳过
    slots = [(3, _R(600, 815, 780, 1000))]
    out = find_supply_boxes(img, slots)
    assert out and out[0][0] == 3, f'武装箱槽应报,得 {out}'
