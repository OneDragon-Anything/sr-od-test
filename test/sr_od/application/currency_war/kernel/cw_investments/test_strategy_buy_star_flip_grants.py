"""策略卡购买翻星登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_BUY_STAR_FLIP_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-187-sifei-jinsheng.md(定稿)§2.1/§4 锁 1
+ 验收裁定 reviews/T-187-r1.md §2/§7(校验随 2026-10-28 治理收缩至孤儿
键单哨;卡面官方原文:「你购买的下1个4费角色将立刻升到2星。获得12金币。」;
直构形态先例 = 同目录 test_strategy_first_buy_xp_grants.py):
- 登记单一源:行值 = 卡面直读(四费晋升 id 202201:费用过滤档 4,目标
  星级 2);键 ∈ 策略注册表且 id 对拍(防改名/换 id 后静默错挂);
- 构建校验负控:孤儿键单哨(2026-10-28 治理后形,同家族
  test_strategy_first_buy_xp_grants.py——费用档/目标星级系卡面手抄
  常量,游戏数值改版只改「正确值」、正确转录值恒在域内,值域查纯笔误
  类按治理不加;顾问型跨表双登记互斥同判防呆类不加;行值防线 = 本锁
  精确断言 + id 对拍)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BUY_STAR_FLIP_GRANTS,
    _validate_strategy_buy_star_flip_grants,
)

_CARD = '四费晋升'
_ROW = (4, 2)


def test_registry_row_single_source() -> None:
    """登记单一源(锁 1):键集 = 族现役首例(同族后续卡各自独立批,
    禁顺手代登记);行值 = 卡面两维直读(费用过滤档 4/目标星级 2);
    键 ∈ 策略注册表且 id 对拍 plaza:202201。行值精确断言 = 治理裁定下
    登记笔误对账的合规承载(值域 import 期形查不加)。"""
    assert set(STRATEGY_BUY_STAR_FLIP_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例'
    assert STRATEGY_BUY_STAR_FLIP_GRANTS[_CARD] == _ROW, \
        f'行值漂移: {STRATEGY_BUY_STAR_FLIP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:202201', \
        '注册行 id 对拍(202201,改名/换 id 漂移哨现值通过)'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_BUY_STAR_FLIP_GRANTS, '不存在的卡', _ROW)
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_buy_star_flip_grants()
