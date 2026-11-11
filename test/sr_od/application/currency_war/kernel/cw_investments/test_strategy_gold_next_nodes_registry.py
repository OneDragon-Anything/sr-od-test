"""长期主义注册面测试(cw_investments 分目录镜像;登记锁先例 =
同目录 test_strategy_dingqi_fuli_registry.py)。

测试面依据 = 设计稿(原件已退役) 设计稿(原件已退役) §4 锁 1(已退役评审稿(§ 号 = 原稿节序)§4.3 同面)。卡面官方原文
(cw_invest_data.py):「现在及接下来3次进入新节点时，每次获得7金币。」

- 注册面锁:STRATEGY_ECONOMY['长期主义'] 条目以 frozen dataclass 值相等
  形态锁分期金双字段 = gold_next_nodes_amount=7 ∧ gold_next_nodes_count=3
  (数值 = 卡面 desc 逐字;值相等形态 = 任何其他字段的意外污染同样红,
  姊妹行「长期主义+」9/3 已随 T-178 批直测);
- 分期族键空间负锁:卡无 STRATEGY_EFFECTS(EffectSpec)条目——economy-only
  注册(战场段零登记),入集 = 越约。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)

_CARD = '长期主义'


def test_changqi_zhuyi_economy_registration_surface() -> None:
    """长期主义 注册面锁(锁 1):分期金双字段 frozen dataclass 值相等
    (amount=7「每次获得7金币」/count=3「接下来3次进入新节点」;本测试
    存活同时证明构建校验通过——注册表孤儿键/双匹配闸在 import 期)。"""
    assert STRATEGY_ECONOMY[_CARD] == EconomyEffect(
        gold_next_nodes_amount=7, gold_next_nodes_count=3), \
        '分期金注册行 = 卡面 desc 逐字(7/3;值相等形态,任何额外字段污染同红)'
    assert _CARD in INVESTMENT_STRATEGIES, '策略名入 base 注册表'


def test_changqi_zhuyi_no_effect_spec_entry() -> None:
    """分期族键空间负锁:卡无 STRATEGY_EFFECTS 条目(economy-only 注册,
    无战场段只登记不写状态的实现分支;入集 = 越约——分期金唯一新增机制件住 sim 把结果写进状态副本的实现分支,
    不走 effects 自动递减通道,T-191 r1-F2 同证口径)。"""
    assert _CARD not in STRATEGY_EFFECTS, 'economy-only 注册零 EffectSpec 条目'


def test_changqi_zhuyi_plus_registration_row() -> None:
    """姊妹注册行直测(长期主义+,T-178 批):分期金双字段 frozen
    dataclass 值相等(amount=9「每次获得9金币」/count=3「接下来3次」;
    与模式卡唯一差异 = 金额 7→9);economy-only 注册同构负锁。"""
    assert STRATEGY_ECONOMY['长期主义+'] == EconomyEffect(
        gold_next_nodes_amount=9, gold_next_nodes_count=3), \
        '姊妹注册行 = 卡面 desc 逐字(9/3;值相等形态)'
    assert '长期主义+' in INVESTMENT_STRATEGIES, '策略名入 base 注册表'
    assert '长期主义+' not in STRATEGY_EFFECTS, 'economy-only 注册同构'
