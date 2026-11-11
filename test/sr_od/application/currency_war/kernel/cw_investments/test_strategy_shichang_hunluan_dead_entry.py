"""市场混乱(201901)零改动定论反向锁(镜像 src = 无——本卡零注册零消费)。

测试面依据 = 原稿锁面 §4
(原稿评审锁 判定:零改动定论——「在奖励节点的备战阶段，你的商店每4秒
进行一次强制刷新，持续7次。」= 墙钟定时类,desc 未写明不实机查 + 定时轴
零建模已登记,TriggerKind 现值 8 成员无定时形态;零注册零消费端零披露键,
fields.md §3.2.18 定时自动类预登行承载假设申报):

- 反向锁:策略侧全套注册表(STRATEGY_EFFECTS/STRATEGY_ECONOMY/
  STRATEGY_GRANTS/PICK_INVEST_EFFECTS/绑定表)零「市场混乱」条目;
  kernel/sim 全域零消费符号。任何后续批为该卡建载体或消费端 = 本锁红,
  须先取得用户定为(定时轴建模属另批立项面)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_effects import (
    PICK_INVEST_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
)

_CARD = '市场混乱'


def test_shichang_hunluan_dead_entry_zero_registration() -> None:
    """零改动定论反向锁:卡面已登记(数据面)但策略侧五注册表零条目;
    base 名入 INVESTMENT_STRATEGIES(数据注册行唯一存在形态)。"""
    assert _CARD in INVESTMENT_STRATEGIES, '卡面数据行已登记(唯一存在形态)'
    assert _CARD not in STRATEGY_EFFECTS, '零 EffectSpec 条目(零建模)'
    assert _CARD not in STRATEGY_ECONOMY, '零 EconomyEffect 条目'
    assert _CARD not in STRATEGY_GRANTS, '零发放条目'
    assert _CARD not in PICK_INVEST_EFFECTS, '零选卡效果登记'
    for binding_pair in STRATEGY_BINDINGS.values():
        assert _CARD not in binding_pair, '零绑定登记'
