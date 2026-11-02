"""策略卡羁绊档位条件发放注册表测试(镜像 src = kernel/cw_investments.py
的 STRATEGY_BOND_TIER_GRANTS + StrategyBondTierGrant + 构建校验)。

测试面依据 = 迭代设计 designs/T-271-mengjing-dawutai.md §4 锁 1/2
(REVIEW-T271 §3.1 校验面 M12 治理归类:三漂移哨全落、档位升序哨删——
「只能由写表人笔误触发的校验删」在册治理口径,升序性属值形/阈值形纯笔误
类,行值精确断言在本文件把关;直构形态先例 = 同目录
test_strategy_bond_battle_grants.py):

- 登记单一源:行值 = 卡面效果原文直读(「盛会之星羁绊激活时,战斗中
  首次激活3/7/10个不同的非独立羁绊后,获得【盛会之星星徽】」→
  (gate='盛会之星', tiers=(3,7,10), item='盛会之星星徽');档位 3/7/10
  为卡面明写常量入表——与门槛羁绊自身档位两套数值异构,禁随 FACTIONS
  改版静默漂移);触发-发放单拍制(结算拍状态评估直发,无节点窗载体
  句),与战后触发族两拍制时点语义异构各建各表;
- 构建校验 3 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  gate 羁绊漂移 / 装备名漂移;
- 数据对拍:gate ∈ FACTIONS(档位判据派生源在册)∧ item ∈ EQUIPMENTS
  (发放物身份在册),键 ∈ 策略注册表。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.data.cw_factions import FACTIONS
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BOND_TIER_GRANTS,
    StrategyBondTierGrant,
    _validate_strategy_bond_tier_grants,
)

#: 族现役成员闭集(卡名 → 行值):首例单成员(同族后续卡各自独立批,
#: 禁顺手代登记,扩名随批申报)。
_CARD_ROWS: dict[str, StrategyBondTierGrant] = {
    '梦境大舞台': StrategyBondTierGrant(
        gate_faction='盛会之星', tiers=(3, 7, 10), item='盛会之星星徽'),
}


def test_registry_rows_closed_set() -> None:
    """登记面闭集:族现役单成员(表外卡零条目 = 触发函数集合语义的
    对偶面,禁从效果原文自动猜装)。"""
    assert set(STRATEGY_BOND_TIER_GRANTS) == set(_CARD_ROWS), \
        f'注册面漂移: {sorted(STRATEGY_BOND_TIER_GRANTS)!r}'


@pytest.mark.parametrize(('card', 'row'), sorted(_CARD_ROWS.items()))
def test_registry_row_single_source(card: str,
                                    row: StrategyBondTierGrant) -> None:
    """登记单一源(逐行参数化):行值 = 卡面效果原文直读(gate 羁绊 /
    档位 3/7/10 / 发放物三维全为卡面明写常量);键 ∈ 策略注册表(孤儿
    哨现值通过 = import 过闸即证,显式对拍防静默漂移)。"""
    assert STRATEGY_BOND_TIER_GRANTS[card] == row, \
        f'行值漂移: {STRATEGY_BOND_TIER_GRANTS!r}'
    assert card in INVESTMENT_STRATEGIES, '键必须在策略注册表'


@pytest.mark.parametrize(('card', 'row'), sorted(_CARD_ROWS.items()))
def test_registry_row_data_crosscheck(card: str,
                                      row: StrategyBondTierGrant) -> None:
    """数据对拍锁:gate ∈ FACTIONS(激活判据 tiers[0] 派生源在册)∧
    item ∈ EQUIPMENTS(发放物在册;错名运行期 = 幻影装备盲追加,import
    哨外第二道表域对账)。"""
    assert row.gate_faction in FACTIONS, \
        f'gate 羁绊漂移: {row.gate_faction!r}'
    assert row.item in EQUIPMENTS, f'发放物漂移: {row.item!r}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验负控①(孤儿哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '不存在的卡',
        StrategyBondTierGrant(gate_faction='盛会之星', tiers=(3, 7, 10),
                              item='盛会之星星徽'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bond_tier_grants()


def test_validator_gate_faction_drift_raises(monkeypatch) -> None:
    """构建校验负控②(gate 漂移哨):gate_faction 不在 FACTIONS →
    ValueError(档位判据派生源失联 = 条件腿静默失效,构建期响亮拦截)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '梦境大舞台',
        StrategyBondTierGrant(gate_faction='不存在的羁绊', tiers=(3, 7, 10),
                              item='盛会之星星徽'))
    with pytest.raises(ValueError, match='gate 羁绊漂移'):
        _validate_strategy_bond_tier_grants()


def test_validator_item_drift_raises(monkeypatch) -> None:
    """构建校验负控③(装备名漂移哨):item 不在 EQUIPMENTS →
    ValueError(发放物身份失联,错名入栏 = 幻影装备)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '梦境大舞台',
        StrategyBondTierGrant(gate_faction='盛会之星', tiers=(3, 7, 10),
                              item='不存在的装备'))
    with pytest.raises(ValueError, match='装备名漂移'):
        _validate_strategy_bond_tier_grants()
