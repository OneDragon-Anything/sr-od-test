"""策略卡首购经验登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_FIRST_BUY_XP_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-163-luansheng-sushu.md(定稿)§4 锁 1/2
+ REVIEW-T163 §4② + 验收 R1 裁定(reviews/T-163-r1.md §4:值形查违
2026-10-28 治理随批移除;卡面官方原文:「获得本投资策略后，首次购买
1/2/3/4/5费角色时，获得2/3/5/7/11点经验值。」;直构形态先例 = 同目录
test_strategy_encounter_battle_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(孪生素数 id 200201:五费用档
  1/2/3/4/5 → 2/3/5/7/11 XP,值下标 = 费用−1);五桶全取上限 = 28
  (求和算例随锁,与 fields.md/invest_effects.md 权威版本订正值对拍);
- 构建校验负控:孤儿键单哨(2026-10-28 治理后形——五桶值系手抄常量
  纯笔误类,值形查按治理不加;行值防线 = 锁 1 精确断言 + id 对拍,
  强于 import 期形查)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_FIRST_BUY_XP_GRANTS,
    _validate_strategy_first_buy_xp_grants,
)

_CARD = '孪生素数'
_AMOUNTS = (2, 3, 5, 7, 11)


def test_registry_row_single_source() -> None:
    """登记单一源(锁 1):键集 = 族现役首例;行值 = 卡面五桶直读;
    键 ∈ 策略注册表且 id 对拍(防改名/换 id 后静默错挂);五桶全取上限
    求和 = 28(2+3+5+7+11,权威版本口径)。行值精确断言 = 值形防线的合规
    承载(治理裁定:登记笔误类对账归评审与测试,import 期形查不加)。"""
    assert set(STRATEGY_FIRST_BUY_XP_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_FIRST_BUY_XP_GRANTS[_CARD] == _AMOUNTS, \
        f'行值漂移: {STRATEGY_FIRST_BUY_XP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:200201', \
        '注册行 id 对拍(200201,改名/换 id 漂移哨现值通过)'
    assert sum(_AMOUNTS) == 28, '五桶全取上限 = 28(38 系串档误值,已订正)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_FIRST_BUY_XP_GRANTS, '不存在的卡',
                        _AMOUNTS)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_first_buy_xp_grants()
