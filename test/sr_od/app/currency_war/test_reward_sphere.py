"""货币战争 奖励球(晶矿)识别测试(read_reward_spheres / find_reward_spheres;2026-08-14 首见机制)。

通关奖励节点后备战右侧面板出球形奖励(点球开启入账;角色/补给箱占席;席满点不动)。
检测 = HoughCircles(**颜色分割不可行**:蓝球与背景 HSV 几乎同值,实测无分离度);
颜色分类 = 圆心 HSV(金/灰/蓝)。fixture:8球/5球/4球/空 四态(2026-08-14 实机采集)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import pytest

from one_dragon.base.geometry.rectangle import Rect
from sr_od.application.currency_war.obs.cw_identity_obs import find_reward_spheres

if True:  # test_context fixture 类型
    from test.conftest import SrTestContext

SCREEN = '货币战争-备战'
PANEL = Rect(1257, 140, 1662, 493)  # 区域-奖励(ground truth)


def _count(hits: list[tuple[str, object, int]], color: str) -> int:
    return sum(1 for c, _p, _r in hits if c == color)


def test_reward_spheres_8(test_context: SrTestContext) -> None:
    """8 球态:1 金 + 5 蓝 + 2 灰(VLM 逐球 ground truth 吻合)。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_8'):
        pytest.skip('fixture 缺:reward_spheres_8.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_8')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 8, f'应 8 球,实得 {[(c, p.x, p.y) for c, p, r in hits]}'
    assert _count(hits, 'gold') == 1 and _count(hits, 'blue') == 5 and _count(hits, 'gray') == 2
    # 金球位置 ground truth(1333,184)±15
    gold = [p for c, p, r in hits if c == 'gold'][0]
    assert abs(gold.x - 1333) <= 15 and abs(gold.y - 184) <= 15


def test_reward_spheres_5(test_context: SrTestContext) -> None:
    """收 3 球后 5 球态:0 金 + 3 蓝 + 2 灰。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_5'):
        pytest.skip('fixture 缺:reward_spheres_5.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_5')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 5 and _count(hits, 'blue') == 3 and _count(hits, 'gray') == 2, (
        f'应 3蓝2灰,实得 {[(c, p.x, p.y) for c, p, r in hits]}'
    )


def test_reward_spheres_4(test_context: SrTestContext) -> None:
    """收 4 球后 4 球态:0 金 + 2 蓝 + 2 灰。"""
    if not test_context.has_screen(SCREEN, 'reward_spheres_4'):
        pytest.skip('fixture 缺:reward_spheres_4.webp')
    img = test_context.load_screen(SCREEN, 'reward_spheres_4')
    hits = find_reward_spheres(img, PANEL)
    assert len(hits) == 4 and _count(hits, 'blue') == 2 and _count(hits, 'gray') == 2


def test_reward_spheres_empty_no_false_positive(test_context: SrTestContext) -> None:
    """空面板(球收完)0 误报(背景点阵/按钮不触发圆检测)。"""
    if not test_context.has_screen(SCREEN, 'reward_panel_empty'):
        pytest.skip('fixture 缺:reward_panel_empty.webp')
    img = test_context.load_screen(SCREEN, 'reward_panel_empty')
    assert find_reward_spheres(img, PANEL) == []
