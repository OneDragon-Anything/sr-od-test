"""中断挑战弹窗建档验证(2026-08-17;bug#2 挂账闭环)。

- fixture 真阳性:弹窗帧 id_mark 组合(标识-中断挑战 + 按钮-放弃并结算)全命中 is_precise;
- 不撞父屏:弹窗帧上备战屏不是 is_precise(背景压暗 OCR 全灭,天然区分);
- 按钮 area 可命中:按钮-暂时离开 / 只读 文本-小队生命值(HP 真值快照源)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import (
    find_area_in_screen,
    get_match_screen_name,
    is_target_screen,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def _load(test_context: SrTestContext):
    if not test_context.has_screen('货币战争-中断挑战弹窗', 'open'):
        pytest.skip('fixture 缺:screens/货币战争-中断挑战弹窗/open.webp')
    return test_context.load_screen('货币战争-中断挑战弹窗', 'open')


def test_interrupt_dialog_true_positive(test_context: SrTestContext) -> None:
    """弹窗帧:自家 id_mark 组合全命中(is_precise)。"""
    img = _load(test_context)
    assert is_target_screen(test_context, img, screen_name='货币战争-中断挑战弹窗'), (
        '中断挑战弹窗 fixture 应精准命中自家 id_mark 组合')


def test_interrupt_dialog_no_parent_collision(test_context: SrTestContext) -> None:
    """弹窗帧:父屏(货币战争-备战)不得 is_precise(遮罩压暗,天然区分)。"""
    img = _load(test_context)
    assert not is_target_screen(test_context, img, screen_name='货币战争-备战'), (
        '弹窗帧不应命中备战 id_mark(遮罩应盖灭父屏识别)')
    assert get_match_screen_name(
        test_context, img,
        screen_name_list=['货币战争-中断挑战弹窗', '货币战争-备战'],
    ) == '货币战争-中断挑战弹窗'


def test_interrupt_dialog_areas(test_context: SrTestContext) -> None:
    """按钮/只读 area 在 fixture 上可命中(1g 分支点按钮-关闭的前提)。"""
    img = _load(test_context)
    si = test_context.screen_loader.get_screen('货币战争-中断挑战弹窗')
    for name in ('按钮-暂时离开', '文本-小队生命值'):
        area = next((a for a in si.area_list if a.area_name == name), None)
        assert area is not None, f'area 缺:{name}'
        assert find_area_in_screen(test_context, img, area).value == 1, (
            f'area 应命中:{name}')
