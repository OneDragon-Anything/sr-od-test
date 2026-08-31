"""货币战争 位面过渡画面 id_mark 准确性测试(2026-08-14 建档)。

验:① 真阳性 — 位面过渡 fixture 精准匹配 货币战争-位面过渡(id_mark 组合
   标识-位面节点2 + 标识-位面节点3 全中);
② 无碰撞 — 位面过渡 fixture 不被误判模拟宇宙(撞车源:sim_uni.yml 有同名
   点击空白处继续 area,建档前两画面并列 is_precise=false)。组合 id_mark
   (位面节点2/3 位面 文字,模拟宇宙无)解决 -> 位面过渡精准,模拟宇宙不命中。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_plane_transition_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:位面1->2 过渡 fixture -> 精准匹配 货币战争-位面过渡。"""
    if not test_context.has_screen('货币战争-位面过渡', 'plane_1to2'):
        pytest.skip('fixture 缺:screens/货币战争-位面过渡/plane_1to2.webp')
    img = test_context.load_screen('货币战争-位面过渡', 'plane_1to2')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-位面过渡']) == '货币战争-位面过渡', (
        '位面过渡 fixture 应精准匹配 货币战争-位面过渡(id_mark 标识-位面节点2+3 全中)'
    )


def test_plane_transition_not_misread_as_sim_universe(test_context: SrTestContext) -> None:
    """无碰撞:位面过渡 fixture 不被误判模拟宇宙。

    撞车源:sim_uni.yml 有同名 点击空白处继续 area -> 建档前两画面并列
    is_precise=false。组合 id_mark(位面节点2/3 位面 文字)使位面过渡精准命中,
    模拟宇宙无此 id_mark -> 不被误判。
    """
    if not test_context.has_screen('货币战争-位面过渡', 'plane_1to2'):
        pytest.skip('fixture 缺:screens/货币战争-位面过渡/plane_1to2.webp')
    img = test_context.load_screen('货币战争-位面过渡', 'plane_1to2')
    # 位面过渡应精准命中自身
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-位面过渡']) == '货币战争-位面过渡'
    # 模拟宇宙不应精准命中(无位面节点 id_mark)
    assert get_match_screen_name(test_context, img, screen_name_list=['模拟宇宙']) is None, (
        '位面过渡 fixture 不应被误判模拟宇宙(模拟宇宙无位面节点 id_mark)'
    )
