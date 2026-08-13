"""货币战争 补给画面 id_mark 准确性测试(2026-08-13 建档)。

验:① 真阳性 — 补给 fixture 精准匹配 货币战争-补给(id_mark ``标识-补给阶段`` 全中);
② 无碰撞 — 补给节点备战 fixture(含「返回补给阶段」按钮)精准匹配 货币战争-备战,**不**被误判
   货币战争-补给。根因(bug):``BuyShopCards`` 曾把备战「返回补给阶段」按钮文本的子串「补给阶段」
   误判补给 overlay → bail → Loop 死循环;id_mark 位置区分(补给标题 [893,120,1027,230]
   ≠ 备战返回按钮 [1716,51,..])→ 备战不被误判补给。本测锁之。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_supply_screen_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:补给 fixture(未选择/已选择)→ 精准匹配 货币战争-补给。"""
    for state in ('未选择', '已选择'):
        if not test_context.has_screen('货币战争-补给', state):
            pytest.skip(f'fixture 缺:screens/货币战争-补给/{state}.webp')
    for state in ('未选择', '已选择'):
        img = test_context.load_screen('货币战争-补给', state)
        assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-补给']) == '货币战争-补给', (
            f'补给 fixture({state})应精准匹配 货币战争-补给(id_mark 标识-补给阶段 全中)'
        )


def test_supply_node_prep_not_misread_as_supply(test_context: SrTestContext) -> None:
    """无碰撞:补给节点备战(含「返回补给阶段」按钮)→ 精准匹配 货币战争-备战,非 货币战争-补给。

    防 BuyShopCards 假阳根因复发:备战「返回补给阶段」按钮文本含「补给阶段」,
    但其位置 [1716,51] ≠ 补给标题 id_mark [893,120,1027,230] → 备战不被误判补给。
    """
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        pytest.skip('fixture 缺:screens/货币战争-备战/补给节点.webp')
    img = test_context.load_screen('货币战争-备战', '补给节点')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) == '货币战争-备战', (
        '补给节点备战应精准匹配 货币战争-备战'
    )
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-补给']) is None, (
        '补给节点备战(含返回补给阶段按钮)不应被误判 货币战争-补给(id_mark 位置区分)'
    )
