"""策略卡条件节点序列改写注册表测试(镜像 src = kernel/cw_investments.py
的 STRATEGY_NODE_REWRITE_TRIGGERS + 构建校验)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-318-jueyi-yule-xingqiu.md §4 锁 1(REVIEW-T318 §四 M12 治理归类:校验面
收缩为孤儿键漂移哨 1 条——金门槛值域/触发时机闭集/改写词闭集三笔误哨删,
「只能由写表人笔误触发的校验删」已登记治理口径;改写词表值笔误后果 = 决策
函数词表分派 KeyError 响亮可见,行值精确断言在本文件把关;直构形态先例 =
同目录 test_strategy_bond_tier_grants.py):

- 登记单一源:行值 = 卡面效果原文直读(「进入战斗时，若拥有180枚金币，
  将本局游戏剩余的非首领节点替换为奖励节点」→ ('battle_entry', 180,
  'remaining_non_boss_to_reward');180 = 卡面明写常量入表,禁随经济环境
  静默漂移);
- 构建校验 1 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键;
- 数据对拍:键 ∈ 策略注册表(孤儿哨现值通过 = import 过闸即证,显式
  对拍防静默漂移);与 env 侧改写注册表(ENV_NODE_REWRITE_RULES)键域
  互斥(彼表键 = 环境名,本表键 = 策略卡名,两户口禁互挂)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_NODE_REWRITE_TRIGGERS,
    _validate_strategy_node_rewrite_triggers,
)

#: 族现役成员闭集(卡名 → 行值):首例单成员(同族后续卡各自独立批,
#: 禁顺手代登记,扩名随批申报)。
_CARD_ROWS: dict[str, tuple[str, int, str]] = {
    '决议:娱乐星球': ('battle_entry', 180, 'remaining_non_boss_to_reward'),
}


def test_registry_rows_closed_set() -> None:
    """登记面闭集:族现役单成员(表外卡零条目 = 触发函数集合语义的
    对偶面,禁从效果原文自动猜装)。"""
    assert set(STRATEGY_NODE_REWRITE_TRIGGERS) == set(_CARD_ROWS), \
        f'注册面漂移: {sorted(STRATEGY_NODE_REWRITE_TRIGGERS)!r}'


@pytest.mark.parametrize(('card', 'row'), sorted(_CARD_ROWS.items()))
def test_registry_row_single_source(card: str,
                                    row: tuple[str, int, str]) -> None:
    """登记单一源(逐行参数化):行值 = 卡面效果原文直读(触发时机类型
    读法仅普通战斗/金门槛 180/改写词「剩余非首领→奖励」;键 ∈ 策略
    注册表,孤儿哨现值通过 = import 过闸即证)。"""
    assert STRATEGY_NODE_REWRITE_TRIGGERS[card] == row, \
        f'行值漂移: {STRATEGY_NODE_REWRITE_TRIGGERS!r}'
    assert card in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_keys_disjoint_from_env_rewrite_registry() -> None:
    """两表键域互斥锁:本表键(策略卡名)不得出现在 env 改写注册表
    (键 = 环境名,户口互斥申报;校验①孤儿键兜底的同向显式对拍)。"""
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        ENV_NODE_REWRITE_RULES,
    )
    clash = set(STRATEGY_NODE_REWRITE_TRIGGERS) & set(ENV_NODE_REWRITE_RULES)
    assert not clash, f'两注册表键域互斥破约: {sorted(clash)}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验负控(孤儿哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(
        STRATEGY_NODE_REWRITE_TRIGGERS, '不存在的卡',
        ('battle_entry', 180, 'remaining_non_boss_to_reward'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_node_rewrite_triggers()
