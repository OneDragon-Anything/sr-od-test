"""打通上下游·金(id 250201)条目锁(cw_investments 分目录镜像;UNIT_BUFF
族战力类零响应登记;先例 = 同目录 test_strategy_renhai_entry.py 人海战术)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-251 对应稿
§4 锁面(REVIEW-T251 无需用户决定 7/7;卡面官方原文:「我方小队速度增幅提高10%。
每个节点开始时，速度增幅额外提高1%。」——两段增幅与节点增长句游戏侧
自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 250201 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '打通上下游·金'


def test_datong_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(人海战术同形;effect_text 与卡面
    单一源对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '250201', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_datong_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
