"""定期福利注册面测试(cw_investments 分目录镜像;登记锁先例 =
同目录 test_strategy_cheer_squad_registry.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-162-dingqi-
fuli.md §4 锁 1。卡面官方原文(cw_invest_data.py):「立刻获得4个金币,
并且在每次进入新节点时，获得2金币。」

- 注册面锁:STRATEGY_ECONOMY 条目双字段 = instant_gold=4 ∧
  gold_per_node=2(固化快照滞后订正——注册行先于消费面接线已登记,
  数值来源 = 卡面 desc 逐字;本卡系 gold_per_node 族唯一精确卡,
  desc「每次进入新节点时」与字段语义逐字对应,两条效果条目零条件零上限);
- 绑定负锁:卡不入 STRATEGY_BINDINGS(泛用给金无阵营/召唤物/星徽
  点名,登记判据「泛用数值 → 不绑」直辖),strategy_bindings() 返回
  默认空元组(fail-closed);
- 即时金写端负锁:卡不入 PICK_INVEST_EFFECTS——instant_gold 族的
  选卡当场金写端当前按族级待办维持不建(零获得时点世界写入),入集
  = 实现越约;族级写端立项时随批迁移本锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_ECONOMY,
    strategy_bindings,
)

_CARD = '定期福利'


def test_dingqi_fuli_economy_registration_surface() -> None:
    """定期福利 注册面锁:双字段全已登记且数值 = 卡面 desc 逐字
    (instant_gold=4 选牌当场 / gold_per_node=2 每进节点;本测试存活
    同时证明构建校验通过——注册表孤儿键/双匹配闸在 import 期)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 4, \
        '选牌当场金 = 卡面「立刻获得4个金币」'
    assert eff.gold_per_node == 2, \
        '每节点金 = 卡面「每次进入新节点时,获得2金币」'
    assert _CARD in INVESTMENT_STRATEGIES, '策略名入 base 注册表'


def test_dingqi_fuli_no_faction_binding() -> None:
    """绑定负锁:定期福利不入 STRATEGY_BINDINGS——无条件泛用给金,
    判据「泛用数值(全队强度/给金/装备)→ 不绑」直辖;表外卡
    strategy_bindings() 返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定表零触碰(泛用给金不绑)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_dingqi_fuli_not_in_pick_effects_closed_set() -> None:
    """即时金写端负锁:定期福利不得入 PICK_INVEST_EFFECTS(本卡
    instant_gold 腿按族级待办维持零写端,入集 = 越约;全集逐名断言
    归存量闭集锁,此处只锁本卡键不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '即时金族写端未建,零获得时点世界写入(负向防线)'
