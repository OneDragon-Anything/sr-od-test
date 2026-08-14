"""货币战争 投资策略屏 id_mark 准确性测试(2026-08-15 live 重建档)。

投资策略节点触发的独立屏(右上「返回备战界面」;非 overlay —— 2026-08-15 live 实锤):
「请选择投资策略」标题 + 3 张策略卡(卡名 y~474)+ 每卡独立刷新按钮(y~855,每卡 1 次
免费,live 验证 卡3 借力打力→战术专家:佩拉)+ 确认(978,983)。
验证:
① 真阳性 — fixture(default/card1_selected/card3_refreshed 三态)精准匹配;
② 无碰撞 — 独立屏无备战 id_mark 元素 → 不与 货币战争-备战 撞车。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


SCREEN = '货币战争-投资策略'


@pytest.mark.parametrize('state', ['default', 'card1_selected', 'card3_refreshed'])
def test_invest_strategy_id_mark_true_positive(test_context: SrTestContext, state: str) -> None:
    """真阳性:三态 fixture(未选/选中卡1/刷新卡3)都精准匹配 投资策略屏。"""
    if not test_context.has_screen(SCREEN, state):
        pytest.skip(f'fixture 缺:screens/{SCREEN}/{state}.webp')
    img = test_context.load_screen(SCREEN, state)
    assert get_match_screen_name(test_context, img, screen_name_list=[SCREEN]) == SCREEN


def test_invest_strategy_not_misread_as_battle_prep(test_context: SrTestContext) -> None:
    """无碰撞:投资策略独立屏不被误判 货币战争-备战(无备战 id_mark 元素)。"""
    if not test_context.has_screen(SCREEN, 'default'):
        pytest.skip('fixture 缺:default.webp')
    img = test_context.load_screen(SCREEN, 'default')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) is None
