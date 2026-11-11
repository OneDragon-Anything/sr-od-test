"""赞美太阳(id 252401)登记锁(cw_investments 分目录镜像;先例 = 同目录
test_strategy_zhuangbei_entry.py 装备党)。

测试面依据 = 设计稿(原件已退役) 设计稿(原件已退役)(定稿,REVIEW 无需用户决定 9/9)§4 锁面(卡面官方原文:「每拥有一件
【白昼装备】以及其原型装备，在进入新节点时就获得1点经验。角色每穿戴一件
【白昼装备】，幸运一击率提高10%。获得【那刻夏】。」):

- 条目锁(锁 1):UNIT_BUFF 零响应登记形 / id 252401 / payload
  UnitBuffRef 且 effect_text 与卡面单一源对拍(锁 2)/ duties 三位全
  False / pending False / 现金分支 fail-closed(估值恒 (0.0, False));
- 授予/绑定存量成员锁(锁 5):那刻夏逐名独立构造防伪锁 + 绑定二元组
  精确相等 + 阵容域差集语义(不锁全值——scope 派生值随阵容知识批漂移);
- 封闭集不扩 + 停机钩子零成员(锁 6):本卡不入 PICK 具名发放封闭集、
  不入商店停机钩子名单(卡面无采集需求,零响应 buff + sim XP 真值非
  停机对象;名单现值与断言访问形 = 类限定 ClassVar)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_invest_data import PLAZA_AUGMENTS
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EffectKind,
    UnitBuffRef,
)
from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _STRATEGY_BINDINGS_EXPLICIT,
    INVESTMENT_STRATEGIES,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
    strategy_faction_scope,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '赞美太阳'
_CID = '252401'


def test_zanmei_entry_registered() -> None:
    """条目锁(锁 1):UNIT_BUFF 零响应登记形;id 对拍;duties 三位全
    False;pending False(三条效果条目全卡面明文,无二义冻结面)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == _CID, 'id 对拍'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_zanmei_effect_text_single_source() -> None:
    """锁 2:effect_text 与卡面单一源对拍(经 PLAZA_AUGMENTS 数据面,版本
    更新改文自动跟随)+ id 域与 name 域双恰一(表达式取元前提,双命中 =
    数据层漂移,恰一哨先红)。"""
    assert STRATEGY_EFFECTS[_CARD].payload.effect_text == \
        INVESTMENT_STRATEGIES[_CARD].effect, 'effect_text 与卡面单一源对拍'
    assert len([a for a in PLAZA_AUGMENTS if a.id == _CID]) == 1, \
        'id 域恰一'
    assert len([a for a in PLAZA_AUGMENTS if a.name == _CARD]) == 1, \
        'name 域恰一'


def test_zanmei_cash_fail_closed() -> None:
    """现金分支锁(锁 1 尾):无 STRATEGY_ECONOMY 条目 → 估值 fail-closed
    (0.0, False)(xp_per_node 静态挂值被否决后的登记后果申报:效果条目 1 动态
    XP 未入现金通道,战力类立场 0,复合结果 = 零现金分)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD, gs) == (0.0, False)


def test_zanmei_grant_and_binding_stock_members() -> None:
    """授予/绑定存量成员锁(锁 5):那刻夏逐名独立构造(防伪锁——整元组
    引用同一常量对象会漏「字段被替换为别值」形态);绑定二元组精确相等;
    阵容域差集语义 ⊇ {昼之半神, 追击}(scope 全值随阵容知识批漂移,
    不锁全值只锁本卡两条效果条目来源必在域)。"""
    grant = STRATEGY_GRANTS[_CARD]
    assert grant.chars_immediate == ('那刻夏',), '效果条目 3 授予 = 那刻夏单发'
    assert grant.advisor is False, '卡面无「加入商店」句,advisor False'
    assert _STRATEGY_BINDINGS_EXPLICIT[_CARD] == (
        frozenset({'昼之半神'}), frozenset({'那刻夏'})), '绑定二元组精确相等'
    scope = strategy_faction_scope(_CARD)
    assert {'昼之半神', '追击'} <= scope, \
        f'差集语义:scope 缺成员,现值 {sorted(scope)}'


def test_zanmei_not_in_pick_and_watch_names() -> None:
    """封闭集不扩 + 停机钩子零成员(锁 6):效果条目 3 系具名角色发放非具名装备,
    不入 PICK(入集 = 实现错误);本卡零响应 + sim XP 真值非采集需求,
    不入商店停机钩子名单(名单访问形 = 类限定 ClassVar)。"""
    assert _CARD not in set(PICK_INVEST_EFFECTS), '本卡禁入 PICK 封闭集'
    assert _CARD not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'
