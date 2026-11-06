"""超发货币注册面测试(cw_investments 分目录镜像;登记锁先例 =
同目录 test_strategy_gold_next_nodes_registry.py,闭集伴随先例 =
test_strategy_refresh_pair_registry.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-191-chaofa-
huobi.md §3 锁 1/锁 2(REVIEW-T191 §四④ 锁 1 落位修正:本卡注册锁落
拆目录新文件——test_cw_investments.py 1355 行超 800 拆分线禁追加)。
卡面官方原文(cw_invest_data.py):「失去你现在所有的金币，并在5个
节点后，获得该金币数+70的总金币。」

- 注册行锁(锁 1):STRATEGY_ECONOMY['超发货币'] 条目以 frozen dataclass
  值相等形态锁时点大额双字段 = gold_at_node=70 ∧ gold_at_node_offset=5
  (数值 = 卡面 desc 逐字;值相等形态 = 任何其他字段的意外污染同样红);
- 条目形状锁:STRATEGY_EFFECTS 条目 duration_nodes=6(发放入口序 =
  offset+1 的载体表达,裁定出处 = strategy-env-impacts.md 超发货币条目
  用户裁定 2026-09-10)+ payload 同一实例(单一源)+ duties 全空 +
  pending=False;
- 判别键一致性锁:HYPEREMIT_SPEC_ID/NAME 常量与注册行/条目对拍(漂移
  即红——登记播值腿与 sim 两条效果条目共用判别键,静默漂移 = 三条效果条目全失联);
- 双闭集伴随锁(锁 2):gold_at_node/gold_at_node_offset ∈ 引擎排除桶
  _ENGINE_CHANNEL_EXCLUDED_FIELDS ∧ ∈ 估值待建模字段集
  _PENDING_MODELING_FIELDS(薄锁防漂移;import 期炸校验已兜底)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    DutyFlags,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _ENGINE_CHANNEL_EXCLUDED_FIELDS,
    HYPEREMIT_SPEC_ID,
    HYPEREMIT_SPEC_NAME,
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    _PENDING_MODELING_FIELDS,
)

_CARD = '超发货币'


def test_chaofa_huobi_economy_registration_surface() -> None:
    """注册行直测(锁 1):时点大额双字段 frozen dataclass 值相等
    (gold_at_node=70「该金币数+70的总金币」/gold_at_node_offset=5
    「在5个节点后」;负债部分无字段载体,由消费端按持有金处理——注册行
    随行注释现值)。本测试存活同时证明构建校验通过(孤儿键/双匹配闸
    在 import 期)。"""
    assert STRATEGY_ECONOMY[_CARD] == EconomyEffect(
        gold_at_node=70, gold_at_node_offset=5), \
        '注册行 = 卡面 desc 逐字(70/5;值相等形态,任何额外字段污染同红)'
    assert _CARD in INVESTMENT_STRATEGIES, '策略名入 base 注册表'


def test_chaofa_huobi_effect_spec_entry_shape() -> None:
    """条目形状锁:STRATEGY_EFFECTS 已登记(漏登记 = 获得链静默失联面)+
    duration_nodes=6(入口序 = offset+1,用户裁定 2026-09-10)+ payload
    同一实例(单一源,误复制实例即红)+ duties 全空(余期推进 N_NODES
    结构自动,回流发放不住 duties)+ pending=False。"""
    spec = STRATEGY_EFFECTS.get(_CARD)
    assert spec is not None, '条目已登记'
    assert spec.id == '202501', 'plaza id 对拍'
    assert spec.name == _CARD, '规范名对拍'
    assert spec.trigger is TriggerKind.CONDITIONAL, '触发声明占 CONDITIONAL'
    assert spec.duration is DurationKind.N_NODES, '余期维度 = 节点递减'
    assert spec.category is EffectKind.ECONOMY, '类别声明 = 经济发放'
    assert spec.payload is STRATEGY_ECONOMY[_CARD], 'payload 同一实例(单一源)'
    assert spec.duties == DutyFlags(), 'duties 全空'
    assert spec.duration_nodes == 6, \
        '发放入口序 = offset(5)+1 = 第 6 次节点入口(用户裁定 2026-09-10)'
    assert spec.pending is False, '两分支语义已定谳,无保守支'


def test_chaofa_huobi_discriminator_keys_match_registry() -> None:
    """判别键一致性锁:HYPEREMIT_SPEC_ID/NAME 与注册行/条目对拍
    (登记播值腿与 sim 清零/回流两条效果条目共用的条目判别键,漂移即红)。"""
    assert HYPEREMIT_SPEC_ID == '202501'
    assert HYPEREMIT_SPEC_NAME == _CARD
    assert STRATEGY_EFFECTS[HYPEREMIT_SPEC_NAME].id == HYPEREMIT_SPEC_ID
    assert INVESTMENT_STRATEGIES[HYPEREMIT_SPEC_NAME].source == \
        f'plaza:{HYPEREMIT_SPEC_ID}'


def test_chaofa_huobi_fields_in_double_closed_sets() -> None:
    """双闭集伴随(锁 2):gold_at_node/gold_at_node_offset ∈ 引擎排除桶
    ∧ ∈ 估值待建模字段集(薄锁防漂移;漏登记 = 字段进持续通道引擎/
    被估值通道误消费)。"""
    for field_name in ('gold_at_node', 'gold_at_node_offset'):
        assert field_name in _ENGINE_CHANNEL_EXCLUDED_FIELDS, field_name
        assert field_name in _PENDING_MODELING_FIELDS, field_name
