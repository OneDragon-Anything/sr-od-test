"""绕口令(id 250901)条目锁(cw_investments 分目录镜像;UNIT_BUFF 族
战力类零响应登记;先例 = 同目录 test_strategy_chuangshang_entry.py
创伤小组)。

测试面依据 = 设计稿(原件已退役)T-258 对应稿
§4 锁面(已退役评审稿 无需用户决定 7/7;卡面官方原文:「进入战斗时，前台一号位角色
及其忆灵获得等同于后台一号位角色30%后台强度的前台强度，后台一号位角色及
其忆灵获得等同于前台一号位角色30%前台强度的后台强度。」——换位镜像增幅
游戏侧自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 250901 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '绕口令'


def test_raokouling_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(创伤小组同形;effect_text 与卡面
    单一源对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '250901', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_raokouling_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
