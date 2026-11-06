"""嘴硬注册面 + 败局修饰聚合 helper 测试(cw_investments 分目录镜像;
登记锁先例 = 同目录 test_strategy_dingqi_fuli_registry.py。超线主文件
test_cw_investments.py 禁追加,拆目录落位)。

测试面依据 = 迭代设计 designs/T-181-zuiying.md §4 锁 3/锁 4。卡面官方
原文(cw_invest_data.py):「战斗失败时，受到的小队生命值伤害提高5点，
但能维持原来的连胜数。获得6金币。」

- 注册面锁:STRATEGY_ECONOMY 条目三字段 = instant_gold=6 ∧
  loss_hp_extra=5 ∧ keep_streak_on_loss=True(数值 = 卡面 desc 逐字;
  金腿 = 选卡当场已登记,败局修饰两条效果条目 = 本批新增);败局修饰族非收入
  通道,is_economy_engine 恒 False(排除桶成员);
- 闭集落位锁:两字段 ∈ kernel 引擎排除桶(战斗结算修饰族划界;
  2026-10-28 治理后漏登记不炸,成员防线 = 本锁)+ 策略侧三分
  (keep_streak_on_loss ∈ 待建模桶——维持省下的连胜金流价值是轨迹依赖;
  loss_hp_extra ∈ 不计分桶负向结构登记——纯负向成本无正账可折);
- helper 纯锁:败局修饰聚合(逐名归一后直读注册表现值,卡直读禁
  aggregate_economy——其聚合字段集不含战斗结算修饰族字段,误走 =
  静默漏读);表外卡名跳过;空名单零修饰。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    _ENGINE_CHANNEL_EXCLUDED_FIELDS,
    STRATEGY_ECONOMY,
    is_economy_engine,
    strategy_loss_battle_modifier,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    _NOT_SCORED_FIELDS,
    _PENDING_MODELING_FIELDS,
)

_CARD = '嘴硬'


def test_zuiying_economy_registration_surface() -> None:
    """注册面锁:三字段全已登记且数值 = 卡面 desc 逐字(instant_gold=6
    选卡当场 / loss_hp_extra=5 败局伤害提高 / keep_streak_on_loss 败局
    连胜维持);败局修饰族非收入通道,引擎谓词恒 False。本测试存活同时
    证明构建校验通过(注册表孤儿键/双匹配闸在 import 期)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.instant_gold == 6, '选卡当场金 = 卡面「获得6金币」'
    assert eff.loss_hp_extra == 5, \
        '败局额外扣血 = 卡面「受到的小队生命值伤害提高5点」'
    assert eff.keep_streak_on_loss is True, \
        '败局连胜维持 = 卡面「能维持原来的连胜数」'
    assert is_economy_engine(eff) is False, \
        '战斗结算修饰族非收入通道(引擎排除桶划界)'


def test_zuiying_closed_set_classification() -> None:
    """闭集落位锁:kernel 引擎排除桶两字段已登记(治理后漏登记不炸,
    成员防线 = 本锁;难度族同款划界)+ 策略侧三分各归各桶——
    keep_streak_on_loss 待建模(维持的金流价值轨迹依赖未建模)、
    loss_hp_extra 不计分(纯负向成本,负向结构登记族)。"""
    assert 'loss_hp_extra' in _ENGINE_CHANNEL_EXCLUDED_FIELDS, \
        '败局额外扣血 ∈ 引擎排除桶(非收入通道)'
    assert 'keep_streak_on_loss' in _ENGINE_CHANNEL_EXCLUDED_FIELDS, \
        '败局连胜维持 ∈ 引擎排除桶(非收入通道)'
    assert 'keep_streak_on_loss' in _PENDING_MODELING_FIELDS, \
        '策略侧分类 = 待建模桶(维持的金流价值轨迹依赖)'
    assert 'loss_hp_extra' in _NOT_SCORED_FIELDS, \
        '策略侧分类 = 不计分桶(纯负向成本无正账可折)'
    assert 'loss_hp_extra' not in _PENDING_MODELING_FIELDS, \
        '两桶互斥(三分闭集无双归属)'
    assert 'keep_streak_on_loss' not in _NOT_SCORED_FIELDS, \
        '两桶互斥(三分闭集无双归属)'


def test_loss_battle_modifier_aggregation() -> None:
    """helper 纯锁:持嘴硬聚合 = (5, True)(hp 求和/维持取或);
    表外卡名跳过(零命中零修饰);空名单 (0, False);表内+表外混合 =
    表内成员独立计入。"""
    assert strategy_loss_battle_modifier([_CARD]) == (5, True), \
        '单卡聚合 = 注册行现值直读'
    assert strategy_loss_battle_modifier(['不存在的卡']) == (0, False), \
        '表外卡名跳过(零修饰)'
    assert strategy_loss_battle_modifier([]) == (0, False), \
        '空名单零修饰'
    assert strategy_loss_battle_modifier([_CARD, '不存在的卡']) == (5, True), \
        '混合名单只计表内成员'
