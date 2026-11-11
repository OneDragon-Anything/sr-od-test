"""策略卡卡级待建模登记锁·赞美太阳(mandate_v1/strategy_economy 分目录
镜像;宿主 test_invest_strategy.py 超线禁追加,先例 = kernel 侧各登记
锁分目录文件)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 3(效果条目 1 登记归宿裁决点 1 默认案:PENDING 卡级
登记 + 条件 XP 族状态副本通道,空仓/人才空洞同形):
- 已登记成员 + 描述非空 + 行值精确断言(登记笔误对账归测试,治理裁定
  2026-10-28 形);
- _validate_pending_modeling_registry 直调不炸(①孤儿键 ②空描述
  ③全默认条目已登记 ④辖域闭集四查全过——加行不得破既有断言);
- 既有点名断言(test_invest_strategy.test_pending_modeling_registry_
  shape)零改动原样绿,本文件不重复。
"""
from __future__ import annotations

from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    STRATEGY_ECONOMY_PENDING_MODELING,
    _validate_pending_modeling_registry,
)

_CARD = '赞美太阳'
_ROW = ('装备计数经验发放已建状态副本写入通道 STRATEGY_EQUIP_COUNT_XP_GRANTS;'
        '估值零登记维持')


def test_zanmei_pending_row_registered() -> None:
    """登记锁:成员已登记 + 描述非空 + 行值精确断言(动态计数 XP 不挂
    xp_per_node 无条件通道,治理口径 = 已建状态副本通道 + 估值零登记维持)。"""
    assert _CARD in STRATEGY_ECONOMY_PENDING_MODELING, '卡级已登记'
    desc = STRATEGY_ECONOMY_PENDING_MODELING[_CARD]
    assert desc, '描述非空'
    assert desc == _ROW, f'行值漂移: {desc!r}'


def test_pending_registry_validator_passes_with_new_row() -> None:
    """直调不炸(锁 3):加行后四查全过(孤儿键无/描述非空/全默认条目
    已登记/辖域闭集已登记——既有断言零触碰的回归面)。"""
    _validate_pending_modeling_registry()
