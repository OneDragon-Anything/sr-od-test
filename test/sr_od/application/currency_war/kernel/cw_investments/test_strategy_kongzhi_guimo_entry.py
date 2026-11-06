"""控制规模(id 302901)登记面锁(cw_investments 分目录镜像;等级帽覆写族
首例 + 具名装备授予族后继;先例 = 同目录 test_strategy_lixishang_entry.py
声明性条目锁形)。

测试面依据 = 迭代设计 designs/T-324-kongzhi-guimo.md §4 锁 2/6/7
(REVIEW-T324 无需用户决定 7/7;卡面官方原文:「最大等级变为7级，获得【财富宝钻】
和40金币。」——帽改写腿 level_cap_override=7 注册行承载 / 宝钻腿 =
cw_gain_effects.PICK_INVEST_EFFECTS 具名装备登记行 / 40 金腿 =
instant_gold=40 已登记估值零漂):

- 注册行直测(锁 2):level_cap_override == 7 ∧ instant_gold == 40
  (等值扩写——金面零漂);
- 双闭集伴随(锁 2):level_cap_override ∈ 引擎排除桶(_ENGINE_CHANNEL_
  EXCLUDED_FIELDS 进度轴结构改写族)∧ ∈ 策略侧 _NOT_SCORED_FIELDS
  (结构登记永不为分)——两闸 import 即炸防线随本文件 import 自证,
  显式成员断言兜显式登记;is_economy_engine 维持 False(帽字段非持续
  收入通道,方向守卫零扰);
- 反扫闭集零破面(锁 6):卡文「获得」窗 30 字内无 roster 名
  (【财富宝钻】系装备名),机械反扫候选集零命中(闸 import 已自证,
  本锁程序化断言留痕);
- 采样池规模锁(锁 7):len(INVESTMENT_STRATEGIES) 现值不变(登记不扩池)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTER_ROSTER
from sr_od.application.currency_war.kernel.cw_investments import (
    _ENGINE_CHANNEL_EXCLUDED_FIELDS,
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    _scan_strategy_grant_candidates,
    is_economy_engine,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    _NOT_SCORED_FIELDS,
)

_CARD = '控制规模'

#: 采样池现值基线(登记不扩池;版本重采改数随批复核卡数来源后更新)。
_POOL_SIZE = 335


def test_registry_row_value() -> None:
    """注册行直测(锁 2):帽腿 7 ∧ 金腿 40 等值扩写(估值现金计分零漂)。"""
    eff = STRATEGY_ECONOMY[_CARD]
    assert eff.level_cap_override == 7
    assert eff.instant_gold == 40


def test_dual_closure_membership_and_engine_off() -> None:
    """双闭集伴随 + 引擎判别零扰(锁 2):新字段显式落引擎排除桶与策略侧
    不计桶(缺位 = 各自 import 期校验炸,本断言兜显式登记);
    is_economy_engine 维持 False——帽字段非持续收入通道。"""
    assert 'level_cap_override' in _ENGINE_CHANNEL_EXCLUDED_FIELDS
    assert 'level_cap_override' in _NOT_SCORED_FIELDS
    assert is_economy_engine(STRATEGY_ECONOMY[_CARD]) is False


def test_anti_scan_closure_zero_hit() -> None:
    """反扫闭集零破面(锁 6):卡文「获得…」窗内无 roster 名程序化断言
    (【财富宝钻】系装备名非角色)——候选集零命中,登记不触发闭集动作
    (闸 import 已自证,本锁留程序化痕)。"""
    assert _CARD not in _scan_strategy_grant_candidates()
    effect = INVESTMENT_STRATEGIES[_CARD].effect
    idx = effect.find('获得')
    assert idx >= 0, '卡文含「获得」句(卡面原文自证)'
    seg = effect[idx + len('获得'): idx + len('获得') + 30]
    assert not any(c in seg for c in CHARACTER_ROSTER), \
        f'卡文出现 roster 名:反扫判读前提漂移 {seg!r}'


def test_sample_pool_size_unchanged() -> None:
    """采样池规模锁(锁 7):登记不扩池——STRATEGY_ECONOMY 行扩写不进
    采样池,池规模维持基线。"""
    assert len(INVESTMENT_STRATEGIES) == _POOL_SIZE
