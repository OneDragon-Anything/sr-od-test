"""货币战争 备战-武装箱选择画面 id_mark 准确性测试(2026-08-14 建档)。

开补给箱(点箱内「开启」文字区)弹出的装备 4 选 1 overlay:「<档位>武装箱」标题 +
「请选择1个」副题 + 4 张装备卡。验证:
① 真阳性 — fixture 精准匹配 货币战争-备战-武装箱选择(id_mark 组合 标识-武装箱 +
   标识-请选择 全中;OCR 实读「简易武装箱」/「请选择1个」,LCS 覆盖档位前缀变体);
② 无碰撞 — overlay 盖住备战 id_mark(购买经验/出战)→ 备战不精准命中,不与父画面撞车。

建档案:OCR rect 纵向 padding 要足(原 30px 高裁切 paddle 检测不到「请选择1个」,
放宽到 45px 后稳读;2026-08-14 建档实测)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


SCREEN = '货币战争-备战-武装箱选择'


def test_supply_box_open_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:武装箱选择 fixture -> 精准匹配 货币战争-备战-武装箱选择。"""
    if not test_context.has_screen(SCREEN, 'box_open'):
        pytest.skip('fixture 缺:screens/货币战争-备战-武装箱选择/box_open.webp')
    img = test_context.load_screen(SCREEN, 'box_open')
    assert get_match_screen_name(test_context, img, screen_name_list=[SCREEN]) == SCREEN, (
        '武装箱选择 fixture 应精准匹配(id_mark 标识-武装箱+标识-请选择 全中)'
    )


def test_supply_box_open_not_misread_as_battle_prep(test_context: SrTestContext) -> None:
    """无碰撞:overlay 盖住备战 id_mark -> 不被误判货币战争-备战。"""
    if not test_context.has_screen(SCREEN, 'box_open'):
        pytest.skip('fixture 缺:screens/货币战争-备战-武装箱选择/box_open.webp')
    img = test_context.load_screen(SCREEN, 'box_open')
    assert get_match_screen_name(test_context, img, screen_name_list=['货币战争-备战']) is None, (
        '武装箱 overlay 盖备战 id_mark,备战不应精准命中'
    )
