"""主角光环蓝色光标识别(``find_aura_cursor`` 带内模板匹配 +
``map_aura_x_to_slot`` 槽位映射)fixture 回归。

锁的设计约定(标定依据见 src cw_aura_cursor.py 模块 docstring 与
画面档「标识-主角光环光标」):
- 在场判定:前排四槽头顶带内 TM 命中(蓝色雪花光标 = 主角光环归属
  可视标记),命中中心跨帧稳定(同帧系存档 cx/cy 恒定——位置稳定性回归,
  铁路列车图案先例同款锁法);
- 分离度:语料 74 帧离线扫描实证真阳性 ≥0.806 / 阴性 ≤0.463,阈值 0.7
  落分离带中央;webp 归档帧真阳性仍过阈(压缩劣化不破阈);
- 槽位映射:命中中心 x 落建档「前排-N」槽域 → 槽号 1 基;全槽域外 →
  None(读链漂移宁缺勿造)。

fixture:reward_spheres_15(光标在槽 1)、rail_badge_prep_r4 /
rail_badge_consumed_r4(光标在槽 3)= 货币战争-备战/;
deployed_2star、shop_open = 阴性(带内无光标)。缺帧/缺模板 → skip。
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs.cw_aura_cursor import (
    find_aura_cursor,
    map_aura_x_to_slot,
)

#: 光标搜索带 = 画面档「标识-主角光环光标」pc_rect(建档单一源;
#: 铁路列车图案回归同款硬编码先例)。
_AURA_BAND_RECT = Rect(660, 283, 1260, 345)

#: 前排四槽槽域(画面档「前排-N」pc_rect;映射回归用)。
_SLOT_RECTS = [Rect(677, 329, 810, 467), Rect(823, 329, 951, 467),
               Rect(969, 329, 1097, 467), Rect(1109, 329, 1241, 467)]


def _screens_dir() -> Path:
    """向上定位中央归档库 ``screens/``(同 test_battle_prep_recognizer 手法)。"""
    p = Path(__file__)
    while p != p.parent:
        cand = p / 'screens'
        if cand.is_dir() and (any(cand.glob('*/*.webp')) or any(cand.glob('*/*.png'))):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库')


@cache
def _load_frame(name: str) -> np.ndarray | None:
    """读 fixture 帧(RGB 口径,框架截图同口径);缺失 → None。"""
    f_dir = _screens_dir() / '货币战争-备战'
    for suffix in ('.webp', '.png'):
        f = f_dir / f'{name}{suffix}'
        if f.is_file():
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def _require_frame(name: str) -> np.ndarray:
    img = _load_frame(name)
    if img is None:
        pytest.skip(f'存档截图缺失:screens/货币战争-备战/{name}.webp|png')
    return img


@cache
def _run_find(name: str) -> tuple[float, int, int] | None:
    """单帧只跑一次识别,结果供该帧全部断言共用(贵加载只算一次)。"""
    return find_aura_cursor(_require_frame(name), _AURA_BAND_RECT)


def _aura_tpl_missing() -> bool:
    from one_dragon.utils.file_utils import get_project_root
    p = (get_project_root() / 'assets' / 'template' / 'currency_war'
         / 'cw_aura_marker' / 'raw.webp')
    return not p.is_file()


pytestmark = pytest.mark.skipif(_aura_tpl_missing(), reason='主角光环光标模板未归档')


@pytest.mark.parametrize('frame, slot, cx, cy', [
    ('reward_spheres_15', 1, 751, 320),        # 光标在槽 1(校准帧系)
    ('rail_badge_prep_r4', 3, 1029, 320),      # 光标在槽 3
    ('rail_badge_consumed_r4', 3, 1029, 320),  # 光标在槽 3(消费后帧)
])
def test_cursor_hit_maps_to_slot(frame: str, slot: int, cx: int, cy: int) -> None:
    """在场帧带内命中:score ≥ 阈值、中心恒定(位置稳定性回归)、
    槽位映射正确。"""
    out = _run_find(frame)
    assert out is not None, f'{frame} 光标应命中(归档帧光标在场)'
    score, hit_cx, hit_cy = out
    assert score >= 0.7, f'{frame} score={score:.3f} 应 ≥ 阈值 0.7'
    assert (hit_cx, hit_cy) == (cx, cy), \
        f'{frame} 中心漂移: ({hit_cx},{hit_cy}) != ({cx},{cy})'
    assert map_aura_x_to_slot(hit_cx, _SLOT_RECTS) == slot


@pytest.mark.parametrize('frame', [
    'deployed_2star',   # 无光标备战帧
    'shop_open',        # 商店开态(牌行盖前排,带内无光标)
])
def test_cursor_miss_on_negative_frames(frame: str) -> None:
    """阴性帧带内不命中(语料阴性最高 0.463 << 阈值 0.7,宁缺勿造)。"""
    assert _run_find(frame) is None


def test_slot_mapping_out_of_band_returns_none() -> None:
    """纯函数:命中 x 落全部槽域外 → None(读链漂移信号,禁猜槽号)。"""
    assert map_aura_x_to_slot(660, _SLOT_RECTS) is None      # 带内槽域外(左缘)
    assert map_aura_x_to_slot(1250, _SLOT_RECTS) is None     # 带内槽域外(右缘)
    assert map_aura_x_to_slot(887, _SLOT_RECTS) == 2         # 槽 2 域内
    assert map_aura_x_to_slot(1175, _SLOT_RECTS) == 4        # 槽 4 域内
