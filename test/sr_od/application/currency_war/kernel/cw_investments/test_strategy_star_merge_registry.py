"""星星相印注册面测试(cw_investments 分目录镜像;单一源 + 载体声明 +
引擎桶落位,先例 = 同目录 test_strategy_refresh_pair_registry.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-135-xingxing-
xiangyin.md(定稿)§4 锁 3 + REVIEW-T135 §四 ④。卡面官方原文:「每次合成
3星角色时，获得5金币。立刻获得1个【员工投影仪】。」

- 载体直测:STRATEGY_EFFECTS['星星相印'] trigger = ON_MERGE ∧
  payload is STRATEGY_ECONOMY 注册行同一实例(防表外安静返 0/双
  overlay 漂移;payload 误复制实例即红);
- 数值单一源:gold_per_3star_merge = 5(卡面明写);
- 引擎闭集落位:gold_per_3star_merge ∈ 引擎单字段桶
  (is_economy_engine 判据现值即真,持续通道零新增动作);
- 双向隔离基准:本卡 payload 无 refresh_per_compose 字段(缺省 0,
  与武力刷新刷新腿天然隔离)/ 武力刷新 payload 无本卡字段(反向
  同构)——字段判别双向鸭子缺省的行为面归
  test_check_strategy_star_merge_gold 互证锁。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
    is_economy_engine,
)


def test_star_merge_spec_single_source_identity() -> None:
    """载体直测:payload 必须为注册行同一实例(单一源)+ plaza id /
    触发 / 持续 / 类别声明对拍(ON_MERGE 后继条目,首条 = 武力刷新)。"""
    spec = STRATEGY_EFFECTS['星星相印']
    assert spec.payload is STRATEGY_ECONOMY['星星相印'], \
        'payload 必须为注册行同一实例(单一源)'
    assert spec.id == '104001', 'plaza id 对拍'
    assert spec.trigger is TriggerKind.ON_MERGE, '触发声明 = 合成时(共用载体)'
    assert spec.duration is DurationKind.WHILE_HELD, '持续 = 与持有绑定'
    assert spec.category is EffectKind.ECONOMY, '类别声明 = 经济发放'


def test_star_merge_registry_value_and_engine_bucket() -> None:
    """数值单一源 + 引擎闭集:gold_per_3star_merge = 5(卡面明写,防
    表外安静返 0);字段在引擎单字段桶(持续通道,is_economy_engine 真);
    附双字段互斥缺省(本卡 refresh_per_compose 缺省 0 / 武力刷新
    gold_per_3star_merge 缺省 0——两条效果条目字段判别隔离的注册面基准)。"""
    eff = STRATEGY_ECONOMY['星星相印']
    assert eff.gold_per_3star_merge == 5, '合成 3 星 +5(卡面明写)'
    assert eff.refresh_per_compose == 0, '本卡无刷新腿字段(缺省 0)'
    assert is_economy_engine(eff) is True, '引擎单字段桶生效(持续通道)'
    assert STRATEGY_ECONOMY['武力刷新'].gold_per_3star_merge == 0, \
        '反向缺省:武力刷新无本卡字段(双向鸭子缺省隔离)'
    assert is_economy_engine(
        EconomyEffect(gold_per_3star_merge=5)) is True, \
        '谓词直测(与注册行同判)'
