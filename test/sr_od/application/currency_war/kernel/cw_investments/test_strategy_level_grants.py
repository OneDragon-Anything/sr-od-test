"""策略卡等级触发发放登记表测试(镜像 src = kernel/cw_investments.py 的
StrategyLevelGrant + STRATEGY_LEVEL_GRANTS + 构建校验)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§4 锁 1/11/12
(校验面按 2026-10-28 治理判据分诊:「只能由写表人笔误触发的校验删」
——level_target 形/值域 = 手抄常量纯笔误类不落校验不落锁;「能被游戏
版本变更独立触发的漂移哨留」——孤儿键/id 双匹配/装备名漂移三哨全落):
- 登记单一源:行值 = 卡面效果原文直读(钻石商人 id 130401/触发等级 9/
  财富宝钻;卡面原文 = 「升到9级时，获得【财富宝钻】。」,
  cw_invest_data.PLAZA_AUGMENTS 同 id 行);表键集闭族现役卡(同族后续
  卡各自独立批领取,禁顺手代登记);
- 键集闭集锁 + 存量家族表零扰动(本卡批零改姊妹表,防顺手并表);
- 构建校验 3 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键 /
  id 双匹配(改名且 id 仍在的漂移也炸)/ 装备名漂移(注册表无此装备)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_STREAK_GRANTS,
    INVESTMENT_STRATEGIES,
    STRATEGY_CONDITIONAL_GRANTS,
    STRATEGY_LEVEL_GRANTS,
    StrategyLevelGrant,
    _validate_strategy_level_grants,
)


def test_diamond_merchant_registry_row_single_source() -> None:
    """登记单一源:钻石商人行 = 卡面效果原文直读(「升到9级时」→ 触发
    等级 9;「获得【财富宝钻】」→ 具名装备);发放物 = 装备注册表成员
    (cw_equipment_data 已登记);base 溯源 id 对拍(130401 ↔ plaza:130401)。"""
    assert set(STRATEGY_LEVEL_GRANTS) == {'钻石商人'}, \
        '注册面 = 族现役首例(同族后续卡各自独立批,禁顺手代登记)'
    row = STRATEGY_LEVEL_GRANTS['钻石商人']
    assert row == StrategyLevelGrant(id='130401', level_target=9,
                                     item='财富宝钻')
    assert row.item in cw_investments.EQUIPMENTS, \
        '发放物必须 ∈ 装备注册表(数据性质锁,校验面归评审)'
    base = INVESTMENT_STRATEGIES['钻石商人']
    assert base.source == f"plaza:{row.id}", \
        f'溯源 id 对拍失同步: {base.source}'


def test_sibling_family_tables_untouched() -> None:
    """存量家族表零扰动(锁 11 静态面):本卡「各建各表」不并入姊妹表
    ——STRATEGY_CONDITIONAL_GRANTS(同名计数门)/ ENV_STREAK_GRANTS
    (连胜触发器)键集维持各自现役行,防实现批顺手并表/串行。"""
    assert set(STRATEGY_CONDITIONAL_GRANTS) == {'规模效应'}, \
        '条件计数门姊妹表被并入/串行'
    assert ENV_STREAK_GRANTS == {'深井角斗场': (5, '财富宝钻')}, \
        '连胜触发器姊妹表被并入/串行'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验①(孤儿哨):键不在 base 注册表 → ValueError(import 即炸
    语义;直调校验函数锁同款行为)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_LEVEL_GRANTS, '不存在的卡',
        StrategyLevelGrant(id='999999', level_target=9, item='财富宝钻'))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_level_grants()


def test_validator_id_mismatch_raises(monkeypatch) -> None:
    """构建校验②(id 双匹配哨):登记 id ≠ base 溯源 id → ValueError
    (版本改名且 id 仍在的漂移也炸)。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_LEVEL_GRANTS, '钻石商人',
        StrategyLevelGrant(id='130499', level_target=9, item='财富宝钻'))
    with pytest.raises(ValueError, match='id 漂移'):
        _validate_strategy_level_grants()


def test_validator_item_equip_name_drift_raises(monkeypatch) -> None:
    """构建校验③(装备名漂移哨):登记 item ∉ EQUIPMENTS → ValueError
    (EQUIPMENTS = 游戏数据派生注册表,版本更新改名/移除装备可独立触发,
    STRATEGY_CONDITIONAL_GRANTS 校验③同形)。错名运行期实况 = 静默
    幻影:gain_equipment 盲追加 + on_equipment_gained .get() 安静不写 +
    live 调用位返回值刻意忽略 → 静默幻影装备永久落一次性标志位零报错——import 期
    哨是唯一响亮拦截面,本锁防哨被再删。"""
    monkeypatch.setitem(
        cw_investments.STRATEGY_LEVEL_GRANTS, '钻石商人',
        StrategyLevelGrant(id='130401', level_target=9, item='不存在的装备'))
    with pytest.raises(ValueError, match='装备名漂移'):
        _validate_strategy_level_grants()
