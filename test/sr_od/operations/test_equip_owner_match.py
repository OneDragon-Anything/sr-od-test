"""占用者角标识别基准测试(方法矩阵锦标赛固化)。

fixture = 3 帧实机整屏(无损 webp,``equip_owner_match/``)+ 既有光锥替换
fixture;真值 = 逐卡位人工看图标注(48 用例:21 真角标 + 27 无角标)。
锁的内容(出处 ``src/sr_od/operations/equip_owner_match.py``):

- 真角标 → 正确中文角色名(皮肤归一「三月七」、开拓者男女变体不混);
- 无角标卡面(纯卡面装饰/星空背景)→ None 零误报 —— 这是装备 op
  「不抢」语义的正确性底线(误报会认出幽灵占用者阻止换装);
- 真角标内点 18-61 / 无角标卡面内点 ≤11 的分布 = 内点阈 15、Lowe 比值
  0.7 与直方图/歧义闸的标定依据 —— 调整 ``equip_owner_match`` 的任何
  匹配参数先过本基准,方法替换先在此基准上对比。
"""

from pathlib import Path

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.operations.equip_owner_match import match_owner

_FIXTURE_DIR = Path(__file__).parent / 'equip_owner_match'
_CONE_FIXTURE = Path(__file__).parent / 'equip_light_cone' / 'replace_target_row0_col0.webp'

# 替换列表卡网格:9 列(x=97+139i)× 4 行(y=197/370/543/717),光锥页标定
_COLS = [97 + 139 * i for i in range(9)]
_ROWS = [197, 370, 543, 717]

# 整页真值:(行, 列) → 中文角色名。page_replace_full 与 page_skin_owner 同页,
# 仅 (0,0) 的装备者换为三月七(皮肤态,归一后同名)
_PAGE_TRUTH = {
    (0, 0): '布洛妮娅', (0, 1): '星期日', (0, 4): '停云', (0, 5): '缇宝',
    (1, 2): '艾丝妲', (1, 3): '开拓者·同谐·女', (2, 2): '花火', (2, 3): '阮•梅',
    (2, 4): '知更鸟', (2, 5): '寒鸦',
}

_FRAMES: dict[str, np.ndarray] = {}


def _frame(name: str) -> np.ndarray:
    """帧缓存:三条测试共享同一次解码。"""
    if name not in _FRAMES:
        _FRAMES[name] = cv2_utils.read_image(str(_FIXTURE_DIR / name))
    return _FRAMES[name]


def _badge_rect(x: int, y: int) -> Rect:
    """卡左上角 → 角标窗(与 LightConeReplaceRecognizer 的卡内偏移一致)。"""
    return Rect(x + 95, y + 9, x + 139, y + 53)


def _positive_cases() -> list[tuple[str, int, int, str]]:
    """(帧, 卡 x, 卡 y, 期望中文名);__cone_fixture__ = 既有光锥 fixture 帧。"""
    cases: list[tuple[str, int, int, str]] = []
    for (r, c), cn in _PAGE_TRUTH.items():
        cases.append(('page_replace_full.webp', _COLS[c], _ROWS[r], cn))
    for (r, c), cn in _PAGE_TRUTH.items():
        cases.append(('page_skin_owner.webp', _COLS[c], _ROWS[r],
                      '三月七' if (r, c) == (0, 0) else cn))
    cases.append(('__cone_fixture__', 97, 197, '黄泉'))
    return cases


def _negative_cases() -> list[tuple[str, int, int]]:
    """无角标卡位(其余 26 个格位)+ 背包列表的无主件。"""
    cases = [('page_replace_full.webp', _COLS[c], _ROWS[r])
             for r in range(4) for c in range(9) if (r, c) not in _PAGE_TRUTH]
    cases.append(('bag_cone_list.webp', 375, 454))
    return cases


def test_owner_true_badges() -> None:
    """真角标:占用者中文名逐一正确(0 漏 0 误)。"""
    failures: list[str] = []
    for name, x, y, expect in _positive_cases():
        img = (cv2_utils.read_image(str(_CONE_FIXTURE)) if name == '__cone_fixture__'
               else _frame(name))
        got, inliers = match_owner(img, _badge_rect(x, y))
        if got != expect:
            failures.append(f'{name}({x},{y}): got={got}({inliers}) expect={expect}')
    assert not failures, '\n'.join(failures)


def test_owner_no_badge_is_none() -> None:
    """无角标卡面:全部诚实 None(零误报,假占用者会击穿「不抢」语义)。"""
    failures: list[str] = []
    for name, x, y in _negative_cases():
        got, inliers = match_owner(_frame(name), _badge_rect(x, y))
        if got is not None:
            failures.append(f'{name}({x},{y}): got={got}({inliers}), 应为 None')
    assert not failures, '\n'.join(failures)
