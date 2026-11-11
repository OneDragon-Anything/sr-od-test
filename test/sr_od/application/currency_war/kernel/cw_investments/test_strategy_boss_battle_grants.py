"""策略卡首领战后随机装备发放登记表测试(镜像 src = kernel/
cw_investments.py 的 STRATEGY_BOSS_BATTLE_GRANTS + 构建校验)。

测试面依据 = 设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 8 +
已退役评审稿(校验面按 2026-10-28 治理判据分诊 + T-163 R1 先例同形:
「只能由写表人笔误触发的校验删」——类别词/件数值形手抄笔误类不落校验;
「能被游戏版本变更独立触发的漂移哨留」——孤儿键一哨全落;直构形态先例 =
同目录 test_strategy_encounter_battle_grants.py);T-167 展开卡扩名沿
设计稿(原件已退役;§ 号 = 原稿节序)§4 锁 5(构建校验参数化确认:
新行过孤儿键哨 = 闭集对拍 + 逐行 ∈ 策略注册表,值形/件数对账归本表
逐行参数化,治理后形零新增校验):
- 登记单一源:行值 = 卡面效果原文直读(枪在手 id 200501:首领战后 1 件
  随机简易装备;枪在手+ id 200502 战后效果条目与模式卡逐字同句同值,即时效果条目
  「立刻获得2件」另入 cw_gain_effects 泛化随机装备表行,两条效果条目触发时点
  异构分表);表只收「首领战后随机装备采样」触发器形状,
  与 STRATEGY_ENCOUNTER_BATTLE_GRANTS(占席道具确定发放)形状异构不共表
  (扩形状各建各表),族内后续卡各建各批;
- 构建校验 1 条(漂移哨,import 即炸语义经直调校验函数锁定):孤儿键
  (键 ∈ INVESTMENT_STRATEGIES——版本更新改名/移除后静默失联,import 期
  哨把拦截面前移到构建期)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BOSS_BATTLE_GRANTS,
    _validate_strategy_boss_battle_grants,
    equips_by_category,
)

#: 族现役成员闭集(卡名 → 行值):枪在手(200501 模式卡)+ 枪在手+
#: (200502 展开卡,战后效果条目与模式卡逐字同句同值;同族后续卡各自独立批)。
_CARD_ROWS: dict[str, tuple[str, int]] = {
    '枪在手': ('简易', 1),
    '枪在手+': ('简易', 1),
}
_CAT = '简易'


def test_registry_rows_closed_set() -> None:
    """登记面闭集:族现役两成员(禁顺手代登记,同族后续卡各自独立批,
    扩名随批申报)。"""
    assert set(STRATEGY_BOSS_BATTLE_GRANTS) == set(_CARD_ROWS), \
        f'注册面漂移: {sorted(STRATEGY_BOSS_BATTLE_GRANTS)!r}'


@pytest.mark.parametrize(('card', 'row'), sorted(_CARD_ROWS.items()))
def test_registry_row_single_source(card: str,
                                    row: tuple[str, int]) -> None:
    """登记单一源(逐行参数化):行值 = 卡面效果原文直读(「首领战后,
    获得1件随机简易装备」→ (装备类别词, 件数) 扁平二元组单档);类别池
    非空(数据性质锁,池派生单一源 = equips_by_category 注册表派生);
    键 ∈ 策略注册表(孤儿哨现值通过 = import 过闸即证,显式对拍防静默
    漂移——T-167 §4 锁 5 构建校验参数化确认)。"""
    assert STRATEGY_BOSS_BATTLE_GRANTS[card] == row, \
        f'行值漂移: {STRATEGY_BOSS_BATTLE_GRANTS!r}'
    assert len(equips_by_category(_CAT)) > 0, '类别池必须非空(数据性质)'
    assert card in INVESTMENT_STRATEGIES, '键必须在策略注册表'


def test_validator_orphan_key_raises(monkeypatch) -> None:
    """构建校验(孤儿哨,治理后形唯一哨):键不在策略注册表 → ValueError
    (import 即炸语义;直调校验函数锁同款行为,防哨被再删)。"""
    monkeypatch.setitem(STRATEGY_BOSS_BATTLE_GRANTS, '不存在的卡',
                        (_CAT, 1))
    with pytest.raises(ValueError, match='孤儿键'):
        _validate_strategy_boss_battle_grants()
