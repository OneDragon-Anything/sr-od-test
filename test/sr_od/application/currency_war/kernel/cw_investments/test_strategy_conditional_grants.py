"""策略卡条件发放登记表测试(镜像 src = kernel/cw_investments.py 的
StrategyConditionalGrant + STRATEGY_CONDITIONAL_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-102-guimo-xiaoying.md §4 锁 1(经硬裁定
收缩:防登记笔误类校验「threshold 形/下界、item 装备名闭集」不落校验
不落锁,2026-10-28 治理口径同源——只留漂移哨,T-98 批收缩先例同形):
- 登记单一源:行值 = 卡面效果原文直读(规模效应 id 101301/完美投影仪/
  同名阈值 8);卡面原文 = 「首次拥有8个一样的角色时,获得1个【完美
  投影仪】。」(cw_invest_data.PLAZA_AUGMENTS 同 id 行);表键集闭族
  现役卡(同族后续卡各自独立批领取,禁顺手代登记);
- 构建校验 2 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  id 双匹配(改名且 id 仍在的漂移也炸)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_CONDITIONAL_GRANTS,
    StrategyConditionalGrant,
    _validate_strategy_conditional_grants,
)


def test_scale_effect_registry_row_single_source() -> None:
    """登记单一源:规模效应行 = 卡面效果原文直读(「获得1个【完美投影
    仪】」→ 具名装备;「8个一样的角色」→ 同名阈值 8,单位数口径);
    发放物 = 装备注册表成员(工具类,cw_equipment_data 在册);base 溯源
    id 对拍(id 101301 ↔ plaza:101301)。"""
    assert set(STRATEGY_CONDITIONAL_GRANTS) == {'规模效应'}, \
        '注册面 = 族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    row = STRATEGY_CONDITIONAL_GRANTS['规模效应']
    assert row == StrategyConditionalGrant(id='101301', item='完美投影仪',
                                           threshold_same_name=8)
    assert row.item in cw_investments.EQUIPMENTS, \
        '发放物必须 ∈ 装备注册表(数据性质锁,校验面归评审)'
    base = INVESTMENT_STRATEGIES['规模效应']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_CONDITIONAL_GRANTS, '不存在的卡',
        StrategyConditionalGrant(id='999999', item='完美投影仪',
                                 threshold_same_name=8))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_conditional_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_CONDITIONAL_GRANTS, '规模效应',
        StrategyConditionalGrant(id='101999', item='完美投影仪',
                                 threshold_same_name=8))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_conditional_grants()
