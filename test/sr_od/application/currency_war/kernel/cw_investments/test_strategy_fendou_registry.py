"""奋斗协议(id 301801)注册行双值锁(cw_investments 分目录镜像;单卡
注册行直测锁家族形,先例 = 同目录 test_strategy_gailv_entry.py)。

测试面依据 = 迭代设计 designs/T-313-fendou-xieyi.md §4 锁 1(REVIEW
-T313 无需用户决定 6/6;卡面官方原文:「购买经验值消耗6点小队生命值而非金币。
首领战斗结束时回复50点小队生命值。」两条效果条目 = 血本位成本面 + 首领战回血
HP 把结果写进状态副本的实现分支):

- 注册行双值:xp_buy_hp_cost=6(成本币种切换)∧ boss_end_heal_hp=50
  (首领战斗结束回血,战斗结算型 HP 把结果写进状态副本的实现分支);
- 卡面单一源:effect = cw_invest_data plaza 原文逐字(rarity 棱彩);
- 两道闭集伴随(排除集血本位结算修饰组 + strategy_economy 三分不计分
  桶)由模块 import 面自动覆盖——strategy_economy._validate_field_
  classification 对未分类新字段 import 即炸,本文件不重复立锁本体
  (设计稿 §4 锁 6 口径)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
)

_CARD = '奋斗协议'
_FACE = ('购买经验值消耗6点小队生命值而非金币。'
         '首领战斗结束时回复50点小队生命值。')


def test_fendou_economy_registry_dual_values() -> None:
    """锁 1(注册行双值):血本位成本效果条目 6 + 首领战回血效果条目 50,数值全出
    卡面直读零占位。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.xp_buy_hp_cost == 6, '购经验血价效果条目 = 6'
    assert eff.boss_end_heal_hp == 50, '首领战回血效果条目 = 50'


def test_fendou_strategy_row_face_single_source() -> None:
    """卡面单一源:注册表 effect 与 rarity = plaza 数据行逐字(id 301801,
    cw_invest_data.py 数据行直对)。"""
    strategy = INVESTMENT_STRATEGIES[_CARD]
    assert strategy.effect == _FACE, '卡面原文逐字'
    assert strategy.rarity == '棱彩', '品质 = 棱彩'
    assert '301801' in strategy.source, f'id 溯源漂移: {strategy.source}'
