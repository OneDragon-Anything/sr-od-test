"""货币战争 补给选项双装备行布局锁(read_supply_options;2026-08-26)。

背景:补给节点存在第二种布局 —— 每列 = 角色 + **2 个装备**(第一行 y≈648、
第二行 y≈748-749)。旧 `_SUPPLY_EQUIP_Y` 上界 735 使第二行整行漏读(10 选只读出
4,decide_supply 建模残缺)。本文件用真实存档帧(``货币战争-补给/双排装备``)
锁定:上界 780 后第二行代表性装备名必须读出、配对不退化。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.cw_node_obs import read_supply_options

if True:  # test_context fixture 类型
    from test.conftest import SrTestContext

SCREEN = '货币战争-补给'
STATE = '双排装备'


def test_read_supply_options_dualrow_layout(test_context: SrTestContext) -> None:
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'fixture 缺:{SCREEN}/{STATE}.webp')
    img = test_context.load_screen(SCREEN, STATE)
    opts = read_supply_options(test_context, img)

    names = [o.equip for o, _pt in opts]
    # 第二行(cy≈748-749,旧上界 735 整行漏读)在不同列的 4 个代表必须全部读出。
    assert {'量产型装甲', '轮滑鞋', '生命之花', '幸运星'} <= set(names), \
        f'双排布局第二行装备名漏读: {names}'
    assert len(opts) == 8, f'选项数与建档实测不符: {names}'


def test_read_supply_options_dualrow_char_pairing(test_context: SrTestContext) -> None:
    if not test_context.has_screen(SCREEN, STATE):
        pytest.skip(f'fixture 缺:{SCREEN}/{STATE}.webp')
    img = test_context.load_screen(SCREEN, STATE)
    opts = read_supply_options(test_context, img)

    paired = [o for o, _pt in opts if o.char]
    # 同列两行装备共享同一角色名 x → 配对不应退化(建档帧实测:灵砂/姬子·启行/
    # 丹恒·饮月/万敌 均配对成功)。
    assert len(paired) >= 4, f'角色配对大面积退化: {[(o.equip, o.char) for o, _ in opts]}'
