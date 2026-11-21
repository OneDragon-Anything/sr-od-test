"""boss 大图标 SIFT 模板库 fixture 回归(文件镜像 src cw_node_reader.py)。

锁的设计约定:
- **库覆盖 = 实机帧命中**:boss_avatar 库(图鉴 20 公司 + 实机补采公司)
  加载后,对含该公司大图标的实机帧按生产同款 area rect
  (screen_info「区域-boss大图标」,坐标单一源)裁片跑
  ``match_boss_sift`` → 命中该公司且好匹配达断层门
  (``BOSS_SIFT_MIN_GOOD``/``BOSS_SIFT_RATIO``)。回归背景:图鉴 20 公司
  集外的新赛季公司(深渊育种科技)曾整库未命中致位面情报采集响亮失败;
- **非 boss 图标位不误命中**:语料帧详情条图标位为宝箱(非 boss 节点)
  时,新模板不得成为命中结果(生产链此路径另有「首领」标签门前置,
  本条为库侧负样本保险)。

fixture(货币战争-位面详情/):位面1选中-深渊育种科技(实机决策帧归档,
帧内 boss = 深渊育种科技·堕神之血·亚婆离)、位面1选中-棋盘格纹理
(图标位 = 宝箱)。缺帧/缺模板目录 → skip。
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

import cv2
import numpy as np
import pytest

from one_dragon.utils.file_utils import get_project_root
from sr_od.application.currency_war.obs.cw_node_reader import (
    BOSS_SIFT_MIN_GOOD,
    match_boss_sift,
)
from test.conftest import SrTestContext

_PD = '货币战争-位面详情'
#: 新公司名(模板 stem = SIFT 命中返回名 = cw_enemy_data.BOSS_MECHANICS 规范名)
_NEW_COMPANY = '深渊育种科技'


def _screens_dir() -> Path:
    """向上定位中央归档库 ``screens/``(同 test_identity_obs 手法)。"""
    p = Path(__file__)
    while p != p.parent:
        cand = p / 'screens'
        if cand.is_dir() and (any(cand.glob('*/*.webp')) or any(cand.glob('*/*.png'))):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库')


@cache
def _load_frame(state: str) -> np.ndarray | None:
    """读 fixture 帧(RGB 口径,框架截图同口径);缺失 → None。"""
    d = _screens_dir()
    for suffix in ('.webp', '.png'):
        f = d / _PD / f'{state}{suffix}'
        if f.is_file():
            img = cv2.imdecode(np.fromfile(str(f), dtype=np.uint8), cv2.IMREAD_COLOR)
            return None if img is None else cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return None


def _require_frame(state: str) -> np.ndarray:
    img = _load_frame(state)
    if img is None:
        pytest.skip(f'存档截图缺失:screens/{_PD}/{state}.webp')
    return img


@cache
def _boss_templates() -> dict:
    """生产同款模板库加载;目录缺失/为空 → skip(库面归数据批管)。"""
    from sr_od.application.currency_war.obs.cw_node_reader import load_boss_templates
    base = get_project_root() / 'assets' / 'template' / 'currency_war' / 'boss_avatar'
    if not base.is_dir():
        pytest.skip(f'模板库目录缺失:{base}')
    tpls = load_boss_templates(base)
    if not tpls:
        pytest.skip(f'模板库为空:{base}')
    return tpls


def _detail_icon_rect(ctx: SrTestContext):
    """大图标裁片 rect(screen_info 单一源;area 缺失 → skip)。"""
    from one_dragon.base.geometry.rectangle import Rect
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    r = _area_rect(ctx, '区域-boss大图标', _PD)
    if r is None:
        pytest.skip(f'screen_info 缺 area:{_PD}.区域-boss大图标')
    return r


def test_new_company_big_icon_hits_on_live_frame(
        test_context: SrTestContext) -> None:
    """实机帧 boss 大图标 → 命中补采公司且过断层门(生产 area rect 同款裁片)。"""
    frame = _require_frame('位面1选中-深渊育种科技')
    r = _detail_icon_rect(test_context)
    patch = frame[r.y1:r.y2, r.x1:r.x2]
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    hit = match_boss_sift(gray, _boss_templates())
    assert hit is not None, f'实机帧大图标应命中{_NEW_COMPANY}(库覆盖回归)'
    name, good = hit
    assert name == _NEW_COMPANY, f'命中名应为{_NEW_COMPANY},实际 {name}'
    assert good >= BOSS_SIFT_MIN_GOOD, f'好匹配 {good} 应达断层门 {BOSS_SIFT_MIN_GOOD}'


def test_non_boss_icon_slot_not_matched_by_new_template(
        test_context: SrTestContext) -> None:
    """非 boss 图标位(宝箱)帧:新模板不得成为命中结果(负样本保险)。"""
    frame = _require_frame('位面1选中-棋盘格纹理')
    r = _detail_icon_rect(test_context)
    patch = frame[r.y1:r.y2, r.x1:r.x2]
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    hit = match_boss_sift(gray, _boss_templates())
    assert hit is None or hit[0] != _NEW_COMPANY, \
        f'宝箱图标位不应命中{_NEW_COMPANY},实际 {hit}'
