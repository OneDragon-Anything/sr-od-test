"""货币战争 补给箱识别测试(read_supply_boxes / find_supply_boxes;2026-08-14 首见机制)。

奖励球(晶矿)开启可能掉补给箱落备战席占 1 槽(点「开启」腾槽)。纯 CV 核心
find_supply_boxes TM 匹配:实机 fixture(备战 1-9 槽1 有箱 + 槽2-9 角色)→ 只命中槽1;
合成负例(纯色背景)→ 不命中。分离度实测:箱槽 1.0 vs 角色槽 ≤0.242。
拖动后选中态(蓝光效)降 TM 至 ~0.65-0.69(2026-08-14 拖槽1→槽2 实测)→ 阈值 0.6 覆盖。
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.cw_identity_obs import find_supply_boxes

# 实机截图(1-9 备战,槽1=补给箱,槽2-9=角色;2026-08-14 采集)
_SHOT = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_164308_173490.png'
# 拖箱槽1→槽2 后(箱在槽2 且带选中光效,TM 0.65 档回归用;2026-08-14 采集)
_SHOT_DRAG = r'.debug/sr_od_mcp/screenshot/screenshot_20260814_165941_733433.png'
_BENCH_RECTS = [  # screen_info 备战栏-1..9 pc_rect(ground truth)
    [382, 845, 495, 979], [507, 844, 620, 978], [632, 844, 743, 978],
    [757, 845, 869, 979], [882, 846, 995, 980], [1004, 847, 1118, 978],
    [1132, 846, 1244, 977], [1256, 845, 1368, 979], [1379, 844, 1493, 980],
]


def _slots() -> list[tuple[int, Rect]]:
    return [(i, Rect(*r)) for i, r in enumerate(_BENCH_RECTS, start=1)]


def _load(path: str) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        pytest.skip(f'实机截图 fixture 缺: {path}')
    return img


def test_supply_box_hit_real_screenshot() -> None:
    """实机:槽1 箱子命中,槽2-9(角色)不误报。"""
    hits = find_supply_boxes(_load(_SHOT), _slots())
    assert [idx for idx, _p in hits] == [1], f'应只在槽1 命中,实得 {hits}'
    cx, cy = hits[0][1].x, hits[0][1].y
    assert abs(cx - 438) <= 3 and abs(cy - 912) <= 3, f'开启 center 应≈(438,912),实得 ({cx},{cy})'


def test_supply_box_after_drag_selected_glow() -> None:
    """拖动后(槽2 + 选中光效)仍命中:阈值 0.6 覆盖光效降分(~0.65)。"""
    hits = find_supply_boxes(_load(_SHOT_DRAG), _slots())
    assert [idx for idx, _p in hits] == [2], f'拖后应只在槽2 命中(光效态),实得 {hits}'


def test_supply_box_no_false_positive_on_empty() -> None:
    """合成空槽(纯色 + 噪声)不命中(防 placeholder 误报)。"""
    rng = np.random.default_rng(7)
    blank = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    blank += rng.integers(0, 8, blank.shape, dtype=np.uint8)  # 低方差噪声
    assert find_supply_boxes(blank, _slots()) == []


def test_supply_box_threshold_margin() -> None:
    """分离度:箱槽 val 应超阈值,角色槽远低于(防阈值贴边脆断)。"""
    from sr_od.application.currency_war.cw_identity_obs import (
        _SUPPLY_BOX_TM_THR,
        _get_supply_box_gray,
    )
    tm = _get_supply_box_gray()
    if tm is None:
        pytest.skip('补给箱模板缺(assets/template/currency_war/supply/补给箱.png)')
    gray = cv2.cvtColor(_load(_SHOT), cv2.COLOR_BGR2GRAY)
    box_val, char_max = 0.0, 0.0
    for i, r in enumerate(_BENCH_RECTS, start=1):
        crop = gray[r[1]:r[3], r[0]:r[2]]
        _, mx, _, _ = cv2.minMaxLoc(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED))
        if i == 1:
            box_val = mx
        else:
            char_max = max(char_max, mx)
    assert box_val >= _SUPPLY_BOX_TM_THR + 0.15, f'箱槽 val={box_val:.3f} 应超阈值 +0.15 余量'
    assert char_max <= _SUPPLY_BOX_TM_THR - 0.3, f'角色槽 max={char_max:.3f} 应低于阈值 -0.3 余量'
