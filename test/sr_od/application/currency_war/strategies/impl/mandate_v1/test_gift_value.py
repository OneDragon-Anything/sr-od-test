"""赠卡价值具名口径测试(镜像 src = strategies/impl/mandate_v1/
gift_value.py 的 named_gift_value;该镜像位首文件)。

测试面依据 = fields.md §5.2 效果缺口与载体登记 + 语义描述「概念股族
模式卡登记约定」:随机规格赠卡(阵营轴)/随机装备条目不入档位机器
估值域(gift_hit_tier 只读具名两字段)→ named_gift_value 恒 0——登记
概念股不产生策略层双重计分,与 random_faction_gift_value(随机阵营
路径,读环境 faction 字段)正交。
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    named_gift_value,
)


def test_named_gift_value_concept_stock_is_zero() -> None:
    """追击概念股具名赠卡分 = 0(fields.md §5.2 效果缺口与载体登记,
    先例形态 = 佩佩双断言的具名半边):赠卡档恒 off(off 档映射 0 分)
    → 具名口径恒 0;随机阵营成员的价值由 random_faction_gift_value 随机
    口径承载,具名口径不重复计分(零双重计分锁)。"""
    assert named_gift_value('追击概念股', frozenset()) == 0.0


def test_named_gift_value_ranxue_concept_stock_is_zero() -> None:
    """燃血概念股具名赠卡分 = 0(fields.md §5.2 效果缺口与载体登记,
    概念股族展开卡登记约定,追击首例同锁第二实例):赠卡档恒 off
    (off 档映射 0 分)→ 具名口径恒 0;随机阵营成员的价值由
    random_faction_gift_value 随机口径承载,具名口径不重复计分(零双重
    计分锁)。"""
    assert named_gift_value('燃血概念股', frozenset()) == 0.0
