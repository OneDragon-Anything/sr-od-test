"""和平手枪祝福(id 230301)条目锁+现金 fail-closed 锁(cw_investments
分目录镜像;祝福族第 3 条,UNIT_BUFF 零响应登记载体;先例 = 同目录
test_strategy_zhedie_zhufu_entry.py 折叠小刀祝福)。

测试面依据 = 原稿锁面
§4(原稿评审锁 无需用户决定 7/7;卡面官方原文:「获得1个【和平手枪】。我方小队
获得30%后台强度和15初始能量。」——祝福面游戏侧自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 230301 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '和平手枪祝福'


def test_heping_zhufu_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(折叠小刀祝福同形;effect_text 与
    卡面单一源对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '230301', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_heping_zhufu_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
