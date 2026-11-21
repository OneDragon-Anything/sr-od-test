"""boss 大图标 SIFT 模板库 fixture 回归(文件镜像 src cw_node_reader.py)。

锁的设计约定:
- **库覆盖 = 实机帧命中**:boss_avatar 库(图鉴 20 公司 + 实机补采公司)
  加载后,对含该公司大图标的实机帧按生产同款 area rect
  (screen_info「区域-boss大图标」,坐标单一源)裁片跑
  ``match_boss_sift`` → 命中该公司且好匹配达断层门
  (``BOSS_SIFT_MIN_GOOD``/``BOSS_SIFT_RATIO``)。回归背景:图鉴 20 公司
  集外的新赛季公司(深渊育种科技)曾整库未命中致位面情报采集响亮失败;
- **模板 × 双识别域兼容**:同一公司模板须在两个生产裁片域同时过断层门——
  大图标域(~105px)与节点条域(``classify_node_row`` boss 圆 ~56px patch,
  备战条/位面条共用)。回归背景:不死者联盟模板初版为图鉴 60px 小图,
  在大图标域被同尺度实机大模板抢分(好匹配 7 vs 5,断层门不过)致
  位面情报采集响亮失败;换实机大裁片原尺度落位时节点条域又失配,
  实测 0.9 缩放两域同时过(裁片构建依据,见模板批 commit);
- **非 boss 图标位不误命中**:语料帧详情条图标位为宝箱(非 boss 节点)
  时,新模板不得成为命中结果(生产链此路径另有「首领」标签门前置,
  本条为库侧负样本保险);
- **新模板不抢他司命中**:已识别公司的实机帧(深渊育种科技)与库外
  变体帧(纹章风头像)上,后补模板不得成为命中结果——抢分会破坏
  他司断层门(同尺度模板互相抬次名分,即本批回归的成因形态)。

fixture(货币战争-位面详情/):位面1选中-深渊育种科技(实机决策帧归档,
帧内 boss = 深渊育种科技·堕神之血·亚婆离)、位面1选中-棋盘格纹理
(图标位 = 宝箱)、位面2选中-不死者联盟(实机决策帧归档,帧内 boss =
不死者联盟·极乐颠倒·邪愿莲华主)、位面详情-纹章风头像-run30(库外变体
渲染,无库命中)。缺帧/缺模板目录 → skip。
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
#: 位面2 boss(第七跑补采批:实机大图标裁片替换图鉴小图,见上「模板 × 双识别域兼容」)
_P2_COMPANY = '不死者联盟'


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


def test_p2_boss_big_icon_hits_on_live_frame(
        test_context: SrTestContext) -> None:
    """位面2 实机帧大图标 → 命中不死者联盟且过断层门(模板替换回归)。"""
    frame = _require_frame('位面2选中-不死者联盟')
    r = _detail_icon_rect(test_context)
    patch = frame[r.y1:r.y2, r.x1:r.x2]
    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    hit = match_boss_sift(gray, _boss_templates())
    assert hit is not None, f'实机帧大图标应命中{_P2_COMPANY}(双域兼容回归)'
    name, good = hit
    assert name == _P2_COMPANY, f'命中名应为{_P2_COMPANY},实际 {name}'
    assert good >= BOSS_SIFT_MIN_GOOD, f'好匹配 {good} 应达断层门 {BOSS_SIFT_MIN_GOOD}'


def test_band_boss_slot_hits_same_template(
        test_context: SrTestContext) -> None:
    """节点条域 boss 圆(classify 同款 56px patch)→ 同一模板仍命中(双域锁)。

    fixture 节点条 = 位面详情选中未来位面的彩色渲染态;备战条锁灰态无
    fixture,本条锁的是「模板 × 节点条裁片尺度」这一兼容性(模板重裁时
    最易破坏的面),渲染态差异由生产识别链的重试账兜底。
    """
    frame = _require_frame('位面2选中-不死者联盟')
    from sr_od.application.currency_war.obs.cw_node_reader import (
        classify_node_row,
        load_node_type_templates,
    )
    nt_dir = get_project_root() / 'assets' / 'game_data' / 'cw_node_types'
    nt = load_node_type_templates(nt_dir)
    assert nt, f'节点类型模板缺失:{nt_dir}'
    from sr_od.application.currency_war.kernel.cw_obs_core import _area_rect
    r = _area_rect(test_context, '区域-节点条', _PD)
    if r is None:
        pytest.skip(f'screen_info 缺 area:{_PD}.区域-节点条')
    slots = classify_node_row(frame[r.y1:r.y2, r.x1:r.x2], nt,
                              boss_templates=_boss_templates())
    assert slots, '节点条应检出节点圆(fixture 帧实测 7 圆)'
    assert slots[-1].boss == _P2_COMPANY, \
        f'节点条最右 boss 槽应命中{_P2_COMPANY}(双域兼容锁),实际 {slots[-1].boss}'


def test_new_template_not_hijacking_other_company_icons(
        test_context: SrTestContext) -> None:
    """后补模板不抢他司/变体/非boss位的命中(断层门次名保护)。"""
    r = _detail_icon_rect(test_context)
    for state in ('位面1选中-深渊育种科技',      # 已识别公司(生产命中 = 深渊育种科技)
                  '位面详情-纹章风头像-run30',    # 库外变体渲染(生产 = 未识别缺口)
                  '位面1选中-棋盘格纹理'):        # 非 boss 图标位(宝箱)
        frame = _require_frame(state)
        patch = frame[r.y1:r.y2, r.x1:r.x2]
        gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
        hit = match_boss_sift(gray, _boss_templates())
        assert hit is None or hit[0] != _P2_COMPANY, \
            f'{state} 不应命中{_P2_COMPANY},实际 {hit}'
