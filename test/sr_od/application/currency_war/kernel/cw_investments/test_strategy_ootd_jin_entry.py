"""OOTD·金(id 251301)条目锁(cw_investments 分目录镜像;UNIT_BUFF 族
战力类零响应登记;先例 = 同目录 test_strategy_bangyang_jin_entry.py
榜样的力量·金)。

测试面依据 = 原稿锁面
§4 锁面(原稿评审锁 无需用户决定 8/8;卡面官方原文:「我方小队每穿戴一件不同的
装备，获得3%生命提高，6%前/后台强度。」——件数计数与两段增幅游戏侧
自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 251301 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = 'OOTD·金'


def test_ootd_jin_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(榜样的力量·金同形;effect_text 与
    卡面单一源对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '251301', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_ootd_jin_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
