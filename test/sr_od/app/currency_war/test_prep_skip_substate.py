"""备战「跳过」子态(免战牌)建档测试(2026-08-17 M72,3.21;r34 勘定独立子屏)。

↺ 勘定(2026-08-17 id_mark 撞车修复):r32 原决策「免战=元素级不建屏 + 撤出战 id_mark 保备战精准」
在角色详情帧撞车(备战 3 id_mark 在详情帧全可见 → 双 is_precise)。按 screen-onboarding 场景①④
正统做法恢复:出战 id_mark(详情面板盖住它/免战替换它——一个元素解两类子态,备战帧在两者上
都自然不精准);免战帧归独立子屏「货币战争-备战-免战」(id_mark 跳过)。loop 运行时不受影响
(备战分支入口=单 area 购买经验判定,非 is_precise)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import find_area_in_screen, get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_skip_substate_matches_own_screen(test_context: SrTestContext) -> None:
    """免战跳过态 fixture:精准匹配自己的子屏(货币战争-备战-免战),不再匹配备战。"""
    if not test_context.has_screen('货币战争-备战-免战', '跳过态'):
        pytest.skip('fixture 缺:screens/货币战争-备战-免战/跳过态.webp')
    img = test_context.load_screen('货币战争-备战-免战', '跳过态')
    assert get_match_screen_name(
        test_context, img,
        screen_name_list=['货币战争-备战', '货币战争-备战-免战'],
    ) == '货币战争-备战-免战', (
        '免战跳过态应精准匹配子屏(出战 id_mark 被跳过替换 → 备战不精准,场景④语义)')
    # 「按钮-跳过」area(备战屏,handler 点它)在子屏帧上仍可命中(跨屏正交查找)
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    assert skip_area is not None, '按钮-跳过 area 应已建档'
    assert find_area_in_screen(test_context, img, skip_area).value == 1, (
        '免战跳过态 fixture 上「按钮-跳过」应命中(OCR 跳过)')


def test_skip_area_not_hit_in_normal_prep(test_context: SrTestContext) -> None:
    """常态备战 fixture(无免战):「按钮-跳过」不命中(出战按钮态)。"""
    if not test_context.has_screen('货币战争-备战', 'shop_closed'):
        pytest.skip('fixture 缺:screens/货币战争-备战/shop_closed.webp')
    img = test_context.load_screen('货币战争-备战', 'shop_closed')
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    if skip_area is None:
        pytest.skip('按钮-跳过 area 未建')
    assert find_area_in_screen(test_context, img, skip_area).value != 1, (
        '常态备战(出战按钮)不应命中「按钮-跳过」')
