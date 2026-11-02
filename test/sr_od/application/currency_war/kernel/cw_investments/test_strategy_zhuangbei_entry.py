"""装备党(id 252201)双腿登记锁(cw_investments 分目录镜像;腿 2/3 送卡
在 cw_gain_effects PICK char×char 组合行,本表 UNIT_BUFF 族战力类零响应
登记;先例 = 同目录 test_strategy_dubo_entry.py 读博深造)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-270 对应稿
§4 锁面(REVIEW-T270 免裁 9/9;卡面官方原文:「激活狼狩羁绊时，狼狩角色们
每穿戴一件装备，就获得4%伤害增幅和2%速度增幅。获得【椒丘】和【飞霄】。」
——羁绊激活计件与两段增幅游戏侧自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 252201 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '装备党'


def test_zhuangbei_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(读博深造同形;effect_text 与卡面
    单一源对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '252201', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_zhuangbei_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
