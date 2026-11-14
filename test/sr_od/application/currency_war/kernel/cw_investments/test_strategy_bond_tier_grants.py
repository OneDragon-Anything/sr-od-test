"""策略卡羁绊档位条件发放注册表测试(镜像 src = kernel/cw_investments.py
的 STRATEGY_BOND_TIER_GRANTS + StrategyBondTierGrant + 构建校验)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 1/2
(原稿评审锁(§ 号 = 原稿节序)§3.1 校验面 M12 治理归类:三漂移哨全落、档位升序哨删——
「只能由写表人笔误触发的校验删」已登记治理口径,升序性属值形/阈值形纯笔误
类,行值精确断言在本文件把关;直构形态先例 = 同目录
test_strategy_bond_battle_grants.py):

- 登记单一源:行值 = 卡面效果原文直读(gate 羁绊 / 档位 / 发放物三维全为
  卡面明写常量入表——与门槛羁绊自身档位两套数值异构,禁随羁绊注册表
  改版静默漂移);触发-发放单拍制(结算拍状态评估直发,无节点窗载体
  句),与战后触发族两拍制时点语义异构各建各表;
- 构建校验 3 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  gate 羁绊漂移 / 装备名漂移;
- 数据对拍:gate ∈ 羁绊注册表 trait_by_name(激活判据 tiers[0] 派生源
  已登记)∧ item ∈ EQUIPMENTS(发放物身份已登记),键 ∈ 策略注册表。

v4.7 换赛季退役态:唯一条目「梦境大舞台」已随羁绊消费点迁移批退役
(gate 门槛羁绊盛会之星入消失档,条件机制不存在;判据链语义重定义见
cw_gain_chain)——现表断言 = 空表退役态;三漂移哨结构保留,负控锁面经
注入条目延续(v4.7 新同族卡重采后按原语义恢复登记,哨防线原样生效)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_equipment_data import EQUIPMENTS
from sr_od.application.currency_war.data.cw_traits_data import trait_by_name
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BOND_TIER_GRANTS,
    StrategyBondTierGrant,
    _validate_strategy_bond_tier_grants,
)


def test_registry_current_value_and_validation_passes() -> None:
    """现表 = v4.7 退役态空表 + 直调校验器零异常(条目退役声明见
    src 表头注释;新条目登记时本断言即红灯强制复审,禁从效果原文
    自动猜装)。"""
    assert STRATEGY_BOND_TIER_GRANTS == {}
    _validate_strategy_bond_tier_grants()


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验负控①(孤儿哨):键不在策略注册表 → ValueError(import
    即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '不存在的卡',
        StrategyBondTierGrant(gate_faction='持续伤害', tiers=(3, 7, 10),
                              item='以太钻头'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bond_tier_grants()


def test_validator_gate_faction_drift_raises(monkeypatch) -> None:
    """构建校验负控②(gate 漂移哨):gate_faction 不在羁绊注册表 →
    ValueError(档位判据派生源失联 = 条件效果条目静默失效,构建期响亮拦截;
    注入键取策略注册表在册名,孤儿哨不拦、精确命中 gate 哨)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '躺平',
        StrategyBondTierGrant(gate_faction='不存在的羁绊', tiers=(3, 7, 10),
                              item='以太钻头'))
    with pytest.raises(ValueError, match='gate 羁绊漂移'):
        _validate_strategy_bond_tier_grants()


def test_validator_item_drift_raises(monkeypatch) -> None:
    """构建校验负控③(装备名漂移哨):item 不在 EQUIPMENTS →
    ValueError(发放物身份失联,错名入栏 = 幻影装备;注入键同负控②取
    在册名)。"""
    monkeypatch.setitem(
        STRATEGY_BOND_TIER_GRANTS, '躺平',
        StrategyBondTierGrant(gate_faction='持续伤害', tiers=(3, 7, 10),
                              item='不存在的装备'))
    with pytest.raises(ValueError, match='装备名漂移'):
        _validate_strategy_bond_tier_grants()


def test_negative_control_rows_registry_sanity() -> None:
    """负控注入行自检:沿用档 gate ∈ 羁绊注册表 ∧ item ∈ EQUIPMENTS
    (负控行本身合法,哨触发只靠被注入的漂移维——防负控写坏假绿)。"""
    assert '持续伤害' in trait_by_name
    assert '以太钻头' in EQUIPMENTS
