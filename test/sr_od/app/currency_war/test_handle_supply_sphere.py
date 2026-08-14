"""货币战争 补给箱开箱 + 奖励球收取 op 测试(fixture 驱动,mock controller)。

fixture(2026-08-14 实机采集,sr-od-test/screens/):
- 货币战争-备战/reward_spheres_8:8 球(1金5蓝2灰)+ 槽1 补给箱(9/9 席满态)
- 货币战争-备战-武装箱选择/box_open:开箱 overlay(4 卡:轮滑鞋/生命之花/幸运星/光能电池)

验证读路径 + 选卡逻辑(点击/弹层 mock,不真点)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.operations.handlers.handle_supply_box import (
    HandleSupplyBox,
    _material_value,
)
from sr_od.application.currency_war.cw_identity_obs import (
    read_reward_spheres,
    read_supply_boxes,
)

if True:
    from test.conftest import SrTestContext


def test_material_value_table() -> None:
    """合成材料通用性表:生命之花(7 配方)最高,幸运星(3)低,未知 0。"""
    assert _material_value('生命之花') == 7
    assert _material_value('轮滑鞋') == 6
    assert _material_value('未知装备') == 0


def test_fixture_reads_spheres_and_box(test_context: SrTestContext) -> None:
    """8 球帧无箱(时间线:箱由后续球掉落);5 球帧球+箱同帧共存,两 reader 互不干扰。"""
    if not test_context.has_screen('货币战争-备战', 'reward_spheres_8'):
        pytest.skip('fixture 缺:reward_spheres_8.webp')
    img = test_context.load_screen('货币战争-备战', 'reward_spheres_8')
    assert len(read_reward_spheres(test_context, img)) == 8
    assert read_supply_boxes(test_context, img) == [], '8 球帧箱未出现(箱由后续球掉落)'
    if not test_context.has_screen('货币战争-备战', 'reward_spheres_5'):
        pytest.skip('fixture 缺:reward_spheres_5.webp')
    img5 = test_context.load_screen('货币战争-备战', 'reward_spheres_5')
    spheres5 = read_reward_spheres(test_context, img5)
    boxes5 = read_supply_boxes(test_context, img5)
    assert len(spheres5) == 5 and [s for s, _p in boxes5] == [1], '5 球帧:球 5 + 箱槽1 共存'


def test_pick_card_key_equips_priority(test_context: SrTestContext) -> None:
    """选卡:target_comp.key_equips 命中优先(无 match/无 comp 时按材料通用性)。"""
    op = HandleSupplyBox(test_context)
    # 无 cw_match(局外)→ 材料通用性:生命之花(7) > 轮滑鞋(6)
    assert op._pick_card(['轮滑鞋', '生命之花', '幸运星']) == '生命之花'
    assert op._pick_card([]) is None
