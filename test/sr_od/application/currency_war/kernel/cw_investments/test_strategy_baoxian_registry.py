"""星际和平保险(id 303001)注册行双值锁(cw_investments 分目录镜像;单卡
注册行直测锁家族形,先例 = 同目录 test_strategy_fendou_registry.py)。

测试面依据 = 迭代设计 designs/T-325-xingji-heping-baoxian.md §4 锁 1
(REVIEW-T325 无需用户决定 7/7;卡面官方原文:「获得等同于你已损失生命数量的金币。
战斗后恢复10点小队生命值。」两条效果条目 = 选卡衍生金把结果写进状态副本的实现分支 + 战斗结束回血 HP
把结果写进状态副本的实现分支):

- 注册行双值:gold_per_hp_lost_now is True(选卡时点已损血数金,布尔
  旗标字段)∧ battle_end_heal_hp=10(战斗结束回血,战斗结算型 HP 状态副本
  腿,数值 = 卡面直读);
- 卡面单一源:effect = cw_invest_data plaza 原文逐字(rarity 棱彩);
- 两道闭集伴随(排除集战斗结算修饰组 + strategy_economy 三分不计分
  桶)由模块 import 面自动覆盖——strategy_economy._validate_field_
  classification 对未分类新字段 import 即炸,本文件不重复立锁本体
  (T-313 同款口径)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
)

_CARD = '星际和平保险'
_FACE = ('获得等同于你已损失生命数量的金币。'
         '战斗后恢复10点小队生命值。')


def test_baoxian_economy_registry_dual_values() -> None:
    """锁 1(注册行双值):选卡衍生金旗标 True + 战斗结束回血腿 10,
    数值全出卡面直读零占位。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.gold_per_hp_lost_now is True, '选卡衍生金腿旗标 = True'
    assert eff.battle_end_heal_hp == 10, '战斗结束回血腿 = 10'


def test_baoxian_strategy_row_face_single_source() -> None:
    """卡面单一源:注册表 effect 与 rarity = plaza 数据行逐字(id 303001,
    cw_invest_data.py 数据行直对)。"""
    strategy = INVESTMENT_STRATEGIES[_CARD]
    assert strategy.effect == _FACE, '卡面原文逐字'
    assert strategy.rarity == '棱彩', '品质 = 棱彩'
    assert '303001' in strategy.source, f'id 溯源漂移: {strategy.source}'
