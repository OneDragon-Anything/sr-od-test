"""策略卡首购经验登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_FIRST_BUY_XP_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-163-luansheng-sushu.md(定稿)§4 锁 1/2
+ REVIEW-T163 §4②(卡面官方原文:「获得本投资策略后，首次购买1/2/3/
4/5费角色时，获得2/3/5/7/11点经验值。」;直构形态先例 = 同目录
test_strategy_encounter_battle_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(孪生素数 id 200201:五费用档
  1/2/3/4/5 → 2/3/5/7/11 XP,值下标 = 费用−1);五桶全取上限 = 28
  (求和算例随锁,与 fields.md/invest_effects.md 正本订正值对拍);
- 构建校验 2 条(import 即炸语义经直调校验函数锁定):孤儿键 / 值形
  (恰 5 元全正 int tuple——值下标 = 费用−1 读表契约的前提,错形运行期
  零报错只错发放量,import 期哨把拦截面前移到构建期)。
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
    求和 = 28(2+3+5+7+11,正本口径)。"""
    assert set(STRATEGY_FIRST_BUY_XP_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_FIRST_BUY_XP_GRANTS[_CARD] == _AMOUNTS, \
        f'行值漂移: {STRATEGY_FIRST_BUY_XP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:200201', \
        '注册行 id 对拍(200201,改名/换 id 漂移哨现值通过)'
    assert sum(_AMOUNTS) == 28, '五桶全取上限 = 28(38 系串档误值,已订正)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_FIRST_BUY_XP_GRANTS, '不存在的卡',
                        _AMOUNTS)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_first_buy_xp_grants()


def test_validator_value_shape_raises(monkeypatch) -> None:
    """构建校验②(值形):非 5 元组 / 含非正或非 int 元 → ValueError
    (值下标 = 费用−1 读表契约前提:短元组越域、错形只错发放量且运行期
    零报错,import 期哨是唯一响亮拦截面)。"""
    for bad in ((2, 3, 5, 7), (2, 3, 5, 7, 11, 13), (2, 3, 5, 7, 0),
                (2, 3, 5, 7, '11')):
        monkeypatch.setitem(STRATEGY_FIRST_BUY_XP_GRANTS, _CARD, bad)
        with pytest.raises(ValueError, match='值形'):
            _validate_strategy_first_buy_xp_grants()
