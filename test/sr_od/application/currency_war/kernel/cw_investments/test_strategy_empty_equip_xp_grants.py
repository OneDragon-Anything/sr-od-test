"""策略卡空仓经验登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_EMPTY_EQUIP_XP_GRANTS + 构建校验)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 2 + 已退役评审稿
§五④(卡面官方原文:「进入新节点时，如果物品栏和备战席没有任何装备(消耗品
除外)，则获得2经验值。」;直构形态先例 = 同目录
test_strategy_first_buy_xp_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(空仓 id 202401:每满足一次 +2 XP);
- 消耗品判据词表直锁 {工具, 特殊}(裁决点 2 默认口径 A 锚定——「特殊」类
  整体按消耗品,垃圾袋等特殊类持有时物品栏面仍算空仓);
- 构建校验负控:孤儿键单哨(2026-10-28 治理后形——XP 量系卡面手抄常量
  纯笔误类,值形查按治理不加;行值防线 = 锁 1 精确断言 + id 对拍)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import (
    CONSUMABLE_EQUIP_CATEGORIES,
    EQUIP_TOOL_CATEGORY,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_EMPTY_EQUIP_XP_GRANTS,
    _validate_strategy_empty_equip_xp_grants,
)

_CARD = '空仓'
_XP = 2


def test_registry_row_single_source() -> None:
    """登记单一源(锁 2):键集 = 族现役首例;行值 = 卡面直读 2;键 ∈ 策略
    注册表且 id 对拍(防改名/换 id 后静默错挂)。行值精确断言 = 值形防线的
    合规承载(治理裁定:登记笔误类对账归评审与测试,import 期形查不加)。"""
    assert set(STRATEGY_EMPTY_EQUIP_XP_GRANTS) == {_CARD, '空仓+'}, \
        '注册面 = 族现役两卡(同族后继卡各自独立批,禁顺手代登记)'
    assert STRATEGY_EMPTY_EQUIP_XP_GRANTS[_CARD] == _XP, \
        f'行值漂移: {STRATEGY_EMPTY_EQUIP_XP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:202401', \
        '注册行 id 对拍(202401,改名/换 id 漂移哨现值通过)'


def test_consumable_vocab_single_source() -> None:
    """消耗品判据词表直锁(裁决点 2 默认 A 锚定):{工具, 特殊},「工具」
    经 data 层 EQUIP_TOOL_CATEGORY 常量引名(零第二字面量);词表常量 =
    data 层单一源(kernel 禁本地平行定义——import 即验)。"""
    assert frozenset({'工具', '特殊'}) == CONSUMABLE_EQUIP_CATEGORIES, \
        f'词表漂移: {CONSUMABLE_EQUIP_CATEGORIES!r}'
    assert EQUIP_TOOL_CATEGORY == '工具'
    assert EQUIP_TOOL_CATEGORY in CONSUMABLE_EQUIP_CATEGORIES


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_EMPTY_EQUIP_XP_GRANTS, '不存在的卡', 2)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_empty_equip_xp_grants()
