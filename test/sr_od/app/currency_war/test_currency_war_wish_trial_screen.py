"""货币战争 祈愿试炼画面 id_mark 准确性测试(2026-08-17 建档三件套收尾)。

验:真阳性 — 祈愿试炼 fixture 精准匹配 货币-祈愿试炼(id_mark ``标识-祈愿试炼`` 命中)。
此前该屏无完整建档(doc/fixture 测缺)被停机钩子隔离;三件套补齐后钩子删除,0c 分支
HandleWishTrial 接管。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from one_dragon.base.screen.screen_utils import get_match_screen_name

if TYPE_CHECKING:
    from test.conftest import SrTestContext


def test_wish_trial_screen_id_mark_true_positive(test_context: SrTestContext) -> None:
    """真阳性:祈愿试炼 fixture → 精准匹配 货币战争-祈愿试炼。"""
    if not test_context.has_screen('货币战争-祈愿试炼', '祈愿试炼'):
        pytest.skip('fixture 缺:screens/货币战争-祈愿试炼/祈愿试炼.webp')
    img = test_context.load_screen('货币战争-祈愿试炼', '祈愿试炼')
    assert get_match_screen_name(
        test_context, img, screen_name_list=['货币战争-祈愿试炼']) == '货币战争-祈愿试炼', (
        '祈愿试炼 fixture 应精准匹配(id_mark 标识-祈愿试炼 命中)')
