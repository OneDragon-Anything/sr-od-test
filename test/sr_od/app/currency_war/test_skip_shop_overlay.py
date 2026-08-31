"""免战×商店开叠加态 fixture 验证(子态四问③正交判据的实锤证据)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import find_area_in_screen, get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_skip_x_shop_open_overlay_state(test_context: SrTestContext) -> None:
    """叠加态:识别为 备战-开商店(商店牌盖基态 id_mark 前台区域),但「按钮-跳过」(归备战屏)
    的 OCR 文本在叠加帧上仍可命中——验证「跨屏正交元素查找端不锁死单一屏」的必要性。

    fixture 2026-08-17 迁至 screens/货币战争-备战-开商店/(原误归备战目录;叠加帧开商店
    id_mark[购买经验+收起]全中、备战 前台区域 被商店牌盖 → 实属开商店态,r34 id_mark 修复勘定)。
    """
    if not test_context.has_screen('货币战争-备战-开商店', '免战叠加态'):
        pytest.skip('fixture 缺:screens/货币战争-备战-开商店/免战叠加态.webp')
    img = test_context.load_screen('货币战争-备战-开商店', '免战叠加态')
    # 叠加帧识别为开商店(它盖基态 id_mark → 基态不 is_precise;开商店自己的组合命中)
    assert get_match_screen_name(
        test_context, img, screen_name_list=['货币战争-备战-开商店']) == '货币战争-备战-开商店'
    # 「按钮-跳过」area 归备战屏,但在叠加帧上其 OCR rect 内文本「跳过(1/2)」存在
    si = test_context.screen_loader.get_screen('货币战争-备战')
    skip_area = next((a for a in si.area_list if a.area_name == '按钮-跳过'), None)
    assert skip_area is not None
    assert find_area_in_screen(test_context, img, skip_area).value == 1, (
        '免战×商店开叠加帧上「按钮-跳过」应命中(正交态:两状态同帧共存,'
        '查找端若锁死开商店屏会找不到跳过 → StartBattle 跨屏 fallback 的依据)')
