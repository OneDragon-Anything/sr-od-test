"""策略卡战后触发发放登记表测试(镜像 src = kernel/cw_investments.py 的
STRATEGY_ENCOUNTER_BATTLE_GRANTS + 构建校验)。

测试面依据 = 迭代设计 designs/T-105-yizhan-yangzhan.md §4 锁 7(校验面按
2026-10-28 治理判据分诊:「只能由写表人笔误触发的校验删」——值形/可空形
手抄笔误类不落校验;「能被游戏版本变更独立触发的漂移哨留」——孤儿键/
道具名漂移两哨全落;直构形态先例 = 同目录 test_strategy_conditional_
grants.py):
- 登记单一源:行值 = 卡面效果原文直读(以战养战 id 101501:每次遭遇节点
  战斗后 1 个简易武装箱;金腿「获得6金币」归 STRATEGY_ECONOMY instant_
  gold 已登记不进本表);表只收「遭遇战后」触发器形状,族内后续卡各建各批;
- 构建校验 2 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  道具名漂移(占席道具词表外——BENCH_ITEM_NAMES 为游戏数据派生,版本
  改名/移除可独立触发;落席原语查名字→类别映射 KeyError 响亮但迟,import
  期哨把拦截面前移到构建期)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_NAMES,
    INVESTMENT_STRATEGIES,
    STRATEGY_ENCOUNTER_BATTLE_GRANTS,
    _validate_strategy_encounter_battle_grants,
)

_CARD = '以战养战'
_ITEM = '简易武装箱'


def test_registry_row_single_source() -> None:
    """登记单一源:以战养战行 = 卡面效果原文直读(「在遭遇节点战斗后,
    获得1个【简易武装箱】」→ 战后发放占席道具 ×1);发放物 ∈ 占席道具
    词表(数据性质锁,校验面归构建校验);键 ∈ 策略注册表(孤儿哨现值
    通过 = import 过闸即证,显式对拍防静默漂移)。"""
    assert set(STRATEGY_ENCOUNTER_BATTLE_GRANTS) == {_CARD}, \
        '注册面 = 族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    assert STRATEGY_ENCOUNTER_BATTLE_GRANTS[_CARD] == (_ITEM,), \
        f'行值漂移: {STRATEGY_ENCOUNTER_BATTLE_GRANTS!r}'
    assert _ITEM in BENCH_ITEM_NAMES, '发放物必须 ∈ 占席道具词表'
    assert _CARD in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在策略注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(STRATEGY_ENCOUNTER_BATTLE_GRANTS, '不存在的卡',
                        (_ITEM,))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_encounter_battle_grants()


def test_validator_item_name_drift_raises(monkeypatch) -> None:
    """构建校验②(道具名漂移哨):登记道具 ∉ BENCH_ITEM_NAMES →
    ValueError(版本改名/漏并入可独立触发)。运行期实况 = 落席原语查
    映射 KeyError 响亮但迟(潜伏到持卡局首次遭遇结算才炸),import 期哨
    是构建期拦截面,本锁防哨被再删。"""
    monkeypatch.setitem(STRATEGY_ENCOUNTER_BATTLE_GRANTS, _CARD,
                        ('不存在的道具',))
    with pytest.raises(ValueError, match='道具名漂移'):
        _validate_strategy_encounter_battle_grants()
