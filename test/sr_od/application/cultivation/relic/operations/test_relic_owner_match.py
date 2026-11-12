"""遗器替换列表「占用者角标识别」基准测试。

fixture = 2 帧遗器替换实机整屏(equip_relic/ 目录);真值 = 逐卡位人工看图
标注(33 用例:11 真角标 + 22 无角标,遗器真值另经 mys 全角色明细穿着反向
索引双源确认)。拆分自 test_equip_owner_match(批次B 遗器/光锥分家,光锥侧
见 test_light_cone_owner_match)。锁的内容(出处
``src/sr_od/application/cultivation/relic/relic_list_recognizer.py``
的 match_owner):

- 真角标 → 正确中文角色名(开拓者变体不混);
- 无角标卡面 → None 零误报 —— 装备 op「不抢」语义的正确性底线;
- 遗器标定(2026-11-10 实机 3 帧审计):遗器角标直径 ≈40px(小于光锥 44px),
  真角标内点 16-30、无角标卡面内点 4-8 —— 阈 15 两侧余量 +1/-7,
  同一阈值在两界面成立。
"""

from pathlib import Path

import numpy as np

from one_dragon.base.geometry.rectangle import Rect
from one_dragon.utils import cv2_utils
from sr_od.application.cultivation.relic.relic_list_recognizer import match_owner

_FIXTURE_DIR = Path(__file__).parent / 'equip_relic'

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


def _relic_badge_rect(cell: tuple[int, int, int, int]) -> Rect:
    """卡矩形 → 角标窗(与 RelicReplaceRecognizer 的卡内偏移一致)。"""
    x1, y1, x2, _y2 = cell
    return Rect(x2 - 55, y1 + 10, x2 + 6, y1 + 62)


def _relic_cases() -> tuple[list[tuple[str, Rect, str]], list[tuple[str, Rect]]]:
    """遗器用例:(帧, 角标窗, 期望名) 正例 + (帧, 角标窗) 负例。"""
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
    """真角标:占用者中文名逐一正确(遗器 11 正例 0 漏 0 误)。"""
    relic_pos, _ = _relic_cases()
    failures: list[str] = []
    for name, rect, expect in relic_pos:
        got, inliers = match_owner(_frame(name), rect)
        if got != expect:
            failures.append(f'{name}{rect}: got={got}({inliers}) expect={expect}')
    assert not failures, '\n'.join(failures)


def test_owner_no_badge_is_none() -> None:
    """无角标卡面:全部诚实 None(零误报,假占用者会击穿「不抢」语义)。"""
    _, relic_neg = _relic_cases()
    failures: list[str] = []
    for name, rect in relic_neg:
        got, inliers = match_owner(_frame(name), rect)
        if got is not None:
            failures.append(f'{name}{rect}: got={got}({inliers}), 应为 None')
    assert not failures, '\n'.join(failures)
