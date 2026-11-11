"""爆仓(id 253301)条目锁(cw_investments 分目录镜像;UNIT_BUFF 族战斗域
三重皆盲零建模登记;先例 = 同目录 test_strategy_unit_buff.py 族形)。

测试面依据 = 设计稿(原件已退役)T-280 对应稿
§4 锁面(已退役评审稿 无需用户决定 6/6;卡面官方原文:「我方小队攻击敌方目标后，
若其生命值百分比少于16%，将其【斩杀】。」——斩杀阈值触发面/生命值百分比
读数/斩杀执行面游戏侧自算,bot 零响应):

- 条目锁:category UNIT_BUFF / payload UnitBuffRef 且 effect_text 与
  卡面单一源对拍 / id 253301 / duties 三位全 False / pending False;
- 登记链锁:_scan_strategy_grant_candidates 不含本卡(UNIT_BUFF 零响应
  登记非发放通道,反扫闭集不扩);
- 绑定负锁:_STRATEGY_BINDINGS_EXPLICIT 零本卡成员(不绑判据直辖);
- 封闭集不扩锁:三封闭面(PICK/GRANTS/BINDINGS)零成员。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
)

_CARD = '爆仓'


def test_baocang_entry_registered() -> None:
    """条目锁:UNIT_BUFF 零响应登记形(族形;effect_text 与卡面单一源
    对拍;duties 三位全 False;pending False)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '253301', 'id 对拍'
    assert spec.category.value == 'unit_buff', 'category = UNIT_BUFF'
    assert spec.payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_baocang_registration_chain_not_extended() -> None:
    """登记链锁:反扫闭集不扩(UNIT_BUFF 零响应登记非发放通道)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        _scan_strategy_grant_candidates,
    )
    assert _CARD not in _scan_strategy_grant_candidates(), \
        '反扫闭集不扩(零响应登记非发放通道)'


def test_baocang_binding_negative() -> None:
    """绑定负锁:显式绑定表零本卡成员(不绑判据直辖)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定面零成员'


def test_baocang_closed_sets_not_extended() -> None:
    """封闭集不扩锁:三封闭面(PICK/GRANTS/BINDINGS)零成员。"""
    assert _CARD not in PICK_INVEST_EFFECTS, 'PICK 零命中'
    assert _CARD not in STRATEGY_GRANTS, 'GRANTS 零命中'
    assert _CARD not in STRATEGY_BINDINGS, 'BINDINGS 零命中'
