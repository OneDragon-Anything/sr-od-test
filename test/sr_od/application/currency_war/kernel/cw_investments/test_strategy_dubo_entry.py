"""读博深造(id 251901)双腿登记锁(cw_investments 分目录镜像;腿 2/3 送卡
在 cw_gain_effects PICK char×char 组合行,本表 UNIT_BUFF 族战力类零响应
登记;先例 = 同目录 test_strategy_zuanshi_entry.py 钻石恒永久)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-267 对应稿
§4 锁面(REVIEW-T267 免裁 7/7;卡面官方原文:「战斗开始时，若银河学者羁绊
处于激活状态，一名随机的1费或2费银河学者变成3星。获得【艾丝妲】和【阮·梅】。」
——条件段与随机升星游戏侧自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 251901 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '读博深造'


def test_dubo_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(钻石恒永久同形;effect_text 与卡面
    单一源对拍;duties 三位全 False;pending False[变形持续性 T-180 案 A
    定谳])。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '251901', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_dubo_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
