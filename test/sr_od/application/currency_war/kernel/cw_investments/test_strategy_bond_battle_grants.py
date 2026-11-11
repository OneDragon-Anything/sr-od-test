"""策略卡羁绊条件战后发放登记表测试(镜像 src = kernel/cw_investments.py
的 STRATEGY_BOND_BATTLE_GRANTS + 构建校验)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4
锁 8 + 已退役评审稿(校验面按 2026-10-28 治理判据分诊,T-163 R1 先例同
形:「只能由写表人笔误触发的校验删」——阈值/类别词/件数值形手抄笔误类
不落校验;「能被游戏版本变更独立触发的漂移哨留」——孤儿键一哨全落;
直构形态先例 = 同目录 test_strategy_boss_battle_grants.py):
- 登记单一源:行值 = 卡面效果原文直读(「激活8个羁绊并完成一场战斗后,
  进入节点时获得5个随机星徽」→ (羁绊激活数阈值 8, 装备类别词 '星徽',
  件数 5) 扁平三元组单档,数值两枚为卡面明写常量);表只收「羁绊条件
  ×战后武装 ×节点窗交付」两拍制触发器形状,与战后触发族既有三表
  (占席道具确定发放/首领战后随机装备/胜利条件金)形状异构各建各表,
  族内后续卡各建各批;
- 构建校验 1 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键
  (键 ∈ INVESTMENT_STRATEGIES——版本更新改名/移除后静默失联,import 期
  哨把拦截面前移到构建期);
- 治理后形负向申报:类别池非空/阈值形/件数形不设 import 查(T-166 表
  同款 docstring 口径),池空运行期归触发函数 log 防御分支兜底,表值
  行为对账归本文件逐行参数化(类别池派生单一源数据性质锁保留)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BOND_BATTLE_GRANTS,
    _validate_strategy_bond_battle_grants,
    equips_by_category,
)

#: 族现役成员闭集(卡名 → 行值):首例单成员(同族后续卡各自独立批,
#: 禁顺手代登记,扩名随批申报)。
_CARD_ROWS: dict[str, tuple[int, str, int]] = {
    '不要小看我们的羁绊': (8, '星徽', 5),
}
_CAT = '星徽'


def test_registry_rows_closed_set() -> None:
    """登记面闭集:族现役单成员(表外卡零条目 = 触发函数集合语义的
    对偶面,禁从效果原文自动猜装)。"""
    assert set(STRATEGY_BOND_BATTLE_GRANTS) == set(_CARD_ROWS), \
        f'注册面漂移: {sorted(STRATEGY_BOND_BATTLE_GRANTS)!r}'


@pytest.mark.parametrize(('card', 'row'), sorted(_CARD_ROWS.items()))
def test_registry_row_single_source(card: str,
                                    row: tuple[int, str, int]) -> None:
    """登记单一源(逐行参数化):行值 = 卡面效果原文直读(「激活8个羁绊
    并完成一场战斗后,进入节点时获得5个随机星徽」→ (阈值, 类别, 件数)
    扁平三元组单档,不预泛化——首例触发器形状单一);类别池非空(数据
    性质锁,池派生单一源 = equips_by_category 注册表派生);键 ∈ 策略
    注册表(孤儿哨现值通过 = import 过闸即证,显式对拍防静默漂移)。"""
    assert STRATEGY_BOND_BATTLE_GRANTS[card] == row, \
        f'行值漂移: {STRATEGY_BOND_BATTLE_GRANTS!r}'
    assert len(equips_by_category(_CAT)) > 0, '类别池必须非空(数据性质)'
    assert card in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨,治理后形唯一哨):键不在策略注册表 → ValueError
    (import 即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(STRATEGY_BOND_BATTLE_GRANTS, '不存在的卡',
                        (8, _CAT, 5))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_bond_battle_grants()
