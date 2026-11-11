"""策略卡备战席计数经验登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_BENCH_COUNT_XP_GRANTS + 构建校验)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 1 +
已退役评审稿(§ 号 = 原稿节序)§四④(卡面官方原文:「节点开始时，如果备战席角色小于等于
4名，则获得3经验。」;直构形态先例 = 同目录
test_strategy_empty_equip_xp_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(人才空洞 id 202601:值 =
  (比较符, 备战席单位数门槛, 每满足一次发放的 XP 量) 三元组);
- 行值精确断言 + id 对拍 = 值形/值域防线的合规承载(2026-10-28 治理
  裁定:登记笔误类对账归评审与测试,import 期形查不加);
- 构建校验负控:孤儿键单哨(治理后形——比较符闭集/门槛/XP 量系卡面
  手抄常量纯笔误类,值形/值域查按治理不加)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BENCH_COUNT_XP_GRANTS,
    _validate_strategy_bench_count_xp_grants,
)

_CARD = '人才空洞'
_ROW = ('le', 4, 3)


def test_registry_row_single_source() -> None:
    """登记单一源(锁 1):键集 = 族现役首例;行值 = 卡面直读三元组
    (≤4 名/每次 +3);键 ∈ 策略注册表且 id 对拍(防改名/换 id 后静默
    错挂)。姊妹人才济济(202701,'ge' 行)归其后继批,禁顺手代登记。"""
    assert set(STRATEGY_BENCH_COUNT_XP_GRANTS) == {_CARD, '人才济济'}, \
        '注册面 = 族现役两卡(同族后继卡独立批,禁顺手代登记)'
    assert STRATEGY_BENCH_COUNT_XP_GRANTS[_CARD] == _ROW, \
        f'行值漂移: {STRATEGY_BENCH_COUNT_XP_GRANTS!r}'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'
    assert INVESTMENT_STRATEGIES[_CARD].source == 'plaza:202601', \
        '注册行 id 对拍(202601,改名/换 id 漂移哨现值通过)'
    assert INVESTMENT_STRATEGIES[_CARD].name == _CARD, '名字键对拍'

    assert STRATEGY_BENCH_COUNT_XP_GRANTS['人才济济'] == ('ge', 8, 3), \
        f"姊妹行值漂移: {STRATEGY_BENCH_COUNT_XP_GRANTS['人才济济']!r}"
    assert INVESTMENT_STRATEGIES['人才济济'].source == 'plaza:202701', \
        '姊妹注册行 id 对拍(202701,改名/换 id 漂移哨现值通过)'
    assert INVESTMENT_STRATEGIES['人才济济'].name == '人才济济', '姊妹名字键对拍'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_BENCH_COUNT_XP_GRANTS, '不存在的卡',
                        ('le', 4, 3))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bench_count_xp_grants()
