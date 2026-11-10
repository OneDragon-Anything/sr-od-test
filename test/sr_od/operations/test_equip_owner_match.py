"""占用者角标识别基准测试(方法矩阵锦标赛固化,光锥/遗器双界面)。

fixture = 3 帧光锥替换实机整屏 + 2 帧遗器替换实机整屏(无损 webp,
``equip_owner_match/``)+ 既有光锥替换 fixture;真值 = 逐卡位人工看图标注
(光锥 48 用例:21 真角标 + 27 无角标;遗器 33 用例:11 真角标 + 22 无角标,
遗器真值另经 mys 全角色明细穿着反向索引双源确认)。
锁的内容(出处 ``src/sr_od/operations/equip_owner_match.py``):

- 真角标 → 正确中文角色名(皮肤归一「三月七」、开拓者男女变体不混);
- 无角标卡面(纯卡面装饰/星空背景)→ None 零误报 —— 这是装备 op
  「不抢」语义的正确性底线(误报会认出幽灵占用者阻止换装);
- 真角标内点分布(光锥 18-61 / 遗器 16-30)与无角标内点上限
  (光锥 ≤11 / 遗器 ≤8)= 内点阈 15、Lowe 比值 0.7 与直方图/歧义闸在
  两界面的标定依据 —— 调整 ``equip_owner_match`` 的任何匹配参数先过
  本基准,方法替换先在此基准上对比。
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

# 遗器替换列表卡矩形(cell = 识别器输出的卡 x1,y1,x2,y2;4 列 x1≈39/162/285/408,
# 行带 y 随内容不规整,故逐卡实测而非网格公式)。
# 真值 = 人工看图标注 × mys 穿着反向索引双源一致。
_RELIC_TOP_TRUTH = {
    (39, 180, 159, 340): '布洛妮娅',  # 置顶=该角色穿着中件(详情页实锤)
    (166, 195, 290, 309): '开拓者·欢愉·女',  # 重掷动画遮罩卡,角标未被污染
    (408, 328, 528, 488): '停云',
    (162, 625, 282, 785): '星期日',
}
_RELIC_TOP_NONE_CELLS = [
    (285, 180, 405, 340), (408, 180, 528, 340),
    (39, 328, 159, 488), (162, 328, 282, 488), (285, 328, 405, 488),
    (39, 478, 159, 638), (162, 478, 282, 638), (285, 478, 405, 638),
    (408, 478, 528, 638), (37, 496, 160, 607),
    (39, 625, 159, 785), (285, 625, 405, 785), (408, 625, 528, 785),
    (39, 774, 159, 934), (162, 774, 282, 934), (285, 774, 405, 934),
    (408, 774, 528, 934),
]
# 翔鹰头盔区帧(列表滚动中段):12 件在穿副本中的 7 件 + 5 件仓库
_RELIC_HAWKS_TRUTH = {
    (408, 202, 528, 362): '花火',
    (39, 350, 159, 510): '希露瓦',
    (162, 350, 282, 510): '瓦尔特',
    (285, 350, 405, 510): '佩拉',
    (39, 499, 159, 659): '灵砂',
    (285, 499, 405, 659): '银狼',
    (285, 649, 405, 809): '卡芙卡',
}
_RELIC_HAWKS_NONE_CELLS = [
    (408, 350, 528, 510), (162, 499, 282, 659), (408, 499, 528, 659),
    (162, 649, 282, 809), (408, 649, 528, 809),
]

_FRAMES: dict[str, np.ndarray] = {}


def _frame(name: str) -> np.ndarray:
    """帧缓存:各测试共享同一次解码。"""
    if name not in _FRAMES:
        _FRAMES[name] = cv2_utils.read_image(str(_FIXTURE_DIR / name))
    return _FRAMES[name]


def _cone_badge_rect(x: int, y: int) -> Rect:
    """卡左上角 → 角标窗(与 LightConeReplaceRecognizer 的卡内偏移一致)。"""
    return Rect(x + 95, y + 9, x + 139, y + 53)


def _relic_badge_rect(cell: tuple[int, int, int, int]) -> Rect:
    """卡矩形 → 角标窗(与 RelicReplaceRecognizer 的卡内偏移一致)。"""
    x1, y1, x2, _y2 = cell
    return Rect(x2 - 55, y1 + 10, x2 + 6, y1 + 62)


def _cone_cases() -> tuple[list[tuple[str, Rect, str]], list[tuple[str, Rect]]]:
    """光锥用例:(帧, 角标窗, 期望名) 正例 + (帧, 角标窗) 负例。"""
    positives: list[tuple[str, Rect, str]] = []
    for (r, c), cn in _PAGE_TRUTH.items():
        positives.append(('page_replace_full.webp',
                          _cone_badge_rect(_COLS[c], _ROWS[r]), cn))
    for (r, c), cn in _PAGE_TRUTH.items():
        name = '三月七' if (r, c) == (0, 0) else cn
        positives.append(('page_skin_owner.webp',
                          _cone_badge_rect(_COLS[c], _ROWS[r]), name))
    positives.append(('__cone_fixture__', _cone_badge_rect(97, 197), '黄泉'))

    negatives = [('page_replace_full.webp', _cone_badge_rect(_COLS[c], _ROWS[r]))
                 for r in range(4) for c in range(9) if (r, c) not in _PAGE_TRUTH]
    negatives.append(('bag_cone_list.webp', _cone_badge_rect(375, 454)))
    return positives, negatives


def _relic_cases() -> tuple[list[tuple[str, Rect, str]], list[tuple[str, Rect]]]:
    """遗器用例:同光锥结构,cell → 角标窗换算不同(遗器角标在卡右上角)。"""
    positives = [(('relic_page_top.png'), _relic_badge_rect(cell), cn)
                 for cell, cn in _RELIC_TOP_TRUTH.items()]
    positives += [(('relic_page_hawks.png'), _relic_badge_rect(cell), cn)
                  for cell, cn in _RELIC_HAWKS_TRUTH.items()]
    negatives = [(('relic_page_top.png'), _relic_badge_rect(cell))
                 for cell in _RELIC_TOP_NONE_CELLS]
    negatives += [(('relic_page_hawks.png'), _relic_badge_rect(cell))
                  for cell in _RELIC_HAWKS_NONE_CELLS]
    return positives, negatives


def test_owner_true_badges() -> None:
    """真角标:占用者中文名逐一正确(光锥 0 漏 0 误 / 遗器 0 漏 0 误)。"""
    cone_pos, _ = _cone_cases()
    relic_pos, _ = _relic_cases()
    failures: list[str] = []
    for name, rect, expect in cone_pos + relic_pos:
        img = (cv2_utils.read_image(str(_CONE_FIXTURE)) if name == '__cone_fixture__'
               else _frame(name))
        got, inliers = match_owner(img, rect)
        if got != expect:
            failures.append(f'{name}{rect}: got={got}({inliers}) expect={expect}')
    assert not failures, '\n'.join(failures)


def test_owner_no_badge_is_none() -> None:
    """无角标卡面:全部诚实 None(零误报,假占用者会击穿「不抢」语义)。"""
    _, cone_neg = _cone_cases()
    _, relic_neg = _relic_cases()
    failures: list[str] = []
    for name, rect in cone_neg + relic_neg:
        got, inliers = match_owner(_frame(name), rect)
        if got is not None:
            failures.append(f'{name}{rect}: got={got}({inliers}), 应为 None')
    assert not failures, '\n'.join(failures)
