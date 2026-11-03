"""领航专家:姬子(id 260901)条目锁(cw_investments 分目录镜像;UNIT_BUFF
族战力类零响应登记;先例 = 同目录 test_strategy_baocang_entry.py 爆仓形)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-294 对应稿
§4 锁面(REVIEW-T294 免裁 8/8;卡面官方原文:「获得专家顾问【姬子】，并使
其在本局游戏中加入商店。战斗开始时，姬子邀请大家品尝咖啡，根据她的星级
使我方全体行动提前40%/70%/100%，获得25%/50%/90%速度增幅，所有前台角色
损失40%当前生命值。」——行动提前段/速度增幅段/HP 损失段游戏侧自算,
bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 260901 / duties 三位全 False / pending False;
- 现金 fail-closed 锁:条目载荷非 EconomyEffect = 经济面零承载。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
)

_CARD = '领航专家:姬子'


def test_linghang_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(爆仓同形;effect_text 与卡面单一源
    对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '260901', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_linghang_cash_fail_closed() -> None:
    """现金 fail-closed 锁:战力类零响应登记无经济面——条目载荷非
    EconomyEffect 载体 = 经济聚合面零承载(估值恒 (0.0, False) 结构前提)。"""
    assert not hasattr(STRATEGY_EFFECTS[_CARD].payload, 'gold_per_node'), \
        'UNIT_BUFF 载体非 EconomyEffect(经济面零承载)'
